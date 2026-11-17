"""Retrieval Explorer API: shows each step of retrieval without calling the LLM."""
import numpy as np
from fastapi import APIRouter

from app.config import settings
from app.dependencies import retriever
from app.schemas import RetrievalRequest

router = APIRouter(prefix="/api/retrieval", tags=["Retrieval"])


@router.post("/search")
def search(req: RetrievalRequest):
    top_k = req.top_k or settings.TOP_K
    threshold = settings.SIMILARITY_THRESHOLD if req.threshold is None else req.threshold
    effective = 0.0 if req.include_below_threshold else threshold
    qvec = retriever.embedder.embed_query(retriever.expand_query(req.query.strip()))
    hits = retriever.retrieve(req.query, top_k=top_k, threshold=effective, document_ids=req.document_ids or None)
    results = [{**h, "passes_threshold": h["score"] >= threshold,
                "explanation": retriever.explain(req.query, h, threshold)} for h in hits]
    return {
        "query": req.query,
        "expanded_query": retriever.expand_query(req.query.strip()),
        "query_embedding": {
            "model": retriever.embedder.model_name,
            "dimension": int(len(qvec)),
            "l2_norm": round(float(np.linalg.norm(qvec)), 4),
            "preview": [round(float(x), 4) for x in qvec[:8]],
        },
        "top_k": top_k, "threshold": threshold, "total_vectors": retriever.store.count(),
        "results": results,
    }
