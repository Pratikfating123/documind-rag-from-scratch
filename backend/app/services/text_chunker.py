"""Stage 3 (v2): structure-aware chunking.

What changed from v1 (which produced ONE chunk per page, mixing unrelated sections):
  * Text is split into paragraphs and headings first; chunks never mix two sections.
  * Each chunk starts with its section heading, so the embedding "knows" its topic.
  * Sizes are in words but are capped to the embedding model's window (see settings.effective_chunking)
    and then verified with the real tokenizer, so no chunk is silently truncated.
  * Overlap only happens inside one section (sentence-level), never across headings.
  * Chunks still never cross pages, so page numbers stay exact.
  * Each chunk is tagged kind="content" or "questions" (lists of test questions / testing notes),
    so the retriever can avoid answering from them.
"""
import re
from dataclasses import dataclass, replace
from typing import Callable, Optional

from app.services.document_processor import ExtractedPage
from app.utils.helpers import new_id

CHUNKER_VERSION = "2"

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_BULLET_RE = re.compile(r"^\s*(?:[•●▪◦·*\-–]|\d{1,2}[.)]|[a-z][.)])\s+")
_NUMBERED_HEADING = re.compile(r"^\d+(?:\.\d+)*\.?\s+[A-Z]")
_SMALL_WORDS = {"a", "an", "and", "as", "at", "by", "for", "in", "of", "on", "or", "the", "to", "vs", "with", "is", "are"}
_META_HEADING = re.compile(
    r"\b(suggested|sample|test|testing|practice|review)\b.*\b(questions?|queries|notes?)\b|\btesting note\b", re.I)


@dataclass
class TextChunk:
    chunk_id: str
    document_id: str
    chunk_index: int
    content: str
    page_number: Optional[int]
    section: Optional[str]
    kind: str = "content"


@dataclass
class _Piece:
    text: str
    words: int
    sep: str = " "  # separator placed AFTER this piece when joined


def _wc(s: str) -> int:
    return len(s.split())


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n{2,}", text) if s.strip()]


# ------------------------------------------------------------------ structure detection
def _looks_like_heading(line: str, strict: bool = False) -> bool:
    line = line.strip()
    if not line or "\n" in line or len(line) > 100:
        return False
    words = line.split()
    if not 1 <= len(words) <= (8 if strict else 12) or line[-1] in ".!,;":
        return False
    if line[-1] == "?":  # "What Is Artificial Intelligence?" is a heading; "What is RAG?" is a question
        cand = [w for w in words if w.lower() not in _SMALL_WORDS and w[0].isalpha()]
        return (len(words) >= 2 and bool(cand) and all(w[0].isupper() for w in cand)
                and not _BULLET_RE.match(line))
    core = line.rstrip(":").strip()
    if _NUMBERED_HEADING.match(core):
        return True
    if _BULLET_RE.match(line):
        return False
    if line.endswith(":") and not strict:
        return True
    cand = [w for w in core.split() if w.lower() not in _SMALL_WORDS and w[0].isalpha()]
    if not cand:
        return False
    return sum(w[0].isupper() for w in cand) / len(cand) >= (0.8 if strict else 0.6)


def _blocks(text: str) -> list[str]:
    return [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]


def _split_heading(block: str) -> tuple[Optional[str], Optional[str]]:
    """Returns (heading, remaining_body). Either may be None."""
    if block.startswith("## "):
        first, _, rest = block[3:].partition("\n")
        return first.strip(), (rest.strip() or None)
    if "\n" not in block:
        return (block.rstrip(":").strip(), None) if _looks_like_heading(block) else (None, block)
    first, _, rest = block.partition("\n")
    if rest.strip() and _looks_like_heading(first, strict=True):
        return first.rstrip(":").strip(), rest.strip()
    return None, block


def _paragraph_pieces(block: str) -> list[_Piece]:
    lines = [l.strip() for l in block.split("\n") if l.strip()]
    if any(_BULLET_RE.match(l) for l in lines):  # lists: one piece per line
        pieces = [_Piece(l, _wc(l), "\n") for l in lines]
    else:
        text = " ".join(lines)
        pieces = [_Piece(s.strip(), _wc(s), " ") for s in _SENTENCE_RE.split(text) if s.strip()]
    if pieces:
        pieces[-1].sep = "\n\n"
    return pieces


def classify_chunk(section: Optional[str], body: str) -> str:
    """'questions' for lists of test/sample questions and testing notes, else 'content'."""
    if section and _META_HEADING.search(section):
        return "questions"
    parts = [p.strip() for p in re.split(r"\n|(?<=[.!?])\s+", body) if p.strip()]
    if len(parts) >= 3 and sum(p.endswith("?") for p in parts) / len(parts) >= 0.5:
        return "questions"
    if re.match(r"\s*(testing note|note for testers?)\b", body, re.I):
        return "questions"
    return "content"


# ------------------------------------------------------------------ packing
def _explode(text: str, size: int) -> list[str]:
    words = text.split()
    return [" ".join(words[i:i + size]) for i in range(0, len(words), size)]


def _render(pieces: list[_Piece]) -> str:
    out = []
    for i, p in enumerate(pieces):
        out.append(p.text)
        if i < len(pieces) - 1:
            out.append(p.sep)
    return "".join(out).strip()


def _pack(pieces: list[_Piece], size: int, overlap: int) -> list[str]:
    flat: list[_Piece] = []
    for p in pieces:
        if p.words > size:  # a single sentence longer than a whole chunk
            parts = _explode(p.text, size)
            flat.extend(_Piece(t, _wc(t), p.sep if i == len(parts) - 1 else " ") for i, t in enumerate(parts))
        else:
            flat.append(p)

    chunks: list[str] = []
    cur: list[_Piece] = []
    count = 0
    has_new = False  # does `cur` hold anything beyond carried-over overlap?
    for p in flat:
        if cur and count + p.words > size:
            chunks.append(_render(cur))
            carry, carried = [], 0
            for prev in reversed(cur):
                if carried + prev.words > overlap:
                    break
                carry.insert(0, prev)
                carried += prev.words
            while carry and carried + p.words > size:
                carried -= carry.pop(0).words
            cur, count, has_new = carry, carried, False
        cur.append(p)
        count += p.words
        has_new = True
    if cur and has_new:
        chunks.append(_render(cur))
    return chunks


def chunk_text(text: str, chunk_size: int = 150, overlap: int = 30) -> list[str]:
    """Chunk plain text (paragraph/sentence aware, no heading handling)."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be >= 0 and smaller than chunk_size")
    pieces: list[_Piece] = []
    for block in _blocks(text):
        pieces.extend(_paragraph_pieces(block))
    return _pack(pieces, chunk_size, overlap)


# ------------------------------------------------------------------ page-level API
def _refit(chunks: list[TextChunk], count_tokens: Callable[[list[str]], list[int]],
           max_tokens: int, overlap: int) -> list[TextChunk]:
    """Re-split any chunk the embedding model would truncate (measured with its real tokenizer)."""
    if not chunks:
        return chunks
    counts = count_tokens([c.content for c in chunks])
    out: list[TextChunk] = []
    for c, n in zip(chunks, counts):
        if n <= max_tokens:
            out.append(c)
            continue
        words = max(_wc(c.content), 1)
        prefix = f"{c.section}\n\n" if c.section and c.content.startswith(f"{c.section}\n\n") else ""
        body = c.content[len(prefix):]
        new_size = max(20, int(max_tokens / (n / words) * 0.85) - _wc(c.section or ""))
        for sub in chunk_text(body, new_size, min(overlap, new_size // 3)):
            out.append(replace(c, chunk_id=new_id(), content=prefix + sub))
    return out


def chunk_pages(pages: list[ExtractedPage], document_id: str, chunk_size: int = 150, overlap: int = 30,
                count_tokens: Optional[Callable[[list[str]], list[int]]] = None,
                max_tokens: Optional[int] = None) -> list[TextChunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be >= 0 and smaller than chunk_size")

    chunks: list[TextChunk] = []
    heading: Optional[str] = None
    for page in pages:
        heading = page.section or heading  # heading carries across pages until a new one appears
        if heading and _META_HEADING.search(heading):
            heading = None  # a "Testing Note" must not swallow the next page's real content
        groups: list[tuple[Optional[str], list[_Piece]]] = []
        cur_heading, cur_pieces = heading, []
        for block in _blocks(page.text):
            h, body = _split_heading(block)
            if h is not None:
                if cur_pieces:
                    groups.append((cur_heading, cur_pieces))
                heading, cur_heading, cur_pieces = h, h, []
            if body:
                cur_pieces.extend(_paragraph_pieces(body))
        if cur_pieces:
            groups.append((cur_heading, cur_pieces))

        for h, pieces in groups:
            size = max(20, chunk_size - (_wc(h) if h else 0))
            for body in _pack(pieces, size, min(overlap, size // 3)):
                chunks.append(TextChunk(new_id(), document_id, 0, f"{h}\n\n{body}" if h else body,
                                        page.page_number, h, classify_chunk(h, body)))

    if count_tokens and max_tokens:
        chunks = _refit(chunks, count_tokens, max_tokens, overlap)
    for i, c in enumerate(chunks):
        c.chunk_index = i
    return chunks
