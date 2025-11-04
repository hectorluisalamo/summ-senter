def test_html_injection_sanitized(client, mock_summarize):
    malicious = "h1>Hi</h1><img src=x onerror=alert(1)><script>steal()</script><p>Body</p>"
    r = client.post('/analyze', json={"html": malicious, "lang": "en"})
    assert r.status_code == 200
    body = r.json()
    assert 'onerror' not in body and 'alert(' not in body
    
    from app.services import clean_html_to_text
    txt = clean_html_to_text(malicious)
    assert 'steal()' not in txt and 'onerror' not in txt and 'Hi' in txt and 'Body' in txt
