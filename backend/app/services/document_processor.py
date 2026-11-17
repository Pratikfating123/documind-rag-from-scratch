"""Stage 2: extract text (with page numbers / sections) from PDF, DOCX and TXT."""
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


class ExtractionError(Exception):
    pass


@dataclass
class ExtractedPage:
    text: str
    page_number: Optional[int] = None
    section: Optional[str] = None


_BULLET_START = re.compile(r"^\s*(?:[•●▪◦·*\-–]|\d{1,2}[.)])\s+")


def _join_lines(lines: list[str]) -> str:
    """Join the lines of one PDF paragraph: keep list items on separate lines, repair hyphenated wraps."""
    lines = [l.strip() for l in lines if l.strip()]
    if any(_BULLET_START.match(l) for l in lines):
        return "\n".join(lines)
    text = ""
    for l in lines:
        if text.endswith("-") and l[:1].islower():
            text = text[:-1] + l  # "retrie-\nval" -> "retrieval"
        else:
            text = f"{text} {l}" if text else l
    return text


def _page_text_structured(page) -> str:
    """Paragraphs separated by blank lines; headings (larger or fully-bold short lines) as '## Heading'."""
    data = page.get_text("dict", sort=True)
    lines = []  # (text, size, bold, block_no)
    for b in data.get("blocks", []):
        if b.get("type") != 0:
            continue
        for ln in b.get("lines", []):
            spans = [sp for sp in ln.get("spans", []) if sp.get("text", "").strip()]
            if not spans:
                continue
            text = "".join(sp["text"] for sp in ln["spans"]).strip()
            size = max(sp["size"] for sp in spans)
            bold = all((sp.get("flags", 0) & 16) or "bold" in sp.get("font", "").lower() for sp in spans)
            lines.append((text, size, bool(bold), b.get("number")))
    if not lines:
        return ""
    weights = Counter()
    for text, size, _, _ in lines:
        weights[round(size, 1)] += len(text)
    body_size = weights.most_common(1)[0][0]

    def is_heading(text, size, bold):
        words = text.split()
        if len(words) > 14 or text.endswith((".", ",", ";")):
            return False
        return size >= body_size + 0.8 or (bold and len(words) <= 10 and size >= body_size - 0.1)

    out, para, para_block = [], [], None
    last_heading_block = None

    def flush():
        nonlocal para
        if para:
            out.append(_join_lines(para))
        para = []

    for text, size, bold, block in lines:
        if is_heading(text, size, bold):
            flush()
            if last_heading_block == block and out and out[-1].startswith("## "):
                out[-1] += " " + text  # heading wrapped over two lines
            else:
                out.append("## " + text)
            last_heading_block = block
            para_block = None
            continue
        if para and block != para_block:
            flush()
        para.append(text)
        para_block = block
    flush()
    return "\n\n".join(out)


def _page_text(page) -> str:
    try:
        text = _page_text_structured(page)
        if text.strip():
            return text
    except Exception:  # noqa: BLE001 - never lose a page because of layout analysis
        pass
    try:
        blocks = page.get_text("blocks", sort=True)
        return "\n\n".join(_join_lines(b[4].split("\n")) for b in blocks if b[6] == 0 and b[4].strip())
    except Exception:  # noqa: BLE001
        return page.get_text("text")


def extract_pdf(path: Path) -> list[ExtractedPage]:
    import fitz  # PyMuPDF
    try:
        doc = fitz.open(path)
    except Exception as e:
        raise ExtractionError(f"Could not open PDF (corrupted?): {e}")
    pages = []
    with doc:
        for i, page in enumerate(doc, start=1):
            text = _page_text(page).strip()
            if text:
                pages.append(ExtractedPage(text=text, page_number=i))
    return pages


def extract_docx(path: Path) -> list[ExtractedPage]:
    import docx
    try:
        d = docx.Document(str(path))
    except Exception as e:
        raise ExtractionError(f"Could not open DOCX (corrupted?): {e}")
    pages: list[ExtractedPage] = []
    section, buf = None, []

    def flush():
        text = "\n\n".join(buf).strip()
        if text:
            pages.append(ExtractedPage(text=text, page_number=None, section=section))
        buf.clear()

    for p in d.paragraphs:
        if p.style is not None and p.style.name.lower().startswith("heading") and p.text.strip():
            flush()
            section = p.text.strip()
        elif p.text.strip():
            buf.append(p.text.strip())
    flush()
    return pages


def extract_txt(path: Path) -> list[ExtractedPage]:
    for enc in ("utf-8", "utf-16", "latin-1"):
        try:
            text = path.read_text(encoding=enc).strip()
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    else:
        raise ExtractionError("Could not decode the text file.")
    return [ExtractedPage(text=text, page_number=1)] if text else []


def extract_document(path: Path) -> list[ExtractedPage]:
    ext = path.suffix.lower()
    extractors = {".pdf": extract_pdf, ".docx": extract_docx, ".txt": extract_txt}
    if ext not in extractors:
        raise ExtractionError(f"Unsupported file type: {ext}")
    pages = extractors[ext](path)
    if not pages:
        raise ExtractionError("No readable text found in this document (it may be empty or scanned images).")
    return pages
