"""See exactly what is indexed and how a query is scored, using the REAL model and your real data.

    python -m scripts.diagnose_retrieval "What is Retrieval-Augmented Generation?"
    python -m scripts.diagnose_retrieval --chunks            # only list indexed chunks

Prints (1) every indexed chunk: page, section, kind, words, model tokens and whether the model would
TRUNCATE it, and (2) the full candidate table for the query (cosine, rerank, kept/dropped, text).
"""
import argparse
import logging
import sys

from app.config import settings
from app.dependencies import retriever, vector_store
from app.services.embedding_engine import embedding_engine


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="?")
    ap.add_argument("--chunks", action="store_true", help="only list chunks")
    ap.add_argument("--top-k", type=int, default=None)
    args = ap.parse_args()

    meta = vector_store.metadata
    limit = embedding_engine.max_seq_length
    print(f"Model: {embedding_engine.model_name} | max_seq_length={limit} | index vectors={len(meta)} "
          f"| manifest={vector_store.manifest}")
    tokens = embedding_engine.count_tokens([m["content"] for m in meta]) if meta else []
    truncated = 0
    print(f"\n{'doc':34} {'page':>4} {'idx':>3} {'kind':9} {'words':>5} {'tokens':>6}  section")
    for m, t in zip(meta, tokens):
        flag = "  <-- TRUNCATED by the model" if t > limit else ""
        truncated += t > limit
        print(f"{m['document_name'][:34]:34} {str(m.get('page_number')):>4} {m['chunk_index']:>3} "
              f"{m.get('kind', '(old)'):9} {len(m['content'].split()):>5} {t:>6}  {m.get('section') or '-'}{flag}")
    print(f"\n{truncated} of {len(meta)} chunks exceed the model window "
          f"({'re-run scripts.reindex --all' if truncated or any('kind' not in m for m in meta) else 'OK'}).")

    if args.chunks or not args.query:
        return
    settings.LOG_TEXT_CHARS = 0  # full text of every candidate
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
    print()
    retriever.retrieve(args.query, top_k=args.top_k)


if __name__ == "__main__":
    main()
