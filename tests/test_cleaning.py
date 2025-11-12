from app.services import clean_article_html

def test_cleaning_strips_scripts():
    html = "<h1>Title</h1><img src=x onerror=alert(1)><script>alert('x')</script><p>Body</p>"
    text, meta = clean_article_html(html)
    
    low = text.lower()
    # no script payload or inline event handlers
    assert "<script" not in low
    assert "alert(" not in low
    assert "onerror" not in low

    # content preserved
    assert "Title" in text and "Body" in text

    # plain text only (sanity)
    assert "<" not in text and ">" not in text
    
    # meta present with expected keys (may be None if not in HTML)
    assert set(meta.keys()) == {'title', 'snippet', 'pub_time'}