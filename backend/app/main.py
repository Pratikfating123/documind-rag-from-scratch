"""FastAPI entry point.  Run:  uvicorn app.main:app --reload"""
import logging
import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.database import SessionLocal, init_db
from app.dependencies import embedding_engine
from app.models.document import Document
from app.routes import chat, dashboard, documents, retrieval
from app.routes import settings as settings_routes
from app.services.embedding_engine import EmbeddingError, EmptyTextError
from app.services.vector_store import IndexMismatchError
from app.services.llm_service import LLMError, LLMNotConfiguredError, LLMRateLimitError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("rag")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    settings_routes.load_runtime_overrides()
    with SessionLocal() as db:  # documents left "processing" by a crash/restart can never finish
        stale = db.query(Document).filter(Document.processing_status == "processing").all()
        for d in stale:
            d.processing_status, d.error_message = "failed", "Processing was interrupted. Click Reprocess."
        db.commit()
    if not os.getenv("RAG_SKIP_WARMUP"):  # load the model once, in the background
        threading.Thread(target=lambda: _warm(), daemon=True).start()
    yield


def _warm():
    try:
        embedding_engine.dimension
    except Exception as e:  # noqa: BLE001
        logger.error("Embedding model warm-up failed: %s", e)


app = FastAPI(title="RAG from Scratch API", version="1.0.0", lifespan=lifespan,
              description="Document question answering with a hand-built RAG pipeline.")
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


def _err(status: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": status, "message": message}})


@app.exception_handler(StarletteHTTPException)
async def http_error(_: Request, exc: StarletteHTTPException):
    return _err(exc.status_code, str(exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    first = exc.errors()[0]
    field = ".".join(str(p) for p in first["loc"] if p != "body")
    return _err(422, f"Invalid input{' for ' + field if field else ''}: {first['msg']}")


@app.exception_handler(LLMNotConfiguredError)
async def llm_not_configured(_: Request, exc: LLMNotConfiguredError):
    return _err(503, str(exc))


@app.exception_handler(LLMRateLimitError)
async def llm_rate_limit(_: Request, exc: LLMRateLimitError):
    return _err(429, str(exc))


@app.exception_handler(LLMError)
async def llm_error(_: Request, exc: LLMError):
    return _err(502, str(exc))


@app.exception_handler(EmbeddingError)
async def embedding_error(_: Request, exc: EmbeddingError):
    return _err(503, str(exc))


@app.exception_handler(EmptyTextError)
async def empty_text(_: Request, exc: EmptyTextError):
    return _err(422, str(exc))


@app.exception_handler(IndexMismatchError)
async def index_mismatch(_: Request, exc: IndexMismatchError):
    return _err(409, str(exc))


@app.exception_handler(Exception)
async def unexpected(_: Request, exc: Exception):
    logger.exception("Unhandled error")
    return _err(500, "Something went wrong on the server. Check the backend logs.")


for r in (documents.router, chat.router, retrieval.router, dashboard.router, settings_routes.router):
    app.include_router(r)
