"""Single shared instances (model loaded once, vector store loaded once)."""
from app.config import settings
from app.services.embedding_engine import embedding_engine
from app.services.llm_service import llm_service
from app.services.rag_pipeline import RAGPipeline
from app.services.retriever import Retriever
from app.services.vector_store import VectorStore

vector_store = VectorStore(settings.VECTOR_DIR, model_name=settings.EMBEDDING_MODEL)
retriever = Retriever(vector_store, embedding_engine)
pipeline = RAGPipeline(retriever, embedding_engine, vector_store, llm_service)
