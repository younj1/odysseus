"""ARIA Personal API Gateway — Natural language interface to everything."""

import json, os, logging, httpx, re
from datetime import datetime, date

logger = logging.getLogger(__name__)
OLLAMA_URL = os.environ.get("ARIA_OLLAMA_URL", "http://172.19.16.1:11434")
ODYSSEUS_URL = "http://127.0.0.1:7000"

C = "\033[96m"; G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"; B = "\033[1m"; D = "\033[2m"; X = "\033[0m"

def _query_llm(prompt, model="qwen3:8b"):
    try:
        resp = httpx.post(f"{OLLAMA_URL}/api/chat", json={"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False, "options": {"temperature": 0.2, "num_predict": 500}}, timeout=60)
        if resp.status_code == 200:
            content = resp.json().get("message", {}).get("content", "").strip()
            if "<think>" in content:
                end = content.find("</think>")
                if end > 0: content = content[end + 8:].strip()
            return content
    except: pass
    return ""

def _classify_intent(command):
    """Classify a natural language command into an action."""
    prompt = f"""Classify this command into exactly one category. Return ONLY the category name.

Categories:
- note: creating or saving a note to Obsidian
- search_vault: searching for information in notes
- task: creating or checking tasks/todos
- study: study related (flashcards, review, quiz)
- fitness: workout or fitness related
- invest: investment or portfolio related
- weather: weather questions
- monitor: checking or adding website monitors
- research: research a topic in depth
- system: system status, services, docker
- pdf: reading or analyzing a PDF
- git: git operations
- briefing: daily briefing
- chat: general conversation or question

COMMAND: {command}

CATEGORY:"""
    result = _query_llm(prompt, model="qwen2.5-coder:7b")
    clean = result.strip().lower().split()[0] if result else "chat"
    clean = re.sub(r"[^a-z_]", "", clean)
    return clean

def _handle_note(command):
    from aria.vault.obsidian_client import ObsidianClient
    from aria.aria_config import get_config
    config = get_config()
    obs = config.get("obsidian", {})
    client = ObsidianClient(base_url=obs.get("api_url","http://172.19.16.1:27123"), api_key=obs.get("api_key",""))
    prompt = f"""Extract the note title and content from this command. Return JSON with "title" and "content" fields.
COMMAND: {command}
Return ONLY JSON:"""
    resp = _query_llm(prompt, model="qwen2.5-coder:7b")
    try:
        clean = resp.replace("\n", " ")
        s = clean.find("{")
        e = clean.rfind("}") + 1
        if s >= 0 and e > s:
            data = json.loads(clean[s:e])
            title = data.get("title", "Untitled").replace(" ", "-")
            content = data.get("content", command)
            path = f"Inbox/{title}.md"
            fm = f"---\ntags:\n  - capture\ndate: {date.today().isoformat()}\naria_created: true\n---\n\n# {data.get('title','Untitled')}\n\n{content}"
            if client.save_note(path, fm):
                return f"Note saved: {path}"
    except: pass
    return "Could not create note."

def _handle_search(command):
    from aria.vault.obsidian_client import ObsidianClient
    from aria.aria_config import get_config
    config = get_config()
    obs = config.get("obsidian", {})
    client = ObsidianClient(base_url=obs.get("api_url","http://172.19.16.1:27123"), api_key=obs.get("api_key",""))
    query = command.replace("search", "").replace("find", "").replace("look up", "").strip()
    results = client.search(query)
    if results:
        output = f"Found {len(results)} results:\n"
        for r in results[:5]:
            output += f"  - {r.get('filename', 'unknown')}\n"
        return output
    return f"No results found for: {query}"

def _handle_task(command):
    from aria.vault.obsidian_client import ObsidianClient
    from aria.aria_config import get_config
    config = get_config()
    obs = config.get("obsidian", {})
    client = ObsidianClient(base_url=obs.get("api_url","http://172.19.16.1:27123"), api_key=obs.get("api_key",""))
    task_text = command.replace("add task", "").replace("create task", "").replace("todo", "").replace("remind me to", "").strip()
    existing = client.get_note("Tasks/Active.md")
    if existing:
        new_content = existing.rstrip() + f"\n- [ ] {task_text} (added {date.today().isoformat()})\n"
        if client.save_note("Tasks/Active.md", new_content):
            return f"Task added: {task_text}"
    else:
        content = f"---\ntags:\n  - tasks\n---\n\n# Active Tasks\n\n- [ ] {task_text} (added {date.today().isoformat()})\n"
        if client.save_note("Tasks/Active.md", content):
            return f"Task added: {task_text}"
    return "Could not add task."

def _handle_study(command):
    from aria.study_coach import get_stats, get_due_cards
    stats = get_stats()
    return f"Study stats: {stats['total_cards']} cards, {stats['due_today']} due today, {stats['accuracy']}% accuracy. Run 'aria study review' to start a session."

def _handle_fitness(command):
    from aria.fitness_coach import get_stats
    stats = get_stats()
    return f"Fitness: {stats['total_workouts']} workouts, {stats['streak']} day streak. Last workout: {stats['last_workout'] or 'Never'}. Run 'aria fitness log' to log a workout."

def _handle_invest(command):
    from aria.investment_tracker import get_portfolio_summary
    summary = get_portfolio_summary()
    if summary["holdings"]:
        holdings = ", ".join(f"{h['symbol']} (${h['value']:,.0f})" for h in summary["holdings"])
        return f"Portfolio: ${summary['total_value']:,.2f} total ({summary['total_gain_pct']:+.1f}%). Holdings: {holdings}"
    return "No holdings. Add with: aria invest add SYMBOL SHARES COST"

def _handle_system(command):
    from aria.homelab import check_services
    services = check_services()
    online = sum(1 for s in services if s["status"] == "online")
    return f"System: {online}/{len(services)} services online. Run 'aria dashboard' for full view."

def _handle_chat(command):
    return _query_llm(command, model="qwen3:8b")

HANDLERS = {
    "note": _handle_note,
    "search_vault": _handle_search,
    "task": _handle_task,
    "study": _handle_study,
    "fitness": _handle_fitness,
    "invest": _handle_invest,
    "system": _handle_system,
    "chat": _handle_chat,
}

def process_command(command):
    """Process a natural language command through the gateway."""
    print(f"{D}Classifying intent...{X}")
    intent = _classify_intent(command)
    print(f"{D}Intent: {intent}{X}")
    handler = HANDLERS.get(intent, _handle_chat)
    result = handler(command)
    return result

def interactive_gateway():
    """Run interactive natural language gateway."""
    print(f"""
{C}{B}+========================================+
|       ARIA Personal Gateway            |
|   Tell me what you need in plain English|
+========================================+{X}
{D}Examples:
  "Save a note about Docker networking"
  "Add task: review security report by Friday"
  "How are my investments doing?"
  "How many study cards are due?"
  "Check system status"
  "What did I write about buffer overflows?"
Type 'quit' to exit.{X}
""")
    while True:
        try:
            cmd = input(f"{G}{B}> {X}").strip()
            if not cmd: continue
            if cmd.lower() in ("quit", "exit", "q"): break
            result = process_command(cmd)
            print(f"\n{C}{result}{X}\n")
        except KeyboardInterrupt:
            print(f"\n{D}Gateway closed.{X}")
            break
