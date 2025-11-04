from app.schemas import AnalyzeResponse

def test_health(client):
    r = client.get('/health')
    assert r.status_code == 200
    assert r.json()['status'] == 'ok'
    
def test_analyze_happy_path(client, mock_summarize):
    payload = {"text": "Markets rallied on upbeat outlook.", "lang": "en"}
    r = client.post('/analyze/', json=payload)
    assert r.status_code == 200
    body = r.json()
    AnalyzeResponse(**body)  # validate response schema
    assert 'summary' in body and 'sentiment' in body
    
def test_analyze_requires_single_input(client):
    r = client.post('/analyze/', json={"text": "Sample", "html": "<p>Sample</p>"})
    assert r.status_code == 400
    
def test_analyze_disallowed_domain(client, mock_fetch, mock_summarize, monkeypatch):
    import app.services as services
    monkeypatch.setattr(services, 'domain_allowed', lambda url: False, raising=True)
    r = client.post('/analyze/', json={"url": "http://bad.example.com/news"})
    assert r.status_code == 403