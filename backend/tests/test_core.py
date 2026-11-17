import numpy as np
import pytest
from app.services.text_chunker import chunk_text, chunk_pages
from app.services.document_processor import ExtractedPage, extract_txt
from app.services.vector_store import VectorStore, cosine_similarity
from app.utils.file_validator import safe_filename, validate_upload, FileValidationError


def test_chunking_respects_size_and_overlap():
    text = " ".join(f"Sentence number {i} is here." for i in range(200))
    chunks = chunk_text(text, chunk_size=50, overlap=10)
    assert len(chunks) > 1
    assert all(len(c.split()) <= 50 for c in chunks)
    last_sentence = chunks[0].split(". ")[-1]
    assert last_sentence in chunks[1]  # overlap carried over


def test_chunk_pages_keeps_metadata():
    pages = [ExtractedPage("Hello world. " * 100, page_number=3)]
    chunks = chunk_pages(pages, "doc1", 40, 10)
    assert {c.page_number for c in chunks} == {3}
    assert len({c.chunk_id for c in chunks}) == len(chunks)


def test_chunk_invalid_overlap():
    with pytest.raises(ValueError):
        chunk_text("a b c", 10, 10)


def test_cosine_similarity_known_values():
    q = np.array([1, 0], dtype=np.float32)
    m = np.array([[1, 0], [0, 1], [-1, 0]], dtype=np.float32)
    assert np.allclose(cosine_similarity(q, m), [1, 0, -1])


def test_vector_store_add_search_delete_persist(tmp_path):
    vs = VectorStore(tmp_path)
    vecs = np.eye(3, dtype=np.float32)
    vs.add(vecs, [{"chunk_id": str(i), "document_id": "A" if i < 2 else "B"} for i in range(3)])
    top = vs.search(np.array([1, 0, 0], dtype=np.float32), top_k=2)
    assert top[0]["chunk_id"] == "0" and top[0]["score"] == pytest.approx(1.0)
    only_b = vs.search(np.array([0, 0, 1], dtype=np.float32), document_ids=["B"])
    assert only_b[0]["document_id"] == "B"
    assert VectorStore(tmp_path).count() == 3
    assert vs.delete_document("A") == 2 and vs.count() == 1


def test_txt_extraction(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("Hello there.", encoding="utf-8")
    assert extract_txt(f)[0].text == "Hello there."


def test_filename_and_validation():
    assert safe_filename("../../etc/passwd.txt") == "passwd.txt"
    with pytest.raises(FileValidationError):
        validate_upload("x.exe", 10)
