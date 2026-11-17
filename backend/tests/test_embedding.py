import numpy as np
import pytest


def test_fake_embedder_is_normalised(fake_embedder):
    v = fake_embedder.embed_texts(["machine learning models", "cats"])
    assert v.shape == (2, fake_embedder.dimension)
    assert np.allclose(np.linalg.norm(v, axis=1), 1.0, atol=1e-5)


@pytest.mark.skipif(True, reason="Downloads the real model (~90 MB). Remove skip to run manually.")
def test_real_model_dimension():
    from app.services.embedding_engine import EmbeddingEngine
    e = EmbeddingEngine()
    assert e.dimension == 384
    assert abs(np.linalg.norm(e.embed_query("hello")) - 1.0) < 1e-4
