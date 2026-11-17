from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship
from app.database import Base
from app.utils.helpers import new_id, utcnow


class Document(Base):
    __tablename__ = "documents"
    id = Column(String, primary_key=True, default=new_id)
    filename = Column(String, nullable=False, index=True)
    file_type = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    file_hash = Column(String, index=True)  # prevents duplicate processing
    upload_date = Column(DateTime, default=utcnow, index=True)
    processing_status = Column(String, default="uploaded", index=True)  # uploaded|processing|processed|failed
    error_message = Column(Text, nullable=True)
    total_chunks = Column(Integer, default=0)
    storage_path = Column(String, nullable=False)
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")
