import os, re, hashlib, sqlite3, requests
from urllib.parse import urlparse
import urllib.robotparser as roboparser
from bs4 import BeautifulSoup
from fastapi import HTTPException
from readability import Document
from app.obs import log

ALLOWLIST_PATH = 'config/allowlist.txt'
USER_AGENT = 'NewsSumSentiment/0.1 (+contact: halamo24@gmail.com)'
MAX_INPUT_CHARS = 8000
FETCH_TIMEOUT_S = 10
DB_PATH = os.getenv('DB_PATH', 'data/app.db')

def load_allowlist():
    with open(ALLOWLIST_PATH, 'r', encoding='utf-8') as f:
        domains = []
        for line in f:
            s = line.strip()
            if not s or s.startswith('#'):
                continue
            s = s.lower().lstrip('.')
            domains.append(s)
        return set(domains)
    
ALLOW = load_allowlist()

def reload_allowlist():
    global ALLOW
    ALLOW = load_allowlist()

def domain_allowed(url: str) -> bool:
    host = urlparse(url).hostname or ''
    host = host.lower().rstrip('.')
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

def clean_html_to_text(html: str):
    doc = Document(html)
    soup = BeautifulSoup(doc.summary(), 'lxml')
    for tag in soup(['script', 'style', 'iframe', 'noscript']):
        tag.decompose()
    for el in soup(True):
        for attr in list(el.attrs.keys()):
            if attr.lower().startswith('on'):
                del el.attrs[attr]
    full = ' '.join(soup.get_text(separator=' ').split())
    text = full[:MAX_INPUT_CHARS]
    return text

def fetch_url(url: str) -> str:
    if not domain_allowed(url):
        raise HTTPException(status_code=403, detail='domain_not_allowed')
    if not robots_allow(url):
        raise HTTPException(status_code=403, detail='blocked_by_robots')
    resp = requests.get(url, headers={'User-Agent': USER_AGENT}, timeout=FETCH_TIMEOUT_S)
    if resp.status_code != 200:
        raise HTTPException(status_code=400, detail=f'http_{resp.status_code}')
    return clean_html_to_text(resp.text)

def cache_key(url: str, model_version: str) -> str:
    blob = (url + '|' + model_version).encode('utf-8')
    return 'an:' + hashlib.sha256(blob).hexdigest()

def ensure_db():
    os.makedirs('data', exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    schema_path = 'data/schema.sql'
    if os.path.exists(schema_path):
        conn.executescript(open(schema_path).read())
    else:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS articles(
            id TEXT PRIMARY KEY,
            url TEXT NOT NULL,
            domain TEXT NOT NULL,
            title TEXT,
            lang TEXT CHECK (lang IN ('en','es')),
            pub_time TIMESTAMP,
            snippet TEXT,
            text_hash TEXT NOT NULL,
            fetch_status TEXT,
            create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS analyses(
            article_id TEXT NOT NULL,
            summary TEXT,
            key_sentences JSON,
            sentiment TEXT CHECK (sentiment IN ('positive','neutral','negative')),
            confidence REAL,
            cost_cents INTEGER,
            tokens INTEGER,
            model_version TEXT,
            create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(article_id) REFERENCES articles(id)
        );
        """)
    conn.close()
    
def store_analysis(aid, url, domain, title, lang, summary, sentiment, conf, tokens, latency_ms, cost_cents, model_version):
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    
    snippet = (summary or '')[:600]
    norm = ' '.join(snippet.lower().split())
    text_hash = hashlib.sha256(norm.encode('utf-8')).hexdigest()
    
    cur.execute("""INSERT OR REPLACE INTO articles
                (id, url, domain, title, lang, pub_time, snippet, text_hash, create_time) 
                VALUES(?,?,?,?,?,?,?,?, datetime('now'))
    """, (aid, url or '', domain or '', (title or None), lang, None, snippet, text_hash))
    
    cur.execute("""
        INSERT OR REPLACE INTO analyses
        (article_id, summary, sentiment, confidence, cost_cents, model_version, create_time)
        VALUES (?,?,?,?,?,?, datetime('now'))
    """, (aid, summary or '', sentiment, float(conf), int(cost_cents), model_version))
    
    conn.commit(); conn.close()