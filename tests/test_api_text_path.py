def test_text_path_ok(client):
    r = client.post("/analyze", json={"text": "Short test.", "lang": "en"})
    assert r.status_code == 200
    body = r.json()
    assert "summary" in body