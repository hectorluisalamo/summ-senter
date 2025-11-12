from app.services import clean_article_html

def test_cleaning_returns_text_and_meta():
    text, meta = clean_article_html("<html><title>T</title><p>X</p></html>")
    assert isinstance(text, str) and isinstance(meta, dict)
    assert set(meta.keys()) == {'title','snippet','pub_time'}