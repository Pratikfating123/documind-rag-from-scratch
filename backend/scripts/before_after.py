"""Before/after comparison on the fixture documents:  python -m scripts.before_after

OLD = v1 chunker (500/100 words, one chunk per page) + cosine-only retrieval, threshold 0.25.
NEW = v2 chunker + candidates -> threshold -> re-rank -> tiering.
Both use the FakeEmbedder with max_words=190 to SIMULATE MiniLM's silent 256-token truncation.
This is a simulation of the mechanism, NOT a measurement of MiniLM. For real numbers run
scripts/diagnose_retrieval.py on your machine.
"""
import tempfile
from pathlib import Path

from app.config import settings
from app.services.retriever import Retriever
from app.services.text_chunker import chunk_pages, classify_chunk
from app.services.vector_store import VectorStore
from tests import legacy_chunker
from tests.fakes import FIXTURES, FakeEmbedder, load_fixture_pages

QUERIES = ["What is Retrieval-Augmented Generation? Explain how it works and why it is useful.",
           "Explain the relationship between AI, ML, and DL.",
           "What are the three components of the CIA triad?",
           "What is the difference between precision and recall?",
           "How does reinforcement learning work?",
           "What is the capital of Japan?"]
SHORT = {"ai": "AI-Basics", "cyber": "Cyber", "ml": "ML-Basics"}


def build(version, emb):
    store = VectorStore(Path(tempfile.mkdtemp()))
    for key, name in FIXTURES.items():
        pages = load_fixture_pages(name)
        if version == "old":
            items = [(c, p.page_number, None) for p in pages for c in legacy_chunker.chunk_text(p.text, 500, 100)]
            meta = [{"chunk_id": f"{key}-{i}", "document_id": key, "document_name": name, "chunk_index": i,
                     "page_number": pg, "section": None, "content": c} for i, (c, pg, _) in enumerate(items)]
        else:
            size, ov = settings.effective_chunking()
            chunks = chunk_pages(pages, key, size, ov, emb.count_tokens, emb.max_seq_length - 2)
            meta = [{"chunk_id": c.chunk_id, "document_id": key, "document_name": name, "chunk_index": c.chunk_index,
                     "page_number": c.page_number, "section": c.section, "kind": c.kind, "content": c.content}
                    for c in chunks]
        store.add(emb.embed_texts([m["content"] for m in meta]), meta)
    return store


def describe(hit):
    kind = hit.get("kind") or classify_chunk(None, hit["content"])
    first = " ".join(hit["content"].split()[:6])
    return (f"{SHORT[hit['document_id']]:9} p{hit['page_number']} #{hit['chunk_index']} "
            f"cos={hit['score']:.3f} [{'QUESTIONS' if kind == 'questions' or 'Suggested Test Questions' in hit['content'][:40] else 'content'}] "
            f"{first}...")


def main():
    emb = FakeEmbedder(max_words=190)
    old, new = build("old", emb), build("new", emb)
    retriever = Retriever(new, emb)
    for q in QUERIES:
        print(f"\nQ: {q}")
        print("  BEFORE (v1):")
        hits = old.search(emb.embed_query(q), top_k=3, threshold=settings.SIMILARITY_THRESHOLD)
        for h in hits or [None]:
            print("    ", describe(h) if h else "(nothing above threshold)")
        print("  AFTER  (v2):")
        res = [r for r in retriever.retrieve(q, top_k=3)]
        for r in res or [None]:
            print("    ", describe(r) if r else "(nothing above threshold)")


if __name__ == "__main__":
    main()
