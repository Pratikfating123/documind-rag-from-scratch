import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import pipeline
from app.models.conversation import Conversation
from app.schemas import AskRequest, AskResponse, ConversationDetail, ConversationOut, MessageOut
from app.services.rag_pipeline import ConversationNotFoundError

router = APIRouter(prefix="/api/chat", tags=["Chat"])


@router.post("/ask", response_model=AskResponse)
def ask(req: AskRequest, db: Session = Depends(get_db)):
    try:
        return pipeline.ask(db, req.question.strip(), req.conversation_id, req.document_ids, req.top_k)
    except ConversationNotFoundError as e:
        raise HTTPException(404, str(e))


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(db: Session = Depends(get_db)):
    return db.query(Conversation).order_by(Conversation.updated_at.desc()).all()


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: str, db: Session = Depends(get_db)):
    conv = db.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(404, "Conversation not found.")
    messages = [MessageOut(id=m.id, role=m.role, content=m.content, created_at=m.created_at,
                           sources=json.loads(m.sources_json) if m.sources_json else []) for m in conv.messages]
    return ConversationDetail(id=conv.id, title=conv.title, created_at=conv.created_at,
                              updated_at=conv.updated_at, messages=messages)


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: str, db: Session = Depends(get_db)):
    conv = db.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(404, "Conversation not found.")
    db.delete(conv)
    db.commit()
