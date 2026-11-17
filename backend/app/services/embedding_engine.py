"""Stage 4: Sentence-Transformers embeddings. Model is loaded once and cached in memory.

Documents and queries MUST go through this same engine so they share one model, one
dimension and the same L2 normalisation.
"""
import logging
import threading
import numpy as np
from app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingError(RuntimeError):
    pass


class EmptyTextError(ValueError):
    """Raised instead of silently embedding an empty string (which yields a meaningless vector)."""


class EmbeddingEngine:
    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.EMBEDDING_MODEL
        self._model = None
        self._lock = threading.Lock()

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def _load(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    try:
                        from sentence_transformers import SentenceTransformer
                        logger.info("Loading embedding model %s", self.model_name)
                        self._model = SentenceTransformer(self.model_name)
                        logger.info("Embedding model ready: dim=%s, max_seq_length=%s",
                                    self._model.get_sentence_embedding_dimension(), self._model.max_seq_length)
                    except Exception as e:
                        raise EmbeddingError(f"Could not load embedding model '{self.model_name}': {e}")
        return self._model

    @property
    def dimension(self) -> int:
        return int(self._load().get_sentence_embedding_dimension())

    @property
    def max_seq_length(self) -> int:
        """Longest input (in word-pieces) the model embeds; anything beyond is silently dropped."""
        return int(self._load().max_seq_length or 256)

    def count_tokens(self, texts: list[str]) -> list[int]:
        """Number of word-pieces per text, including special tokens (what max_seq_length is compared to)."""
        tok = self._load().tokenizer
        ids = tok(texts, add_special_tokens=True, truncation=False)["input_ids"]
        return [len(i) for i in ids]

    def embed_texts(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        """Returns an (N, dim) float32 array of L2-normalised vectors."""
        if not texts:
            return np.zeros((0, self.dimension), dtype=np.float32)
        if any(not t or not t.strip() for t in texts):
            raise EmptyTextError("Cannot embed empty text.")
        vecs = self._load().encode(texts, batch_size=batch_size, normalize_embeddings=True,
                                   convert_to_numpy=True, show_progress_bar=False)
        return vecs.astype(np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        text = (text or "").strip()
        if not text:
            raise EmptyTextError("The question is empty.")
        return self.embed_texts([text])[0]


embedding_engine = EmbeddingEngine()
