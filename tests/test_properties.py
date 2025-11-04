import time
from app.schemas import AnalyzeResponse

def test_idempotent_same_input_version(client, mock_summarize):
    payload = {"text": "Policy update: new targets this year.", "lang": "en"}
    r1 = client.post('/analyze', json=payload).json()
    time.sleep(0.01)
    r2 = client.post('/analyze', json=payload).json()
    assert r1['summary'] == r2['summary']
    assert r1['model_version'] == r2['model_version']