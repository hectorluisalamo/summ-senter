#!/usr/bin/env python3
import os, re, time, hashlib, json, sqlite3, uuid
from urllib.parse import urlparse, parse_qs, unquote
from urllib3.util.retry import Retry
from urllib.robotparser import RobotFileParser
import requests
from requests.adapters import HTTPAdapter
from collections import defaultdict
from bs4 import BeautifulSoup
from readability import Document
import datetime as dt
from langdetect import detect, LangDetectException

DB_PATH = os.getenv('DB_PATH', 'data/app.db')
RSS_PATH = 'config/rss_feeds.txt'
USER_AGENT = 'NewsSumSentimentBot/0.1 (+contact: halamo24@gmail.com)'
ALLOWLIST_PATH = 'config/allowlist.txt'

TIMEOUT = 8
RETRIES = 3
BACKOFF = 0.5
STATUS_RETRY = [429, 500, 502, 503, 504]

fail_by_domain = defaultdict(int)
FAIL_LIMIT = 3

def load_allowlist(path=ALLOWLIST_PATH):
    if not os.path.exists(path):
        return set()
    out: set[str] = set()
    with open(path) as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith('#'):
                continue
            out.add(s.lower().rstrip('.'))
    return out
    
ALLOWLIST = load_allowlist()

AGGREGATORS = {'news.google.com'}

def _normalize_host(host: str) -> str:
    host = (host or '').lower().rstrip('.')
    if ':' in host:
        host = host.split(':', 1)[0]
    return host

# If Google News, try to extract the real publisher URL
# from the 'url' query param; 
# else return original.
def de_aggregate_url(u: str) -> str:
    try:
        p = urlparse(u)
    except Exception:
        return u
    host = _normalize_host(p.netloc)
    if host in AGGREGATORS:
        qs = parse_qs(p.query)
        vals = qs.get('url')
        if vals and vals[0]:
            target = vals[0]
            return unquote(unquote(target))
    return u

def is_allowed_domain(domain: str) -> bool:
    return any(domain == d or domain.endswith('.' + d) for d in ALLOWLIST)

def make_session():
    s =requests.Session()
    retry = Retry(
        total=RETRIES,
        connect=RETRIES,
        read=RETRIES,
        backoff_factor=BACKOFF,
        status_forcelist=STATUS_RETRY,
        allowed_methods=['GET', 'HEAD'],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
    s.mount('http://', adapter)
    s.mount('https://', adapter)
    s.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    })
    return s

SESSION = make_session()

ROBOTS_CACHE = {}
def robots_allows(url: str) -> bool:
    p = urlparse(url)
    base = f'{p.scheme}://{p.netloc}'
    robots_url = base + '/robots.txt'
    rp = ROBOTS_CACHE.get(base)
    if rp is None:
        rp = RobotFileParser()
        rp.set_url(robots_url)
        try:
            rp.read()
        except Exception:
            ROBOTS_CACHE[base] = rp
            return True
        ROBOTS_CACHE[base] = rp
    return rp.can_fetch(USER_AGENT, url)

def clean_html_to_text(html: str) -> str:
    doc = Document(html)
    article_html = doc.summary()
    soup = BeautifulSoup(article_html, 'lxml')
    for tag in soup(['script','style','iframe','noscript']):
        tag.decompose()
    for el in soup(True):
        for attr in list(el.attrs.keys()):
            if attr.lower().startswith('on'):
                del el.attrs[attr]
    text = soup.get_text(separator=' ')
    text = ' '.join(text.split())
    return text

def get_lang(text: str, default='en') -> str:
    try:
        code = detect(text)
        if code.startswith('es'):
            return 'es'
        if code.startswith('en'):
            return 'en'
        return default
    except LangDetectException:
        return default

def text_hash(text: str) -> str:
    s = (text or '')
    s = s.lower()
    s = ' '.join(s.split())
    s = re.sub(r'[^\w\s]', '', s)
    return hashlib.sha256(s.encode('utf-8')).hexdigest()       # CS50: sha256(norm).hexdigest()

def ensure_db():
    os.makedirs('data', exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    with open('data/schema.sql','r') as f:
        conn.executescript(f.read())
    conn.close()

def upsert_article(conn, row):
    conn.execute("""
      INSERT OR REPLACE INTO articles(id,url,domain,title,lang,pub_time,snippet,text_hash,create_time)
      VALUES(:id,:url,:domain,:title,:lang,:pub_time,:snippet,:text_hash,:create_time)
    """, row)

def fetch_article(url):
    if not robots_allows(url):
        return None, 'blocked_by_robots'
    r = SESSION.get(url, headers={'User-Agent': USER_AGENT}, timeout=TIMEOUT)
    if r.status_code != 200:
        return None, f'http_{r.status_code}'
    html = r.text
    text = clean_html_to_text(html)
    return text, 'ok'

def process_rss_feed(feed_url):
    try:
        r = SESSION.get(feed_url, timeout=TIMEOUT)
        soup = BeautifulSoup(r.text, 'xml')
        items = soup.find_all(['item', 'entry'])
        out = []
        for i in items[:6]:
            url = None
            if i.name == 'item':
                if i.link and i.link.text:
                    url = i.link.text.strip()
                elif i.guid and i.guid.text:
                    url = i.guid.text.strip()
            else:
                link_tag = i.find('link', attrs={"rel": ["alternative", None]})
                if link_tag and link_tag.get('href'):
                    url = link_tag.get('href').strip()
            title = (i.title.text.strip() if i.title else '')
            pubdate = (i.pubDate.text.strip() if i.name=='item' and i.pubDate else
                       i.updated.text.strip() if i.name=='entry' and i.updated else '')
            if url:
                out.append((url, title, pubdate))
        return out
    except Exception:
        return []

def main():
    ensure_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    with open(RSS_PATH) as f:
        feeds = [l.strip() for l in f if l.strip() and not l.startswith('#')]
    for feed in feeds:
        for url, title, pubdate in process_rss_feed(feed):
            if not url:
                continue
            url = de_aggregate_url(url)
            domain = urlparse(url).netloc
            if not is_allowed_domain(domain):
                continue
            if fail_by_domain[domain] >= FAIL_LIMIT:
                print('SKIP domain (too many fails):', domain)
                continue
            try:
                text, status = fetch_article(url)
                if status != 'ok' or not text:
                    fail_by_domain[domain] += 1
                    continue
                lang = get_lang(text)
                if lang not in ('en','es'):
                    continue
                h = text_hash(text)
                row = {
                    'id': str(uuid.uuid4()),
                    'url': url,
                    'domain': domain,
                    'title': title[:300] if title else None,
                    'lang': lang,
                    'pub_time': pubdate,
                    'snippet': text[:600],
                    'text_hash': h,
                    'create_time': dt.datetime.now(dt.timezone.utc).isoformat()
                }
                upsert_article(conn, row)
                conn.commit()
                print('OK:', domain, lang, title[:60])
            except Exception as e:
                print('ERR:', url, e)
    conn.close()

if __name__ == '__main__':
    main()