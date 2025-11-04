from scripts.ingest_rss import get_lang, text_hash

def test_lang_detect():
    assert get_lang('This is an English sentence') == 'en'
    assert get_lang('Este es un frase en español.') == 'es'
    
def test_hash():
    a = text_hash('Hello    world!')
    b = text_hash('hello world')
    assert a == b