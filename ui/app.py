import os, time, requests, streamlit as st

API_BASE = os.getenv('API_BASE', 'http://localhost:8000')
API_KEY = os.getenv('DEMO_API_KEY', '')

def _assert_api_base():
    if not (API_BASE.startswith('http://') or API_BASE.startswith('https://')):
        raise RuntimeError(f'API_BASE is invalid: {API_BASE}')

_assert_api_base()

st.set_page_config(page_title='News Summarizer + Sentiment Analyzer', layout='centered')
st.title('📰 News Summarizer & Sentiment Analyzer')
st.caption("Paste a URL or text. We'll summarize and analyze its tone, plus show cost & latency. English/Spanish supported!")

st.sidebar.write('Sidebar Menu')
st.sidebar.markdown(f'**API_BASE:** `{API_BASE}`')

if st.sidebar.button('Ping API /health'):
    try:
        response = requests.get(f'{API_BASE}/health', timeout=10)
        st.sidebar.success(f'/health → {response.status_code}: {response.json()}')
    except Exception as e:
        st.sidebar.error(f'/health failed: {e}')

with st.form('analyze'):
    mode = st.radio('Source', ['URL', 'Text'], horizontal=True)
    lang = st.selectbox('Language (input)', ['en', 'es'], index=0)
    if mode == 'URL':
        url = st.text_input('Article URL', placeholder='https://...')
        payload = {'url': url, 'lang': lang}
    else:
        text = st.text_area('Article Text', height=200, placeholder='Paste article text here...')
        payload = {'text': text, 'lang': lang}
    submitted = st.form_submit_button('Analyze (⌘/Ctrl + Enter)', icon='🚀')
    
def sentiment_badge(sentiment: str):
    s = (sentiment or '').lower()
    color_map = {'Positive': 'green', 'Neutral': 'blue', 'Negative': 'red'}
    label = s.capitalize() if s else 'Neutral'
    color = color_map.get(s, 'blue')
    st.markdown(f'<span style="background:{color}; color:white; padding:4px 8px; border-radius:6px">{label}</span>', unsafe_allow_html=True)
    
def call_api(payload: dict):
    t0 = time.time()
    headers = {'Content-Type': 'application/json'}
    if API_KEY:
        headers['Authorization'] = f'Bearer {API_KEY}'
    resp = requests.post(f'{API_BASE}/analyze', json=payload, headers=headers, timeout=60)
    dt = int((time.time() - t0) * 1000)
    ctype = resp.headers.get('Content-Type', '')
    is_json = 'application/json' in ctype.lower()
    if is_json:
        body =resp.json()
    else:
        body = {'non_json_body': resp.text[:1024]}
    return resp.status_code, body, dt

if submitted:
    if mode == 'URL' and not payload['url']:
        st.error('Please provide valid URL.')
    elif mode == 'Text' and not payload['text']:
        st.error('Please provide text.')
    else:
        with st.spinner('Analyzing...'):
            try:
                code, data, roundtrip_ms = call_api(payload)
                if isinstance(data, dict) and 'non_json_body' not in data:
                    st.error(f'API Error {code}: {data.get('code', '')} {data.get('message', '')}')
                    st.code(str(data), language='json')
                else:
                    st.error(f'API Error {code}')
                    st.code(data.get('non_json_body', '(empty body)'), language='text')
                    st.subheader('Summary')
                    st.write(data['summary'])
                    st.subheader('Sentiment Analysis')
                    sentiment_badge(data['sentiment'])
                    st.write(f'Confidence: **{data["confidence"]:.2f}**')
                    st.subheader('Details')
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric('Latency (ms)', data['latency_ms'])
                    col2.metric('Tokens', data['tokens'])
                    col3.metric('Cost (¢)', data['costs_cents'])
                    col4.metric('Cache', 'hit ✅' if data['cache_hit'] else 'miss ❌')
                    st.caption(f'Model: {data['model_version']}')
                    if payload.get('url'):
                        st.caption(f'Source: {payload["url"]}')
                    st.caption(f'Roundtrip UI→API→UI: {roundtrip_ms} ms')
            except Exception as e:
                st.exception(e)

st.markdown('---')
st.caption('Accessibility: large body text, high-contrast badges, keyboard submit (⌘/Ctrl + Enter).')