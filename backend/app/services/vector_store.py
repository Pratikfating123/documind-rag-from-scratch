"""Stages 5 & 6: a tiny NumPy vector store with manual cosine similarity.

Persistence:  embeddings.npy  (N x dim matrix)   metadata.json (N dicts, same row order)
              manifest.json   (embedding model + dimension the index was built with)
Writes are atomic (temp file + rename).
"""
import json
import os
import threading
from pathlib import Path
from typing import Iterable, Optional

import numpy as np


class IndexMismatchError(RuntimeError):
    """The stored vectors were built with a different embedding model/dimension than the query."""


def cosine_similarity(query: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """similarity(A, B) = dot(A, B) / (norm(A) * norm(B)), computed for every row of `matrix`."""
    if matrix.shape[0] == 0:
        return np.zeros(0, dtype=np.float32)
    dots = matrix @ query
    denom = np.linalg.norm(matrix, axis=1) * np.linalg.norm(query)
    denom = np.where(denom == 0, 1e-12, denom)
    return dots / denom


def _normalise(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return (vectors / np.where(norms == 0, 1.0, norms)).astype(np.float32)


class VectorStore:
    def __init__(self, directory: Path, model_name: Optional[str] = None):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.vec_path = self.dir / "embeddings.npy"
        self.meta_path = self.dir / "metadata.json"
        self.manifest_path = self.dir / "manifest.json"
        self.model_name = model_name  # None disables the model check (used by tests)
        self._lock = threading.RLock()
        self.vectors = np.zeros((0, 0), dtype=np.float32)
        self.metadata: list[dict] = []
        self.manifest: dict = {}
        self.load()

    # ---- persistence ----
    def load(self):
        with self._lock:
            self.vectors, self.metadata, self.manifest = np.zeros((0, 0), dtype=np.float32), [], {}
            if self.vec_path.exists() and self.meta_path.exists():
                vectors = np.load(self.vec_path)
                metadata = json.loads(self.meta_path.read_text(encoding="utf-8"))
                if len(metadata) == vectors.shape[0]:
                    self.vectors, self.metadata = vectors, metadata
            if self.manifest_path.exists():
                self.manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            elif self.metadata and self.model_name:  # index created before manifests existed
                self.manifest = {"embedding_model": self.model_name, "dimension": int(self.vectors.shape[1])}

    def _write(self, vectors: np.ndarray, metadata: list[dict], manifest: dict):
        tmp_v, tmp_m, tmp_f = (self.dir / n for n in ("embeddings.tmp.npy", "metadata.tmp.json", "manifest.tmp.json"))
        np.save(tmp_v, vectors)
        tmp_m.write_text(json.dumps(metadata), encoding="utf-8")
        tmp_f.write_text(json.dumps(manifest), encoding="utf-8")
        os.replace(tmp_v, self.vec_path)
        os.replace(tmp_m, self.meta_path)
        os.replace(tmp_f, self.manifest_path)

    def save(self):
        with self._lock:
            self._write(self.vectors, self.metadata, self.manifest)

    # ---- consistency checks ----
    def _check_add(self, vectors: np.ndarray):
        if self.metadata and vectors.shape[1] != self.vectors.shape[1]:
            raise IndexMismatchError(
                f"New vectors have dimension {vectors.shape[1]} but the index has {self.vectors.shape[1]}. "
                "Reprocess all documents after changing the embedding model.")
        known = self.manifest.get("embedding_model")
        if self.metadata and self.model_name and known and known != self.model_name:
            raise IndexMismatchError(
                f"The index was built with '{known}' but the current model is '{self.model_name}'. "
                "Reprocess all documents (scripts/reindex.py --all).")

    def _check_query(self, query_vec: np.ndarray):
        if self.metadata and len(query_vec) != self.vectors.shape[1]:
            raise IndexMismatchError(
                f"The question embedding has {len(query_vec)} dimensions but the index has {self.vectors.shape[1]}. "
                "Reprocess all documents so they use the current embedding model.")
        known = self.manifest.get("embedding_model")
        if self.metadata and self.model_name and known and known != self.model_name:
            raise IndexMismatchError(
                f"The index was built with '{known}' but the current model is '{self.model_name}'. "
                "Reprocess all documents (scripts/reindex.py --all).")

    def _manifest_for(self, vectors: np.ndarray) -> dict:
        m = dict(self.manifest)
        if self.model_name:
            m["embedding_model"] = self.model_name
        m["dimension"] = int(vectors.shape[1]) if vectors.shape[0] else None
        return m

    # ---- mutation ----
    def add(self, vectors: np.ndarray, metadata: list[dict]):
        if len(vectors) != len(metadata):
            raise ValueError("vectors and metadata must have the same length")
        if len(vectors) == 0:
            return
        with self._lock:
            vectors = _normalise(np.asarray(vectors, dtype=np.float32))
            self._check_add(vectors)
            new_v = vectors if self.vectors.shape[0] == 0 else np.vstack([self.vectors, vectors])
            new_m = self.metadata + list(metadata)
            manifest = self._manifest_for(new_v)
            self._write(new_v, new_m, manifest)  # write first, then update memory
            self.vectors, self.metadata, self.manifest = new_v, new_m, manifest

    def replace_document(self, document_id: str, vectors: np.ndarray, metadata: list[dict]):
        """Swap a document's vectors in ONE atomic write: the old vectors stay intact if this fails."""
        if len(vectors) != len(metadata):
            raise ValueError("vectors and metadata must have the same length")
        with self._lock:
            keep = [i for i, m in enumerate(self.metadata) if m.get("document_id") != document_id]
            base_v = self.vectors[keep] if keep else np.zeros((0, 0), dtype=np.float32)
            base_m = [self.metadata[i] for i in keep]
            new = _normalise(np.asarray(vectors, dtype=np.float32)) if len(vectors) else None
            if new is not None and base_m and new.shape[1] != base_v.shape[1]:
                raise IndexMismatchError("Dimension mismatch with the existing index. Reindex all documents.")
            new_v = base_v if new is None else (new if base_v.shape[0] == 0 else np.vstack([base_v, new]))
            new_m = base_m + list(metadata)
            manifest = self._manifest_for(new_v) if new_m else {}
            self._write(new_v, new_m, manifest)
            self.vectors, self.metadata, self.manifest = new_v, new_m, manifest

    def delete_document(self, document_id: str) -> int:
        with self._lock:
            keep = [i for i, m in enumerate(self.metadata) if m.get("document_id") != document_id]
            removed = len(self.metadata) - len(keep)
            if removed:
                new_v = self.vectors[keep] if keep else np.zeros((0, 0), dtype=np.float32)
                new_m = [self.metadata[i] for i in keep]
                manifest = self._manifest_for(new_v) if new_m else {}
                self._write(new_v, new_m, manifest)
                self.vectors, self.metadata, self.manifest = new_v, new_m, manifest
            return removed

    # ---- query ----
    def search(self, query_vec: np.ndarray, top_k: int = 5, threshold: float = 0.0,
               document_ids: Optional[Iterable[str]] = None) -> list[dict]:
        with self._lock:
            if self.vectors.shape[0] == 0:
                return []
            query_vec = np.asarray(query_vec, dtype=np.float32)
            self._check_query(query_vec)
            scores = cosine_similarity(query_vec, self.vectors)
            allowed = set(document_ids) if document_ids else None
            order = np.argsort(-scores)
            results = []
            for i in order:
                if scores[i] < threshold:
                    break  # sorted descending: everything after is lower
                if allowed is not None and self.metadata[i].get("document_id") not in allowed:
                    continue
                results.append({**self.metadata[i], "score": float(scores[i])})
                if len(results) >= top_k:
                    break
            return results

    def count(self) -> int:
        return len(self.metadata)

    def size_bytes(self) -> int:
        return sum(p.stat().st_size for p in (self.vec_path, self.meta_path) if p.exists())
