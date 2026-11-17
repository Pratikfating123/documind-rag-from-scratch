"""Central configuration. Values come from environment / .env; no secrets are hardcoded."""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    def __init__(self):
        self.GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
        self.GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'rag_database.db'}")
        self.EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        self.CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 150))
        self.CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 30))
        self.TOP_K = int(os.getenv("TOP_K", 5))
        self.SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", 0.25))
        self.MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", 20))
        # all-MiniLM-L6-v2 silently truncates input at 256 word-pieces (~170 English words).
        # Chunks larger than this are only partly embedded, so chunk size is capped to it.
        self.EMBED_MAX_WORDS = int(os.getenv("EMBED_MAX_WORDS", 150))
        self.CANDIDATE_K = int(os.getenv("CANDIDATE_K", 10))      # candidates fetched before re-ranking
        self.LOG_TEXT_CHARS = int(os.getenv("LOG_TEXT_CHARS", 300))  # retrieved-text chars in logs (0 = full text)
        self.CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")]
        self.UPLOAD_DIR = BASE_DIR / "storage" / "uploads"
        self.VECTOR_DIR = BASE_DIR / "storage" / "vectors"
        self.ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
        self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        self.VECTOR_DIR.mkdir(parents=True, exist_ok=True)

    def effective_chunking(self) -> tuple[int, int]:
        """(chunk_size, overlap) actually used: the configured values capped to the embedding model's window."""
        size = max(20, min(self.CHUNK_SIZE, self.EMBED_MAX_WORDS))
        overlap = max(0, min(self.CHUNK_OVERLAP, size // 3))
        return size, overlap

    def public_dict(self) -> dict:
        """Safe view for the frontend: never includes the API key."""
        return {
            "embedding_model": self.EMBEDDING_MODEL,
            "llm_provider": "Groq",
            "llm_model": self.GROQ_MODEL,
            "groq_configured": bool(self.GROQ_API_KEY),
            "chunk_size": self.CHUNK_SIZE,
            "chunk_overlap": self.CHUNK_OVERLAP,
            "effective_chunk_size": self.effective_chunking()[0],
            "effective_chunk_overlap": self.effective_chunking()[1],
            "top_k": self.TOP_K,
            "similarity_threshold": self.SIMILARITY_THRESHOLD,
            "max_file_size_mb": self.MAX_FILE_SIZE_MB,
        }


settings = Settings()
