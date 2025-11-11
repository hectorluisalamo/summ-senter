import datetime, os, json, hashlib, re, sqlite3, requests
from pathlib import Path
from urllib.parse import urlparse
import urllib.robotparser as roboparser
from bs4 import BeautifulSoup
from fastapi import HTTPException
from readability import Document
from app.obs import log
import requests

ALLOWLIST_PATH = 'config/allowlist.txt'
USER_AGENT = 'NewsSumSentiment/0.1 (+contact: halamo24@gmail.com)'
MAX_INPUT_CHARS = 8000
FETCH_TIMEOUT_S = 20
DB_PATH = os.getenv('DB_PATH', 'data/app.db')
SNIPPET_CHARS = 240
MAX_BYTES = 2_500_000

def _normalize_whitespace(s: str) -> str:
    return re.sub(r'\s+', ' ', (s or '').strip())

def _lower(x: object) -> str:
    return str(x or '').lower()

def _to_str_or_none(x, *, maxlen=None):
    if x is None:
        return None
    if isinstance(x, (list, tuple)):
        x = ' '.join(map(str, x))
    elif isinstance(x, dict):
        x = json.dumps(x, ensure_ascii=False)
    else:
        x = str(x)
    x = x.strip()
    if not x:
        return None
    if maxlen and len(x) > maxlen:
        x = x[:maxlen]
    return x

def build_snippet(text: str, n: int = SNIPPET_CHARS) -> str:
    t = _normalize_whitespace(text)
    return t[:n]
    
def build_text_hash(text: str) -> str:
    norm = _normalize_whitespace(text)
    return hashlib.sha256('utf-8').hexdigest()

def load_allowlist():
    with open(ALLOWLIST_PATH, 'r', encoding='utf-8') as f:
        domains = []
        for line in f:
            s = line.strip()
            if not s or s.startswith('#'):
                continue
            s = _lower(s).lstrip('.')
            domains.append(s)
        return set(domains)
    
ALLOW = load_allowlist()

def reload_allowlist():
    global ALLOW
    ALLOW = load_allowlist()

def domain_allowed(url: str) -> bool:
    host = urlparse(url).hostname or ''
    host = _lower(host).rstrip('.')
    allowed = any(host == d or host.endswith('.' + d) for d in ALLOW)
    if not allowed:
        log.info('domain_denied', host=host, allowlist=list(ALLOW)[:12], allowlist_size=len(ALLOW))
    return allowed

def robots_allow(url: str) -> bool:
    parsed = urlparse(url)
    base = f'{parsed.scheme}://{parsed.netloc}'
    robots_url = base + '/robots.txt'
    try:
        rp = roboparser.RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch(USER_AGENT, url)
    except Exception:
        return True

def clean_article_html(html: str) -> tuple[str, dict]:
    soup = BeautifulSoup(html or '', 'lxml')
    title = (soup.title.string or '').strip if soup.title else None
    for attr, val in [('property', 'og:description'), ('name', 'description')]:
        tag = soup.find('meta', {attr: val})
        if tag and tag.get('content'):
            desc = tag['content'].strip()
            break
    
    pub = None
    for attr, val in [('property', 'article:published_time'), ('itemprop', 'datePublished'), ('name', 'pubdate'), ('name', 'date')]:
        tag = soup.find('meta', {attr: val})
        if tag and tag.get('content'):
            pub = tag['content'].strip()
            break
    if not pub:
        t = soup.find('time', attrs={'datetime': True})
        if t:
            pub = t['datetime'].strip()
            
    doc = Document(html)
    soup = BeautifulSoup(doc.summary(), 'lxml')
    for tag in soup(['script', 'style', 'iframe', 'noscript']):
        tag.decompose()
    for el in soup(True):
        for attr in list(el.attrs.keys()):
            if _lower(attr).startswith('on'):
                del el.attrs[attr]
    full = ' '.join(soup.get_text(separator=' ').split())
    text = full[:MAX_INPUT_CHARS]
    
    meta = {'title': title, 'snippet': desc, 'pub_time': pub}
    return text, meta

def maybe_extract_pub_time(html: str) -> str | None:
    try:
        soup = BeautifulSoup(html or '', 'lxml')
        candidates = []
        for attr, val in [
            ('property', 'article: published_time'),
            ('name', 'pubdate'),
            ('name', 'date'),
            ('itemprop', 'datePublished'),
        ]:
            tag = soup.find('meta', {attr: val})
            if tag and tag.get('content'): candidates.append(tag['content'])
        t = soup.find('time', attrs={'datetime': True})
        if t: candidates.append(t['datetime'])
        for c in candidates:
            c = c.strip()
            try:
                dt = datetime.fromisoformat(c.replace('Z', '+00:00'))
                return dt.isoformat()
            except Exception:
                if re.search(r'\d{4}-\d{2}-\d{2}', c):
                    return c
        return None
    except Exception:
        return None

def fetch_url(url: str, timeout_s: int) -> str:
    if not domain_allowed(url):
        raise HTTPException(status_code=403, detail='domain_not_allowed')
    if not robots_allow(url):
        raise HTTPException(status_code=403, detail='blocked_by_robots')
    headers = {'User-Agent': USER_AGENT}
    resp = requests.get(url, headers=headers, timeout=FETCH_TIMEOUT_S, allow_redirects=True, stream=True)
    if resp.status_code != 200:
        raise HTTPException(status_code=400, detail=f'http_{resp.status_code}')
    ctype = (resp.headers.get('content-type') or '').lower()
    if 'text/html' not in ctype and 'application/xhtml+xml' not in ctype:
        raise HTTPException(status_code=415, detail='unsupported_media_type')
    
    content = b''
    for chunk in resp.iter_content(64_000):
        content += chunk
        if len(content) > MAX_BYTES:
            raise HTTPException(status_code=413, detail='page_too_large')
        
    resp.encoding = resp.encoding or resp.apparent_encoding or 'utf-8'
    html = content.decode(resp.encoding, errors='replace')
    return html

def cache_key(url: str, model_version: str) -> str:
    blob = (url + '|' + model_version).encode('utf-8')
    return 'an:' + hashlib.sha256(blob).hexdigest()

def ensure_db_dir():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

def safe_connect():
    try:
        ensure_db_dir()
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        raise HTTPException(status_code=503, detail={'code': 'db_unavailable', 'message': str(e)})

def ensure_db():
    os.makedirs('data', exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    schema_path = 'data/schema_v1_1.sql'
    if os.path.exists(schema_path):
        conn.executescript(open(schema_path).read())
    else:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS articles(
            id TEXT PRIMARY KEY,
            url TEXT NOT NULL,
            domain TEXT NOT NULL,
            title TEXT,
            lang TEXT CHECK (lang IN ('en','es')) NOT NULL,
            pub_time TEXT,   -- ISO 8601
            snippet TEXT,
            text_hash TEXT NOT NULL,
            create_time TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS analyses(
            article_id TEXT NOT NULL,
            summary TEXT,
            sentiment TEXT CHECK (sentiment IN ('positive','neutral','negative')),
            confidence REAL,
            cost_cents INTEGER DEFAULT 0,
            model_version TEXT,
            create_time TEXT NOT NULL,
            PRIMARY KEY(article_id, model_version),
            FOREIGN KEY(article_id) REFERENCES articles(id)
        );
        CREATE TABLE IF NOT EXISTS ingest_log(
            id TEXT PRIMARY KEY,
            url TEXT NOT NULL,
            status TEXT NOT NULL,
            note TEXT,
            create_time TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_articles_text_hash ON articles(text_hash);
        CREATE INDEX IF NOT EXISTS idx_articles_create_time ON articles(create_time);
        CREATE INDEX IF NOT EXISTS idx_analyses_article_id ON analyses(article_id);
        """)
    conn.close()
    
def store_analysis(aid, url, domain, title, lang, pub_time, snippet, text_hash, summary, sentiment, confidence, cost_cents, model_version):
    conn = safe_connect()
    cur = conn.cursor()
    
    url = _to_str_or_none(url, maxlen=1024)
    domain = _to_str_or_none(domain, maxlen=255)
    title = _to_str_or_none(title, maxlen=512)
    lang = _to_str_or_none(lang, maxlen=10)
    pub_time = _to_str_or_none(pub_time)
    snippet = _to_str_or_none(snippet, maxlen=512)
    text_hash = _to_str_or_none(text_hash, maxlen=128)
    
    summary = _to_str_or_none(summary)
    sentiment = _to_str_or_none(sentiment, maxlen=16)
    model_version = _to_str_or_none(model_version, maxlen=128)
    
    cur.execute("""INSERT OR REPLACE INTO articles
                (id, url, domain, title, lang, pub_time, snippet, text_hash, create_time) 
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
    """, (aid, url or '', domain or '', (title or None), lang, None, snippet, text_hash))
    
    cur.execute("""
        INSERT OR REPLACE INTO analyses
        (article_id, summary, sentiment, confidence, cost_cents, model_version, create_time)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
    """, (aid, summary or '', sentiment, float(confidence), int(cost_cents), model_version))
    
    conn.commit()
    conn.close()