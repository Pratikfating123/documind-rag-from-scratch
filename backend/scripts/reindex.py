"""Safely re-process stored documents with the current chunker/embedder.

    python -m scripts.reindex --dry-run        # show what would change
    python -m scripts.reindex                  # reprocess documents indexed with an OLD chunker version
    python -m scripts.reindex --all            # reprocess everything (e.g. after changing EMBEDDING_MODEL)
    python -m scripts.reindex --document <id>  # one document

Uploaded files are never deleted. Before changing anything, the vector store and the SQLite file are
copied to storage/backups/<timestamp>/. Each document's vectors are swapped atomically, and if
re-processing a document fails its previous chunks and vectors are kept.
"""
import argparse
import shutil
import time
from pathlib import Path

from app.config import settings
from app.database import SessionLocal, engine, init_db
from app.dependencies import pipeline, vector_store
from app.models.document import Document
from app.services.text_chunker import CHUNKER_VERSION


def backup() -> Path:
    dest = settings.VECTOR_DIR.parent / "backups" / time.strftime("%Y%m%d-%H%M%S")
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copytree(settings.VECTOR_DIR, dest / "vectors", dirs_exist_ok=True)
    if engine.url.drivername.startswith("sqlite") and engine.url.database:
        db_file = Path(engine.url.database)
        if db_file.exists():
            shutil.copy2(db_file, dest / db_file.name)
    return dest


def outdated_doc_ids() -> set[str]:
    versions: dict[str, set] = {}
    for m in vector_store.metadata:
        versions.setdefault(m["document_id"], set()).add(m.get("chunker_version", "1"))
    return {d for d, v in versions.items() if v != {CHUNKER_VERSION}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--document")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    init_db()
    stale = outdated_doc_ids()
    with SessionLocal() as db:
        docs = db.query(Document).all()
        todo = [d for d in docs if (args.document == d.id if args.document else (args.all or d.id in stale
                or d.processing_status == "failed"))]
        print(f"Chunker version {CHUNKER_VERSION}. {len(docs)} documents, {len(todo)} to reprocess.")
        for d in todo:
            exists = Path(d.storage_path).exists()
            print(f" - {d.filename} [{d.processing_status}, {d.total_chunks} chunks]{'' if exists else '  (FILE MISSING, skipped)'}")
        if args.dry_run or not todo:
            return
        print("Backup written to", backup())
        for d in todo:
            if not Path(d.storage_path).exists():
                continue
            pipeline.ingest_document(db, d)
            db.refresh(d)
            print(f"   {d.filename}: {d.processing_status}, {d.total_chunks} chunks" + (f"  NOTE: {d.error_message}" if d.error_message else ""))
    print("Done. Vectors indexed:", vector_store.count())


if __name__ == "__main__":
    main()
