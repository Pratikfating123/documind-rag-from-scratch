"""Test doubles. FakeEmbedder = hashed bag-of-words vectors (NOT a semantic model: it only shows that
shared words give high cosine). `max_words` simulates MiniLM's silent truncation of long inputs."""
import os
import re
import zlib
from pathlib import Path

import numpy as np

from app.services.document_processor import ExtractedPage
from app.services.embedding_engine import EmptyTextError

DATA = Path(__file__).parent / "data"
_FAKE_STOP = {"the", "and", "for", "are", "was", "with", "that", "this", "from", "what", "how", "why", "which",
              "does", "can", "you", "your", "about", "into", "has", "have", "its", "not", "but", "who", "when",
              "then", "than", "there", "their", "they", "such", "each", "also", "may", "any", "use", "used"}


class FakeEmbedder:
    model_name = "fake-embedder"
    is_loaded = True
    dimension = 1024
    max_seq_length = 256

    def __init__(self, max_words=None):
        self.max_words = max_words

    def count_tokens(self, texts):
        return [int(len(t.split()) * 1.4) + 2 for t in texts]

    def embed_texts(self, texts, batch_size=32):
        if any(not t or not t.strip() for t in texts):
            raise EmptyTextError("Cannot embed empty text.")
        out = np.zeros((len(texts), self.dimension), dtype=np.float32)
        for i, t in enumerate(texts):
            words = re.findall(r"[a-z0-9]+", t.lower())
            if self.max_words:
                words = words[: self.max_words]
            for w in words:
                if len(w) > 2 and w not in _FAKE_STOP:
                    out[i, zlib.crc32(w.encode()) % self.dimension] += 1
            n = np.linalg.norm(out[i])
            if n:
                out[i] /= n
        return out

    def embed_query(self, text):
        text = (text or "").strip()
        if not text:
            raise EmptyTextError("The question is empty.")
        return self.embed_texts([text])[0]


def make_embedder():
    """Fake by default; set RAG_TEST_REAL_MODEL=1 to run the same tests with the real MiniLM model."""
    if os.getenv("RAG_TEST_REAL_MODEL") == "1":
        from app.services.embedding_engine import EmbeddingEngine
        return EmbeddingEngine()
    return FakeEmbedder()


def load_fixture_pages(name: str) -> list[ExtractedPage]:
    text = (DATA / f"{name}.txt").read_text(encoding="utf-8")
    return [ExtractedPage(text=p, page_number=i) for i, p in enumerate(text.split("\f"), start=1)]


FIXTURES = {
    "ai": "RAG_Test_Artificial_Intelligence_Basics",
    "cyber": "RAG_Test_Cybersecurity_Fundamentals",
    "ml": "RAG_Test_Machine_Learning_Basics",
}
