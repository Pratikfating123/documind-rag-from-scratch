"""Retrieval regression tests on three fixture documents that mimic the problem report:
every document starts with a 'Suggested Test Questions' list and a 'Testing Note' that repeat the user's
wording, and the real explanation sits later in the document.

Run with the default FakeEmbedder (no downloads) or with the real model:  RAG_TEST_REAL_MODEL=1 pytest
"""
import logging
import re

import numpy as np
import pytest

from app.config import settings
from app.services.retriever import Retriever
from app.services.text_chunker import chunk_pages
from app.services.vector_store import IndexMismatchError, VectorStore, cosine_similarity
from tests.fakes import FIXTURES, load_fixture_pages, make_embedder


@pytest.fixture()
def idx(tmp_path):
    emb = make_embedder()
    store = VectorStore(tmp_path / "vec")
    size, overlap = settings.effective_chunking()
    max_len = getattr(emb, "max_seq_length", None)
    chunks_by_doc = {}
    for key, name in FIXTURES.items():
        chunks = chunk_pages(load_fixture_pages(name), key, size, overlap, emb.count_tokens, max_len - 2)
        chunks_by_doc[key] = chunks
        store.add(emb.embed_texts([c.content for c in chunks]), [
            {"chunk_id": c.chunk_id, "document_id": key, "document_name": name + ".pdf", "chunk_index": c.chunk_index,
             "page_number": c.page_number, "section": c.section, "kind": c.kind, "content": c.content}
            for c in chunks])
    return {"store": store, "emb": emb, "retriever": Retriever(store, emb), "chunks": chunks_by_doc}


def _assert_top(results, doc, must_contain, section=None):
    assert results, "nothing retrieved"
    top = results[0]
    assert top["document_id"] == doc, f"top result came from {top['document_id']} (page {top['page_number']})"
    assert top["kind"] == "content"
    text = top["content"].lower()
    for word in must_contain:
        assert word in text, f"'{word}' missing from top chunk: {text[:120]}"
    if section:
        assert section.lower() in (top["section"] or "").lower()


# ------------------------------------------------------------------ the five required queries
def test_q1_what_is_rag(idx):
    r = idx["retriever"].retrieve("What is Retrieval-Augmented Generation?")
    _assert_top(r, "ai", ["retrieval-augmented generation is a technique", "chunks"], "Retrieval-Augmented")
    assert r[0]["page_number"] == 3


def test_q1_full_user_query(idx):
    r = idx["retriever"].retrieve(
        "What is Retrieval-Augmented Generation? Explain how it works and why it is useful.")
    _assert_top(r, "ai", ["four steps", "hallucination"], "Retrieval-Augmented")


def test_q2_ai_ml_dl_relationship(idx):
    r = idx["retriever"].retrieve("Explain the relationship between AI, ML, and DL.")
    _assert_top(r, "ai", ["subset", "deep learning"], "Relationship")


def test_q3_cia_triad(idx):
    r = idx["retriever"].retrieve("What are the three components of the CIA triad?")
    _assert_top(r, "cyber", ["confidentiality", "integrity", "availability"], "CIA Triad")


def test_q4_precision_vs_recall(idx):
    r = idx["retriever"].retrieve("What is the difference between precision and recall?")
    _assert_top(r, "ml", ["precision", "recall"], "Evaluation Metrics")


def test_q5_reinforcement_learning(idx):
    r = idx["retriever"].retrieve("How does reinforcement learning work?")
    _assert_top(r, "ml", ["reward", "agent"], "Reinforcement Learning")


def test_unrelated_question_returns_no_evidence(idx):
    r = idx["retriever"].retrieve("What is the capital of Japan?")
    assert [x for x in r if x["kind"] == "content"] == []  # nothing the LLM could (wrongly) answer from


# ------------------------------------------------------------------ chunking quality
def test_question_lists_are_tagged_and_never_mixed_with_explanations(idx):
    for key, chunks in idx["chunks"].items():
        first_page = [c for c in chunks if c.page_number == 1]
        assert any(c.kind == "questions" for c in first_page), key
        for c in chunks:
            if c.kind == "questions":
                assert "technique that gives a language model" not in c.content
            headings = [h for h in ("Suggested Test Questions", "Testing Note") if h in c.content]
            assert len(headings) <= 1, f"{key}: a chunk mixes unrelated sections"


def test_rag_definition_is_inside_one_complete_chunk(idx):
    rag = [c for c in idx["chunks"]["ai"] if c.section and c.section.startswith("Retrieval-Augmented")]
    joined = " ".join(c.content for c in rag)
    assert "Fourth, the model generates an answer" in joined and "cite their sources" in joined
    assert all(c.page_number == 3 and c.kind == "content" for c in rag)


def test_no_chunk_exceeds_model_window_and_all_are_indexed(idx):
    emb = idx["emb"]
    total = 0
    for chunks in idx["chunks"].values():
        assert max(emb.count_tokens([c.content for c in chunks])) <= emb.max_seq_length
        assert len({c.chunk_id for c in chunks}) == len(chunks)
        total += len(chunks)
    assert idx["store"].count() == total
    assert idx["store"].vectors.shape == (total, idx["emb"].embed_query("x").shape[0])


def test_chunk_size_is_configurable_and_capped():
    assert settings.effective_chunking()[0] <= settings.EMBED_MAX_WORDS
    pages = load_fixture_pages(FIXTURES["ai"])
    small = chunk_pages(pages, "d", 40, 10)
    big = chunk_pages(pages, "d", 150, 30)
    assert len(small) > len(big)
    assert all(len(c.content.split()) <= 60 for c in small)  # 40 words + heading prefix


# ------------------------------------------------------------------ retrieval behaviour
def test_original_score_preserved_threshold_respected(idx):
    q = "What is Retrieval-Augmented Generation?"
    r = idx["retriever"].retrieve(q)
    from app.services.retriever import expand_query
    qvec = idx["emb"].embed_query(expand_query(q))  # the score is the cosine against the query as searched
    by_id = {m["chunk_id"]: i for i, m in enumerate(idx["store"].metadata)}
    for hit in r:
        expected = float(cosine_similarity(qvec, idx["store"].vectors)[by_id[hit["chunk_id"]]])
        assert hit["score"] == pytest.approx(round(expected, 4))
        assert hit["score"] >= settings.SIMILARITY_THRESHOLD
        assert "rerank_score" in hit


def test_document_filter_and_no_duplicates(idx):
    r = idx["retriever"].retrieve("encryption and firewalls", document_ids=["cyber"], threshold=0.0)
    assert r and {x["document_id"] for x in r} == {"cyber"}
    assert len({x["chunk_id"] for x in r}) == len(r)


def test_neighbouring_context_attached_for_sections(idx):
    r = idx["retriever"].retrieve("What is Retrieval-Augmented Generation?")
    assert r[0]["context"] and r[0]["content"] in r[0]["context"]


def test_diagnostics_are_logged(idx, caplog):
    caplog.set_level(logging.INFO, logger="rag.retrieval")
    idx["retriever"].retrieve("What are the three components of the CIA triad?")
    text = caplog.text
    assert "candidates before filtering=" in text and "after filtering=" in text
    assert "RAG_Test_Cybersecurity_Fundamentals.pdf" in text and "cosine=" in text and "page=" in text


# ------------------------------------------------------------------ embedding / store consistency
def test_dimension_mismatch_is_detected(idx):
    with pytest.raises(IndexMismatchError):
        idx["store"].search(np.ones(7, dtype=np.float32))


def test_replace_document_is_atomic(idx):
    store = idx["store"]
    before = store.count()
    with pytest.raises(IndexMismatchError):
        store.replace_document("ai", np.ones((1, 7), dtype=np.float32), [{"chunk_id": "x", "document_id": "ai"}])
    assert store.count() == before  # old vectors untouched after the failed swap


def test_empty_text_is_rejected(idx):
    from app.services.embedding_engine import EmptyTextError
    with pytest.raises(EmptyTextError):
        idx["retriever"].retrieve("   ")
    with pytest.raises(EmptyTextError):
        idx["emb"].embed_texts(["ok", "  "])


def test_abbreviations_are_expanded_both_ways():
    from app.services.retriever import expand_query
    assert "machine learning" in expand_query("What is ML?")
    assert "RAG" in expand_query("What is retrieval-augmented generation?")
    assert expand_query("What is the CIA triad?") == "What is the CIA triad?"
