
import json, logging, httpx
from datetime import datetime, date
from aria.aria_config import get_config
from aria.vault.obsidian_client import ObsidianClient
logger = logging.getLogger(__name__)
OLLAMA_URL = "http://172.19.16.1:11434"
SEARXNG_URL = "http://127.0.0.1:8080"

def _query_llm(prompt, model="qwen3:8b"):
    try:
        resp = httpx.post(f"{OLLAMA_URL}/api/chat", json={"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False, "options": {"temperature": 0.5, "num_predict": 2000, "think": False}}, timeout=120)
        if resp.status_code == 200:
            return resp.json().get("message", {}).get("content", "").strip()
    except Exception as e:
        logger.error(f"LLM error: {e}")
    return ""

def _search_news(query, count=5):
    try:
        resp = httpx.get(f"{SEARXNG_URL}/search", params={"q": query, "format": "json", "categories": "news", "time_range": "day"}, timeout=15)
        if resp.status_code == 200:
            results = resp.json().get("results", [])
            return [{"title": r.get("title",""), "url": r.get("url",""), "content": r.get("content","")[:200]} for r in results[:count]]
    except Exception as e:
        logger.error(f"SearXNG error: {e}")
    return []

def _get_tasks(client):
    try:
        content = client.get_note("Tasks/Active.md")
        if content: return content
    except: pass
    try:
        files = client.list_files("Tasks")
        tasks = []
        for fl in files:
            if fl.endswith(".md"):
                note = client.get_note(f"Tasks/{fl}")
                if note and ("[ ]" in note or "TODO" in note):
                    tasks.append(f"### {fl.replace('.md','')}\n{note[:300]}")
        return "\n\n".join(tasks) if tasks else "No active tasks found."
    except: return "Could not read tasks."

def _get_study_progress(client):
    try:
        content = client.get_note("Knowledge/Study-Plan.md")
        if content: return content[:1000]
    except: pass
    return "No study plan found."

def generate_briefing(save_to_vault=True):
    today = date.today()
    date_str = today.strftime("%Y-%m-%d")
    day_name = today.strftime("%A")
    config = get_config()
    obs = config.get("obsidian", {})
    client = ObsidianClient(base_url=obs.get("api_url","http://172.19.16.1:27123"), api_key=obs.get("api_key",""))
    print(f"Generating briefing for {day_name}, {date_str}...")
    print("  Fetching tasks...")
    tasks = _get_tasks(client)
    print("  Fetching study progress...")
    study = _get_study_progress(client)
    print("  Searching cybersecurity news...")
    cyber_news = _search_news("cybersecurity news today")
    news_text = ""
    if cyber_news:
        for item in cyber_news:
            news_text += f"- **{item['title']}**: {item['content']} ([link]({item['url']}))\n"
    else: news_text = "Could not fetch news today."
    print("  Searching tech news...")
    tech_news = _search_news("technology AI news today")
    tech_text = ""
    if tech_news:
        for item in tech_news:
            tech_text += f"- **{item['title']}**: {item['content']} ([link]({item['url']}))\n"
    print("  Generating briefing with ARIA...")
    prompt = f"Generate a concise daily briefing for {day_name}, {date_str}.\n\nTASKS:\n{tasks[:800]}\n\nSTUDY PROGRESS:\n{study[:500]}\n\nCYBERSECURITY NEWS:\n{news_text[:1000]}\n\nTECH NEWS:\n{tech_text[:500]}\n\nFormat as markdown with sections: Priority Tasks, Study Plan, Cybersecurity News, Tech News, Focus for Today. Keep it concise. Return ONLY the markdown:"
    briefing = _query_llm(prompt)
    if not briefing:
        briefing = f"# Daily Briefing - {day_name}, {date_str}\n\n## Tasks\n{tasks[:500]}\n\n## Study\n{study[:300]}\n\n## Cyber News\n{news_text}\n\n## Tech News\n{tech_text}"
    full_note = f"---\ntags:\n  - daily\n  - briefing\ndate: {date_str}\naria_generated: true\n---\n\n{briefing}"
    print(f"  Briefing generated ({len(briefing)} chars)")
    if save_to_vault:
        note_path = f"Daily/{date_str}-briefing.md"
        if client.health():
            if client.save_note(note_path, full_note): print(f"  Saved to vault: {note_path}")
            else: print("  Failed to save to vault")
        else: print("  Obsidian not connected")
    try:
        httpx.post("http://127.0.0.1:8091/aria", content=f"Daily briefing ready for {date_str}".encode(), headers={"Title":"ARIA Daily Briefing"}, timeout=5)
        print("  Notification sent via ntfy")
    except: pass
    return briefing
