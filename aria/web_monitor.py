"""ARIA Web Monitor — Watch websites for changes."""

import json, os, hashlib, logging, re, httpx
from datetime import datetime, date

logger = logging.getLogger(__name__)
OLLAMA_URL = os.environ.get("ARIA_OLLAMA_URL", "http://172.19.16.1:11434")
MONITOR_FILE = "data/web_monitors.json"

C = "\033[96m"; G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"; B = "\033[1m"; D = "\033[2m"; X = "\033[0m"

def _query_llm(prompt, model="qwen3:8b"):
    try:
        resp = httpx.post(f"{OLLAMA_URL}/api/chat", json={"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False, "options": {"temperature": 0.3, "num_predict": 1000}}, timeout=120)
        if resp.status_code == 200:
            content = resp.json().get("message", {}).get("content", "").strip()
            if "<think>" in content:
                end = content.find("</think>")
                if end > 0: content = content[end + 8:].strip()
            return content
    except: pass
    return ""

def _load_monitors():
    if os.path.exists(MONITOR_FILE):
        with open(MONITOR_FILE) as f: return json.load(f)
    return {"sites": [], "history": []}

def _save_monitors(data):
    os.makedirs(os.path.dirname(MONITOR_FILE), exist_ok=True)
    with open(MONITOR_FILE, "w") as f: json.dump(data, f, indent=2)

def _fetch_page(url):
    try:
        resp = httpx.get(url, timeout=15, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200:
            text = resp.text
            text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL)
            text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:10000]
    except: pass
    return ""

def _content_hash(text):
    return hashlib.md5(text.encode()).hexdigest()

def add_site(url, name=None):
    monitors = _load_monitors()
    if any(s["url"] == url for s in monitors["sites"]):
        print(f"{Y}Already monitoring: {url}{X}")
        return
    content = _fetch_page(url)
    monitors["sites"].append({"url": url, "name": name or url[:50], "last_hash": _content_hash(content) if content else "", "last_check": datetime.now().isoformat(), "added": date.today().isoformat()})
    _save_monitors(monitors)
    print(f"{G}Now monitoring: {name or url}{X}")

def remove_site(url):
    monitors = _load_monitors()
    monitors["sites"] = [s for s in monitors["sites"] if s["url"] != url]
    _save_monitors(monitors)
    print(f"{G}Removed: {url}{X}")

def check_all():
    monitors = _load_monitors()
    if not monitors["sites"]:
        print(f"{Y}No sites being monitored. Add with: aria monitor add URL{X}")
        return
    print(f"{C}{B}Checking {len(monitors['sites'])} sites...{X}\n")
    changes = []
    for site in monitors["sites"]:
        print(f"  {D}Checking: {site['name']}...{X}", end=" ")
        content = _fetch_page(site["url"])
        if not content:
            print(f"{R}Failed{X}")
            continue
        new_hash = _content_hash(content)
        if new_hash != site["last_hash"] and site["last_hash"]:
            print(f"{Y}CHANGED!{X}")
            changes.append(site["name"])
            summary = _query_llm(f"Briefly summarize what this webpage is about:\n\n{content[:2000]}")
            if summary: print(f"    {C}{summary[:200]}{X}")
            monitors["history"].append({"url": site["url"], "name": site["name"], "changed_at": datetime.now().isoformat(), "summary": summary[:300] if summary else ""})
        else:
            print(f"{G}No change{X}")
        site["last_hash"] = new_hash
        site["last_check"] = datetime.now().isoformat()
    _save_monitors(monitors)
    if changes:
        try: httpx.post("http://127.0.0.1:8091/aria", content=f"{len(changes)} site(s) changed: {', '.join(changes)}".encode(), headers={"Title": "ARIA Web Monitor"}, timeout=5)
        except: pass
    return changes

def list_sites():
    monitors = _load_monitors()
    if not monitors["sites"]:
        print(f"{Y}No sites being monitored.{X}")
        return
    print(f"{C}{B}Monitored Sites ({len(monitors['sites'])}){X}")
    for s in monitors["sites"]:
        print(f"  {B}{s['name']}{X}")
        print(f"    {D}{s['url']}{X}")
        print(f"    {D}Last check: {s.get('last_check','Never')[:19]}{X}")

def scrape(url, question=None):
    print(f"{D}Fetching: {url}{X}")
    content = _fetch_page(url)
    if not content:
        print(f"{R}Could not fetch page.{X}")
        return ""
    if question:
        return _query_llm(f"Based on this webpage, answer: {question}\n\nCONTENT:\n{content[:4000]}")
    else:
        return _query_llm(f"Summarize the key information from this webpage:\n\n{content[:4000]}")
