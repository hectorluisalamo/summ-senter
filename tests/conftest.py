import os, pytest
from fastapi.testclient import TestClient

os.environ.setdefault('OPENAI_API_KEY', 'testkey')

from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture()
def client():
    return TestClient(app)

@pytest.fixture
def mock_summarize(monkeypatch):
    import app.routers.analyze as ar
    def fake_sum(text, lang):
        return {
            'summary': f'[SUM: {lang}] ' + text[:120], 
            'latency_ms': 5, 
            'model_version': 'openai:gpt-5-mini@sum_test',
            'usage': {'prompt_tokens': 50, 'completion_tokens': 80},
            'cost_cents': 0
        }
    monkeypatch.setattr(ar, 'summarize', fake_sum, raising=True)
    
    import scripts.summarize_openai as so
    monkeypatch.setattr(so, 'summarize', fake_sum, raising=True)
    
    import app.routers.analyze as ar
    monkeypatch.setattr(ar, 'predict_label', lambda text: ('neutral', 0.5, 'sent@test'), raising=True)
    
@pytest.fixture
def mock_fetch(monkeypatch):
    import app.services as services
    monkeypatch.setattr(services, 'fetch_url', lambda url: 'Breaking: profits up 12% as costs fall.', raising=True)
    
@pytest.fixture
def mock_sentiment(monkeypatch):
    from scripts import sentiment_infer
    def fake_sent(text):
        return ('neutral', 0.66, 'distilbert-mc@sent_test')
    monkeypatch.setattr(sentiment_infer, 'predict_label', fake_sent)