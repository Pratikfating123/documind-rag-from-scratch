from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from app.database import Base


class Chunk(Base):
    __tablename__ = "chunks"
    id = Column(String, primary_key=True)
    document_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    page_number = Column(Integer, nullable=True)
    section = Column(String, nullable=True)
    embedding_reference = Column(String, nullable=True)  # chunk id key inside the vector store
    document = relationship("Document", back_populates="chunks")
