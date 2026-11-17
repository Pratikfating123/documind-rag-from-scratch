def _upload(client, name="ml.txt", text="Overfitting happens when a model memorises training data and fails on new data."):
    return client.post("/api/documents/upload", files={"file": (name, text.encode(), "text/plain")})


def test_health_and_settings_hide_key(client):
    assert client.get("/api/health").json()["status"] == "ok"
    s = client.get("/api/settings").json()
    assert "groq_api_key" not in str(s).lower() and s["chunk_size"] > 0


def test_upload_process_list_delete(client, env):
    r = _upload(client)
    assert r.status_code == 201
    doc_id = r.json()["id"]
    got = client.get(f"/api/documents/{doc_id}").json()
    assert got["processing_status"] == "processed" and got["total_chunks"] == 1
    assert len(client.get("/api/documents?q=ml").json()) == 1
    assert env.count() == 1
    assert client.delete(f"/api/documents/{doc_id}").status_code == 204
    assert env.count() == 0 and client.get(f"/api/documents/{doc_id}").status_code == 404


def test_upload_validation(client):
    assert _upload(client, "bad.exe").status_code == 400
    assert client.post("/api/documents/upload", files={"file": ("e.txt", b"", "text/plain")}).status_code == 400
    assert _upload(client).status_code == 201
    assert _upload(client).status_code == 409  # duplicate


def test_chat_flow_and_conversations(client):
    _upload(client)
    r = client.post("/api/chat/ask", json={"question": "What is overfitting in a model?"})
    body = r.json()
    assert r.status_code == 200 and body["has_answer"] and body["sources"][0]["document_name"] == "ml.txt"
    cid = body["conversation_id"]
    detail = client.get(f"/api/chat/conversations/{cid}").json()
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
    assert detail["messages"][1]["sources"]
    assert client.post("/api/chat/ask", json={"question": "capital of France?"}).json()["has_answer"] is False
    assert client.delete(f"/api/chat/conversations/{cid}").status_code == 204
    assert client.post("/api/chat/ask", json={"question": "x", "conversation_id": "nope"}).status_code == 404
    assert client.post("/api/chat/ask", json={"question": ""}).status_code == 422


def test_retrieval_endpoint(client):
    _upload(client)
    r = client.post("/api/retrieval/search", json={"query": "overfitting model", "include_below_threshold": True}).json()
    assert r["query_embedding"]["dimension"] > 0
    assert r["results"][0]["explanation"] and r["results"][0]["passes_threshold"]


def test_dashboard_uses_real_data(client):
    assert client.get("/api/dashboard/stats").json()["total_documents"] == 0
    _upload(client)
    client.post("/api/chat/ask", json={"question": "overfitting model"})
    s = client.get("/api/dashboard/stats").json()
    assert s["total_documents"] == 1 and s["processed_documents"] == 1 and s["total_questions"] == 1
    a = client.get("/api/dashboard/activity").json()
    assert sum(x["count"] for x in a["uploads_per_day"]) == 1 and a["recent_activity"]


def test_update_settings_validation(client):
    assert client.put("/api/settings", json={"chunk_size": 100, "chunk_overlap": 100}).status_code == 422
    assert client.put("/api/settings", json={"top_k": 3}).json()["top_k"] == 3
