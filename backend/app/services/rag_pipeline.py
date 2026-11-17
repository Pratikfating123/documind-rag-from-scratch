"""Stage 9: the complete RAG workflow in one readable place.

INGEST : file -> extract text -> chunk -> embed -> save chunks (SQLite) + vectors (NumPy store)
ASK    : question -> embed -> vector search -> build context -> Groq LLM -> answer + citations -> save chat
"""
import json
import logging
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models.chunk import Chunk
from app.models.conversation import Conversation, Message
from app.models.document import Document
from app.services.document_processor import ExtractionError, extract_document
from app.services.embedding_engine import EmbeddingError, EmptyTextError
from app.services.text_chunker import CHUNKER_VERSION, chunk_pages
from app.services.vector_store import IndexMismatchError
from app.utils.helpers import utcnow

logger = logging.getLogger(__name__)

NO_ANSWER = ("The uploaded documents do not contain enough information to answer this question. "
             "Try rephrasing it, selecting different documents, or uploading a relevant document.")


def _drop_duplicate_chunks(chunks):
    """Identical chunk text is embedded only once (repeated headers/footers, copy-pasted paragraphs)."""
    seen, out = set(), []
    for c in chunks:
        key = " ".join(c.content.lower().split())
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    for i, c in enumerate(out):
        c.chunk_index = i
    return out


class ConversationNotFoundError(LookupError):
    pass


class RAGPipeline:
    def __init__(self, retriever, embedder, store, llm):
        self.retriever, self.embedder, self.store, self.llm = retriever, embedder, store, llm

    # ------------------------------------------------------------------ ingest
    def ingest_document(self, db: Session, document: Document) -> None:
        had_previous = (document.total_chunks or 0) > 0
        document.processing_status, document.error_message = "processing", None
        db.commit()
        try:
            pages = extract_document(Path(document.storage_path))
            size, overlap = settings.effective_chunking()
            if settings.CHUNK_SIZE > size:
                logger.warning("CHUNK_SIZE=%d exceeds the embedding window; using %d words instead.",
                               settings.CHUNK_SIZE, size)
            count_tokens = getattr(self.embedder, "count_tokens", None)
            max_len = getattr(self.embedder, "max_seq_length", None)
            chunks = chunk_pages(pages, document.id, size, overlap, count_tokens,
                                 (max_len - 2) if max_len else None)
            chunks = _drop_duplicate_chunks(chunks)
            if not chunks:
                raise ExtractionError("The document produced no text chunks.")
            vectors = self.embedder.embed_texts([c.content for c in chunks])
            if len(vectors) != len(chunks):
                raise RuntimeError("Embedding count does not match chunk count.")

            # DB first (flush only), then ONE atomic vector swap, then commit: old data survives any failure.
            db.query(Chunk).filter(Chunk.document_id == document.id).delete()
            db.add_all([Chunk(id=c.chunk_id, document_id=document.id, chunk_index=c.chunk_index,
                              content=c.content, page_number=c.page_number, section=c.section,
                              embedding_reference=c.chunk_id) for c in chunks])
            db.flush()
            self.store.replace_document(document.id, vectors, [{
                "chunk_id": c.chunk_id, "document_id": document.id, "document_name": document.filename,
                "chunk_index": c.chunk_index, "page_number": c.page_number, "section": c.section,
                "kind": c.kind, "chunker_version": CHUNKER_VERSION, "content": c.content} for c in chunks])
            document.total_chunks, document.processing_status = len(chunks), "processed"
            db.commit()
            kinds = {k: sum(c.kind == k for c in chunks) for k in ("content", "questions")}
            logger.info("Processed %s: %d chunks (avg %.0f words, %s), vector dim %d",
                        document.filename, len(chunks), sum(len(c.content.split()) for c in chunks) / len(chunks),
                        kinds, vectors.shape[1])
        except Exception as e:  # noqa: BLE001
            db.rollback()
            known = isinstance(e, (ExtractionError, EmbeddingError, IndexMismatchError, EmptyTextError))
            if not known:
                logger.exception("Unexpected processing error")
            msg = str(e) if known else "Unexpected error while processing this file."
            if had_previous:  # keep the previous, still-valid index
                document.processing_status = "processed"
                document.error_message = f"Reprocessing failed ({msg}). The previous index was kept."
            else:
                self.store.delete_document(document.id)
                document.processing_status, document.total_chunks, document.error_message = "failed", 0, msg
            db.commit()

    # --------------------------------------------------------------------- ask
    def ask(self, db: Session, question: str, conversation_id: Optional[str] = None,
            document_ids: Optional[list[str]] = None, top_k: Optional[int] = None) -> dict:
        conv = None
        history: list[dict] = []
        if conversation_id:
            conv = db.get(Conversation, conversation_id)
            if conv is None:
                raise ConversationNotFoundError("Conversation not found.")
            history = [{"role": m.role, "content": m.content} for m in conv.messages]

        sources = self.retriever.retrieve(question, top_k=top_k, document_ids=document_ids or None)
        # Lists of test questions / testing notes are never sent to the LLM as evidence.
        usable = [s for s in sources if s.get("kind", "content") == "content"]
        answer = self.llm.generate(question, usable, history) if usable else NO_ANSWER
        public_sources = [{k: v for k, v in s.items() if k != "context"} for s in sources]

        # Only persist once the whole pipeline succeeded.
        if conv is None:
            conv = Conversation(title=question.strip()[:60])
            db.add(conv)
            db.flush()
        db.add(Message(conversation_id=conv.id, role="user", content=question))
        db.add(Message(conversation_id=conv.id, role="assistant", content=answer,
                       sources_json=json.dumps(public_sources)))
        conv.updated_at = utcnow()
        db.commit()
        return {"conversation_id": conv.id, "answer": answer, "has_answer": bool(usable),
                "sources": public_sources}

    # ----------------------------------------------------------------- cleanup
    def delete_document_data(self, document_id: str) -> None:
        self.store.delete_document(document_id)
