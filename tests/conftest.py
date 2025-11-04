import os, json, time
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault('REDIS_URL', '')
os.environ.setdefault('OPENAI_API_KEY', 'testkey')

from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture(autouse=True)
def disable_cache_env(monkeypatch):
    monkeypatch.setenv('REDIS_URL', '')

@pytest.fixture()
def client():
    return TestClient(app)

@pytest.fixture
def mock_summarize(monkeypatch):
    from scripts import summarize_openai
    def fake_sum(text, lang):
        return {'summary': f'[SUM: {lang}] ' + text[:120], 'latency_ms': 5, 'model_version': 'openai:gpt-5-mini@sum_test'}
    monkeypatch.setattr(summarize_openai, 'summarize', fake_sum, raising=True)
    try:
        import app.services as services
        monkeypatch.setattr(services, 'summarize', fake_sum, raising=False)
    except Exception:
        pass
    
@pytest.fixture
def mock_fetch(monkeypatch):
    import app.services as services
    monkeypatch.setattr(services, 'fetch_url', lambda url: 'Breaking: profits up 12% as costs fall.', raising=True)