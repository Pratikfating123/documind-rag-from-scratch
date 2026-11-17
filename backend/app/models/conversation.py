from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from app.database import Base
from app.utils.helpers import new_id, utcnow


class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(String, primary_key=True, default=new_id)
    title = Column(String, default="New conversation")
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, index=True)
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan",
                            order_by="Message.id")


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=False)
    role = Column(String, nullable=False)  # user | assistant
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utcnow, index=True)
    sources_json = Column(Text, nullable=True)
    conversation = relationship("Conversation", back_populates="messages")
