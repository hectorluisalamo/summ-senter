from app.services import clean_html_to_text

def test_cleaning_strips_scripts():
    html = "<h1>Title</h1><script>alert('x')</script><p>Body</p>"
    out = clean_html_to_text(html)
    assert 'alert(' not in out
    assert 'Title' in out and 'Body' in out