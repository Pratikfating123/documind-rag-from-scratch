"""Settings + health. Only safe, validated values are changeable; the API key never leaves the server."""
import json
import logging

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.config import settings
from app.database import SessionLocal
from app.dependencies import pipeline, vector_store
from app.schemas import SettingsUpdate

router = APIRouter(prefix="/api", tags=["Settings"])
logger = logging.getLogger(__name__)
OVERRIDES_FILE = settings.VECTOR_DIR.parent / "runtime_settings.json"


def load_runtime_overrides() -> None:
    if OVERRIDES_FILE.exists():
        try:
            data = json.loads(OVERRIDES_FILE.read_text(encoding="utf-8"))
            settings.CHUNK_SIZE = int(data.get("chunk_size", settings.CHUNK_SIZE))
            settings.CHUNK_OVERLAP = int(data.get("chunk_overlap", settings.CHUNK_OVERLAP))
            settings.TOP_K = int(data.get("top_k", settings.TOP_K))
            settings.SIMILARITY_THRESHOLD = float(data.get("similarity_threshold", settings.SIMILARITY_THRESHOLD))
            settings.GROQ_MODEL = data.get("llm_model", settings.GROQ_MODEL)
        except Exception:  # noqa: BLE001
            logger.warning("Ignoring unreadable runtime_settings.json")


@router.get("/settings")
def get_settings():
    return settings.public_dict()


@router.put("/settings")
def update_settings(body: SettingsUpdate):
    new_size = body.chunk_size or settings.CHUNK_SIZE
    new_overlap = settings.CHUNK_OVERLAP if body.chunk_overlap is None else body.chunk_overlap
    if new_overlap >= new_size:
        raise HTTPException(422, "Chunk overlap must be smaller than chunk size.")
    settings.CHUNK_SIZE, settings.CHUNK_OVERLAP = new_size, new_overlap
    if body.top_k is not None:
        settings.TOP_K = body.top_k
    if body.similarity_threshold is not None:
        settings.SIMILARITY_THRESHOLD = body.similarity_threshold
    if body.llm_model:
        settings.GROQ_MODEL = body.llm_model.strip()
    pub = settings.public_dict()
    OVERRIDES_FILE.write_text(json.dumps({k: pub[k] for k in
                              ("chunk_size", "chunk_overlap", "top_k", "similarity_threshold", "llm_model")}),
                              encoding="utf-8")
    return {**pub, "note": "Chunk settings apply to documents processed from now on. Reprocess existing documents to use them."}


@router.get("/health")
def health(test_llm: bool = False):
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:  # noqa: BLE001
        db_ok = False
    result = {
        "status": "ok" if db_ok else "degraded", "database": "ok" if db_ok else "error",
        "embedding_model_loaded": pipeline.embedder.is_loaded, "vectors_indexed": vector_store.count(),
        "groq_configured": pipeline.llm.is_configured,
    }
    if test_llm:
        ok, msg = pipeline.llm.check_connection()
        result["groq_connection"] = {"ok": ok, "message": msg}
    return result
