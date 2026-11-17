"""Stage 7: retrieval engine.

1. Embed the query and fetch the top CANDIDATE_K chunks by cosine similarity (NO threshold yet).
2. Remove duplicates / near-duplicates.
3. Drop chunks whose ORIGINAL cosine score is below the similarity threshold (threshold is never lowered).
4. Re-rank the survivors:  rerank = cosine + 0.20*keyword_coverage + 0.05*phrase_match.
   Chunks tagged kind="questions" (lists of test questions / testing notes) are placed AFTER all explanatory
   chunks, however high their score: they mirror the user's wording but contain no answer.
   The original cosine score is preserved in `score`; `rerank_score` only decides the ORDER.
5. Return the top_k, each with neighbouring text from the same section as extra context for the LLM.
Every step is logged under the logger name "rag.retrieval".
"""
import logging
import re
from typing import Optional

from app.config import settings
from app.services.text_chunker import classify_chunk, split_sentences

logger = logging.getLogger("rag.retrieval")

LEX_WEIGHT = 0.20
PHRASE_BONUS = 0.05
NEAR_DUPLICATE_JACCARD = 0.90

# Short forms users type vs. the long forms documents usually spell out (and vice versa).
# Both forms are searched, so "ML" also finds text that only says "machine learning".
ABBREVIATIONS = {
    "ai": "artificial intelligence", "ml": "machine learning", "dl": "deep learning",
    "nlp": "natural language processing", "llm": "large language model", "llms": "large language models",
    "rl": "reinforcement learning", "rag": "retrieval-augmented generation",
}

_STOP = {"the", "and", "for", "are", "was", "with", "that", "this", "from", "what", "how", "why", "which",
         "does", "can", "you", "your", "about", "into", "has", "have", "its", "not", "but", "who", "when",
         "explain", "describe", "tell", "give", "works", "work", "useful", "used", "use", "also", "some",
         "between", "difference", "relationship", "components", "component", "three", "two"}


def _tokens(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2 and w not in _STOP]


def _terms(text: str) -> set[str]:
    return set(_tokens(text))


def _stem(w: str) -> str:
    return w[:5] if len(w) > 5 else w  # crude prefix stemming: retrieval/retrieves -> retri


def _stems(text: str) -> list[str]:
    return [_stem(t) for t in _tokens(text)]


def _bigrams(seq: list[str]) -> set[tuple[str, str]]:
    return set(zip(seq, seq[1:]))


def _norm_words(content: str) -> list[str]:
    return re.sub(r"\s+", " ", content.lower()).strip().split()


def _jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def expand_query(query: str) -> str:
    """Append the long form of known abbreviations (and the short form of known long forms)."""
    low = query.lower()
    extra = []
    for short, long in ABBREVIATIONS.items():
        if re.search(rf"\b{re.escape(short)}\b", low) and long not in low:
            extra.append(long)
        elif long in low and not re.search(rf"\b{re.escape(short)}\b", low):
            extra.append(short.upper())
    return f"{query} ({', '.join(extra)})" if extra else query


class Retriever:
    def __init__(self, store, embedder):
        self.store = store
        self.embedder = embedder

    expand_query = staticmethod(expand_query)

    def retrieve(self, query: str, top_k: Optional[int] = None, threshold: Optional[float] = None,
                 document_ids: Optional[list[str]] = None) -> list[dict]:
        query = (query or "").strip()
        top_k = top_k or settings.TOP_K
        threshold = settings.SIMILARITY_THRESHOLD if threshold is None else threshold
        search_query = expand_query(query) if query else query
        qvec = self.embedder.embed_query(search_query)  # raises EmptyTextError for blank queries

        n_candidates = max(settings.CANDIDATE_K, top_k * 2)
        raw = self.store.search(qvec, top_k=n_candidates, threshold=-1.0, document_ids=document_ids)

        q_stems = _stems(search_query)
        q_set, q_bigrams = set(q_stems), _bigrams(q_stems)
        kept, seen_sets, decisions = [], [], []
        for hit in raw:
            words = set(_norm_words(hit["content"]))
            kind = hit.get("kind") or classify_chunk(hit.get("section"), hit["content"])
            if any(_jaccard(words, s) >= NEAR_DUPLICATE_JACCARD for s in seen_sets):
                decisions.append((hit, kind, None, "dropped: duplicate"))
                continue
            seen_sets.append(words)
            if hit["score"] < threshold:
                decisions.append((hit, kind, None, f"dropped: cosine below threshold {threshold:.2f}"))
                continue
            c_stems = _stems(hit["content"])
            coverage = len(q_set & set(c_stems)) / len(q_set) if q_set else 0.0
            phrase = 1.0 if q_bigrams & _bigrams(c_stems) else 0.0
            rerank = hit["score"] + LEX_WEIGHT * coverage + PHRASE_BONUS * phrase
            kept.append((rerank, coverage, kind, hit))
            decisions.append((hit, kind, rerank, "kept"))

        kept.sort(key=lambda t: (t[2] == "content", t[0], t[3]["score"]), reverse=True)
        results = []
        for rank, (rerank, coverage, kind, hit) in enumerate(kept[:top_k], start=1):
            results.append({
                "rank": rank, "label": f"S{rank}",
                "document_id": hit["document_id"], "document_name": hit["document_name"],
                "chunk_id": hit["chunk_id"], "chunk_index": hit["chunk_index"],
                "page_number": hit.get("page_number"), "section": hit.get("section"),
                "score": round(hit["score"], 4),          # original cosine similarity, untouched
                "rerank_score": round(rerank, 4), "keyword_coverage": round(coverage, 2),
                "kind": kind, "content": hit["content"],
            })
        self._attach_context(results)
        self._log(query, search_query, threshold, len(raw), len(kept), decisions, results)
        return results

    # ------------------------------------------------------------------ context & logging
    def _attach_context(self, results: list[dict]) -> None:
        """Add the previous/next chunk of the SAME section so the LLM sees the full passage."""
        index = {(m["document_id"], m["chunk_index"]): m for m in self.store.metadata}
        budget = settings.EMBED_MAX_WORDS * 3
        for r in results:
            parts = [r["content"]]
            if r.get("section") and r["kind"] == "content":
                prev = index.get((r["document_id"], r["chunk_index"] - 1))
                nxt = index.get((r["document_id"], r["chunk_index"] + 1))
                if prev and prev.get("section") == r["section"] and prev.get("kind", "content") == "content":
                    extra = [s for s in split_sentences(prev["content"]) if s not in r["content"]]
                    if extra:
                        parts.insert(0, " ".join(extra))
                if nxt and nxt.get("section") == r["section"] and nxt.get("kind", "content") == "content":
                    extra = [s for s in split_sentences(nxt["content"]) if s not in r["content"]]
                    if extra:
                        parts.append(" ".join(extra))
                if sum(len(p.split()) for p in parts) > budget:
                    parts = [r["content"]]
            r["context"] = "\n\n".join(parts)

    def _log(self, query, search_query, threshold, n_raw, n_kept, decisions, results) -> None:
        limit = settings.LOG_TEXT_CHARS
        logger.info("QUERY %r | searched as %r | candidates before filtering=%d | after filtering=%d | "
                    "returned=%d | threshold=%.2f", query, search_query, n_raw, n_kept, len(results), threshold)
        returned = {r["chunk_id"] for r in results}
        for hit, kind, rerank, status in decisions:
            text = hit["content"] if limit <= 0 else hit["content"][:limit].replace("\n", " ")
            used = "RETURNED" if hit["chunk_id"] in returned else status
            logger.info("  doc=%s chunk_id=%s idx=%s page=%s cosine=%.3f rerank=%s kind=%s -> %s | %s",
                        hit["document_name"], hit["chunk_id"][:8], hit["chunk_index"], hit.get("page_number"),
                        hit["score"], f"{rerank:.3f}" if rerank is not None else "-", kind, used, text)

    @staticmethod
    def explain(query: str, hit: dict, threshold: float) -> str:
        shared = sorted(_terms(query) & _terms(hit["content"]))[:8]
        verdict = "above" if hit["score"] >= threshold else "below"
        text = (f"Ranked #{hit['rank']} with cosine similarity {hit['score']:.3f} ({verdict} the threshold "
                f"{threshold:.2f}); re-rank score {hit.get('rerank_score', hit['score']):.3f}.")
        if shared:
            text += f" Shared keywords: {', '.join(shared)}."
        else:
            text += " No shared keywords - this match comes from semantic (meaning-based) similarity."
        if hit.get("kind") == "questions":
            text += " This chunk looks like a list of test questions/notes, so it is ranked after explanatory chunks and never sent to the LLM."
        return text
