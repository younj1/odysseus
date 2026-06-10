"""ARIA Autonomous Research Agent — Deep research on any topic, saves to vault."""

import json, logging, httpx, time
from datetime import date
from aria.aria_config import get_config
from aria.vault.obsidian_client import ObsidianClient

logger = logging.getLogger(__name__)
OLLAMA_URL = "http://172.19.16.1:11434"
SEARXNG_URL = "http://127.0.0.1:8080"

C = "\033[96m"; G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"; B = "\033[1m"; D = "\033[2m"; X = "\033[0m"

def _query_llm(prompt, model="qwen3:8b"):
    try:
        resp = httpx.post(f"{OLLAMA_URL}/api/chat", json={"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False, "options": {"temperature": 0.4, "num_predict": 3000}, "think": False}, timeout=180)
        if resp.status_code == 200: return resp.json().get("message", {}).get("content", "").strip()
    except Exception as e: logger.error(f"LLM error: {e}")
    return ""

def _search(query, count=5, category="general"):
    try:
        resp = httpx.get(f"{SEARXNG_URL}/search", params={"q": query, "format": "json", "categories": category}, timeout=15)
        if resp.status_code == 200:
            return resp.json().get("results", [])[:count]
    except Exception as e: logger.error(f"Search error: {e}")
    return []

def _fetch_page(url):
    try:
        resp = httpx.get(url, timeout=15, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200:
            text = resp.text
            # Basic HTML stripping
            import re
            text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL)
            text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:5000]
    except: pass
    return ""

def _get_client():
    config = get_config()
    obs = config.get("obsidian", {})
    return ObsidianClient(base_url=obs.get("api_url","http://172.19.16.1:27123"), api_key=obs.get("api_key",""))

def research(topic, depth="standard", save_to_vault=True):
    """Run autonomous research on a topic.
    depth: quick (3 searches), standard (5), deep (8+)
    """
    print(f"\n{C}{B}ARIA Research Agent{X}")
    print(f"{D}Topic: {topic}{X}")
    print(f"{D}Depth: {depth}{X}\n")

    search_rounds = {"quick": 3, "standard": 5, "deep": 8}.get(depth, 5)

    # Step 1: Generate search queries
    print(f"{Y}Step 1: Planning research queries...{X}")
    query_prompt = f"Generate {search_rounds} diverse search queries to thoroughly research this topic: {topic}\n\nReturn ONLY a JSON array of query strings. Example: [\"query 1\", \"query 2\"]"
    query_response = _query_llm(query_prompt, model="nemotron-3-nano:4b")
    queries = [topic]
    try:
        clean = query_response.replace("\n", " ")
        start = clean.find("[")
        end = clean.rfind("]") + 1
        if start >= 0 and end > start:
            parsed = json.loads(clean[start:end])
            queries = [q for q in parsed if isinstance(q, str)][:search_rounds]
    except: pass
    print(f"  Generated {len(queries)} search queries")

    # Step 2: Search and collect sources
    print(f"\n{Y}Step 2: Searching the web...{X}")
    all_results = []
    sources = []
    for i, query in enumerate(queries):
        print(f"  [{i+1}/{len(queries)}] Searching: {query[:60]}...")
        results = _search(query, count=3)
        for r in results:
            title = r.get("title", "")
            url = r.get("url", "")
            snippet = r.get("content", "")[:300]
            if url and not any(s["url"] == url for s in sources):
                sources.append({"title": title, "url": url, "snippet": snippet})
                all_results.append(r)
    print(f"  Found {len(sources)} unique sources")

    # Step 3: Fetch and extract content from top sources
    print(f"\n{Y}Step 3: Reading top sources...{X}")
    detailed_content = []
    for i, source in enumerate(sources[:6]):
        print(f"  [{i+1}] Reading: {source['title'][:50]}...")
        page_text = _fetch_page(source["url"])
        if page_text:
            # Summarize each source
            summary = _query_llm(f"Summarize the key points from this webpage about '{topic}':\n\n{page_text[:3000]}\n\nProvide 3-5 bullet points of the most important information:")
            if summary:
                detailed_content.append({"title": source["title"], "url": source["url"], "summary": summary})

    # Step 4: Synthesize findings
    print(f"\n{Y}Step 4: Synthesizing findings...{X}")
    source_text = ""
    for dc in detailed_content:
        source_text += f"\nSource: {dc['title']}\nURL: {dc['url']}\n{dc['summary']}\n---"

    synthesis_prompt = f"""You are a research analyst. Synthesize these findings into a comprehensive research report.

TOPIC: {topic}

SOURCES AND FINDINGS:
{source_text[:4000]}

Write a well-structured markdown report with:
# Research Report: {topic}
## Executive Summary (2-3 sentences)
## Key Findings (organized by theme)
## Analysis (your synthesis of the findings)
## Sources (list with URLs)
## Further Research (what questions remain)

Be thorough, factual, and cite which sources support each finding."""

    report = _query_llm(synthesis_prompt)

    if not report:
        report = f"# Research Report: {topic}\n\n## Sources Found\n"
        for s in sources:
            report += f"- [{s['title']}]({s['url']})\n  {s['snippet']}\n\n"

    # Step 5: Save to vault
    if save_to_vault:
        print(f"\n{Y}Step 5: Saving to vault...{X}")
        client = _get_client()
        if client.health():
            tags = _query_llm(f"Suggest 3-5 tags for a research report about: {topic}. Return ONLY a JSON array like [\"tag1\", \"tag2\"]")
            tag_list = ["research"]
            try:
                clean = tags.replace("\n", " ")
                s = clean.find("[")
                e = clean.rfind("]") + 1
                if s >= 0 and e > s:
                    tag_list = json.loads(clean[s:e])
            except: pass
            tag_yaml = "\n".join(f"  - {t.lower()}" for t in tag_list)
            note = f"---\ntags:\n{tag_yaml}\ndate: {date.today().isoformat()}\naria_generated: true\ntype: research\n---\n\n{report}"
            safe_name = topic.replace(" ", "-").replace("/", "-")[:50]
            path = f"Knowledge/{date.today().isoformat()}-{safe_name}.md"
            if client.save_note(path, note):
                print(f"  {G}Saved: {path}{X}")
            else:
                print(f"  {R}Failed to save{X}")
    print(f"\n{G}{B}Research complete!{X}")
    print(f"{D}{len(sources)} sources, {len(detailed_content)} analyzed in depth{X}\n")
    return report
