"""Pydantic request/response schemas (validation + Swagger docs)."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    filename: str
    file_type: str
    file_size: int
    upload_date: datetime
    processing_status: str
    total_chunks: int
    error_message: Optional[str] = None


class SourceOut(BaseModel):
    rank: int
    label: str
    document_id: str
    document_name: str
    chunk_id: str
    chunk_index: int
    page_number: Optional[int] = None
    section: Optional[str] = None
    score: float
    content: str
    rerank_score: Optional[float] = None
    keyword_coverage: Optional[float] = None
    kind: Optional[str] = None


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    conversation_id: Optional[str] = None
    document_ids: Optional[list[str]] = None  # None / empty = search all documents
    top_k: Optional[int] = Field(default=None, ge=1, le=20)


class AskResponse(BaseModel):
    conversation_id: str
    answer: str
    has_answer: bool
    sources: list[SourceOut]


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime
    sources: list[SourceOut] = []


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationOut):
    messages: list[MessageOut]


class RetrievalRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: Optional[int] = Field(default=None, ge=1, le=20)
    threshold: Optional[float] = Field(default=None, ge=0, le=1)
    document_ids: Optional[list[str]] = None
    include_below_threshold: bool = False


class SettingsUpdate(BaseModel):
    chunk_size: Optional[int] = Field(default=None, ge=50, le=2000)
    chunk_overlap: Optional[int] = Field(default=None, ge=0, le=1000)
    top_k: Optional[int] = Field(default=None, ge=1, le=20)
    similarity_threshold: Optional[float] = Field(default=None, ge=0, le=1)
    llm_model: Optional[str] = Field(default=None, min_length=1, max_length=100)
