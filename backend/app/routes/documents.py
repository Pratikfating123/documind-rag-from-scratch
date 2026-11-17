import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal, get_db
from app.dependencies import pipeline
from app.models.document import Document
from app.schemas import DocumentOut
from app.utils.file_validator import FileValidationError, resolve_inside, validate_upload
from app.utils.helpers import new_id, sha256_bytes

router = APIRouter(prefix="/api/documents", tags=["Documents"])
logger = logging.getLogger(__name__)


def process_document_task(document_id: str) -> None:
    """Runs after the HTTP response (own DB session, because the request session is closed)."""
    with SessionLocal() as db:
        doc = db.get(Document, document_id)
        if doc:
            pipeline.ingest_document(db, doc)


@router.post("/upload", response_model=DocumentOut, status_code=201)
async def upload_document(background: BackgroundTasks, file: UploadFile = File(...), db: Session = Depends(get_db)):
    limit = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    data = await file.read(limit + 1)
    try:
        clean_name = validate_upload(file.filename or "", len(data))
    except FileValidationError as e:
        raise HTTPException(413 if "exceeds" in str(e) else 400, str(e))

    digest = sha256_bytes(data)
    dup = db.query(Document).filter(Document.file_hash == digest).first()
    if dup:
        raise HTTPException(409, f"This file was already uploaded as '{dup.filename}'.")

    doc_id = new_id()
    ext = Path(clean_name).suffix.lower()
    path = resolve_inside(settings.UPLOAD_DIR, f"{doc_id}{ext}")
    path.write_bytes(data)
    doc = Document(id=doc_id, filename=clean_name, file_type=ext.lstrip("."), file_size=len(data),
                   file_hash=digest, processing_status="uploaded", storage_path=str(path))
    db.add(doc)
    db.commit()
    background.add_task(process_document_task, doc.id)
    return doc


@router.get("", response_model=list[DocumentOut])
def list_documents(q: Optional[str] = None, status: Optional[str] = None, file_type: Optional[str] = None,
                   db: Session = Depends(get_db)):
    query = db.query(Document)
    if q:
        query = query.filter(Document.filename.ilike(f"%{q}%"))
    if status:
        query = query.filter(Document.processing_status == status)
    if file_type:
        query = query.filter(Document.file_type == file_type.lower())
    return query.order_by(Document.upload_date.desc()).all()


def _get_or_404(db: Session, document_id: str) -> Document:
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(404, "Document not found.")
    return doc


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: str, db: Session = Depends(get_db)):
    return _get_or_404(db, document_id)


@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: str, db: Session = Depends(get_db)):
    doc = _get_or_404(db, document_id)
    if doc.processing_status == "processing":
        raise HTTPException(409, "The document is being processed. Try again in a moment.")
    pipeline.delete_document_data(doc.id)
    Path(doc.storage_path).unlink(missing_ok=True)
    db.delete(doc)
    db.commit()


@router.post("/{document_id}/process", response_model=DocumentOut, status_code=202)
def reprocess_document(document_id: str, background: BackgroundTasks, db: Session = Depends(get_db)):
    doc = _get_or_404(db, document_id)
    if doc.processing_status == "processing":
        raise HTTPException(409, "The document is already being processed.")
    if not Path(doc.storage_path).exists():
        raise HTTPException(410, "The original file is missing from storage. Please upload it again.")
    doc.processing_status, doc.error_message = "processing", None
    db.commit()
    background.add_task(process_document_task, doc.id)
    return doc
