from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import pipeline, vector_store
from app.models.conversation import Message
from app.models.document import Document
from app.utils.helpers import utcnow

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


def _dir_size(path) -> int:
    return sum(f.stat().st_size for f in path.glob("*") if f.is_file())


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    total = db.query(func.count(Document.id)).scalar() or 0
    processed = db.query(func.count(Document.id)).filter(Document.processing_status == "processed").scalar() or 0
    chunks = db.query(func.coalesce(func.sum(Document.total_chunks), 0)).scalar() or 0
    questions = db.query(func.count(Message.id)).filter(Message.role == "user").scalar() or 0
    upload_bytes, vector_bytes = _dir_size(settings.UPLOAD_DIR), vector_store.size_bytes()
    if not pipeline.llm.is_configured:
        state = "needs_api_key"
    elif processed == 0:
        state = "no_documents"
    else:
        state = "ready"
    return {
        "total_documents": total, "processed_documents": processed, "total_chunks": int(chunks),
        "total_questions": questions,
        "storage": {"uploads_bytes": upload_bytes, "vectors_bytes": vector_bytes,
                    "total_bytes": upload_bytes + vector_bytes},
        "pipeline": {"state": state, "embedding_model_loaded": pipeline.embedder.is_loaded,
                     "vectors_indexed": vector_store.count(), "llm_configured": pipeline.llm.is_configured},
    }


@router.get("/activity")
def activity(days: int = 14, db: Session = Depends(get_db)):
    days = max(1, min(days, 90))
    today = utcnow().date()
    since = today - timedelta(days=days - 1)
    day_list = [(since + timedelta(days=i)).isoformat() for i in range(days)]

    up = dict(db.query(func.date(Document.upload_date), func.count()).filter(Document.upload_date >= since)
              .group_by(func.date(Document.upload_date)).all())
    qs = dict(db.query(func.date(Message.created_at), func.count())
              .filter(Message.role == "user", Message.created_at >= since)
              .group_by(func.date(Message.created_at)).all())
    status_counts = dict(db.query(Document.processing_status, func.count()).group_by(Document.processing_status).all())

    recent = [{"type": "upload", "title": d.filename, "status": d.processing_status, "time": d.upload_date}
              for d in db.query(Document).order_by(Document.upload_date.desc()).limit(6)]
    recent += [{"type": "question", "title": m.content[:80], "status": None, "time": m.created_at}
               for m in db.query(Message).filter(Message.role == "user").order_by(Message.created_at.desc()).limit(6)]
    recent.sort(key=lambda r: r["time"], reverse=True)

    return {
        "uploads_per_day": [{"date": d, "count": up.get(d, 0)} for d in day_list],
        "questions_per_day": [{"date": d, "count": qs.get(d, 0)} for d in day_list],
        "processing_stats": [{"status": s, "count": status_counts.get(s, 0)}
                             for s in ("uploaded", "processing", "processed", "failed")],
        "recent_activity": recent[:8],
    }
