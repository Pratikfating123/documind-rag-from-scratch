"""Test setup: temp database/storage, a fake embedder (no model download) and a fake LLM (no API key)."""
import os
import tempfile

import pytest

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["GROQ_API_KEY"] = ""
os.environ["RAG_SKIP_WARMUP"] = "1"


@pytest.fixture()
def fake_embedder():
    from tests.fakes import FakeEmbedder
    return FakeEmbedder()


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """Fresh DB tables, vector store and upload dir for every test."""
    from app.config import settings
    from app.database import Base, engine, init_db
    from app.dependencies import pipeline, retriever
    from app.services.vector_store import VectorStore

    Base.metadata.drop_all(bind=engine)
    init_db()
    store = VectorStore(tmp_path / "vectors")
    from tests.fakes import make_embedder
    emb = make_embedder()
    for obj in (pipeline, retriever):
        monkeypatch.setattr(obj, "embedder", emb)
        monkeypatch.setattr(obj, "store", store)
    monkeypatch.setattr("app.routes.dashboard.vector_store", store)
    monkeypatch.setattr("app.routes.settings.vector_store", store)
    monkeypatch.setattr(pipeline.llm, "generate",
                        lambda question, sources, history=None: f"Fake answer based on {sources[0]['label']}.")
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    monkeypatch.setattr(settings, "UPLOAD_DIR", upload_dir)
    monkeypatch.setattr(settings, "SIMILARITY_THRESHOLD", 0.25)
    return store


@pytest.fixture()
def client(env):
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)  # not used as a context manager -> lifespan (warm-up) is skipped
