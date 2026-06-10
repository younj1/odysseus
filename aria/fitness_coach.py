import json, os, logging, httpx
from datetime import datetime, date
from aria.aria_config import get_config
from aria.vault.obsidian_client import ObsidianClient

logger = logging.getLogger(__name__)
OLLAMA_URL = "http://172.19.16.1:11434"
FITNESS_FILE = "data/fitness_log.json"

def _query_llm(prompt, model="qwen3:8b"):
    try:
        resp = httpx.post(f"{OLLAMA_URL}/api/chat", json={"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False, "options": {"temperature": 0.5, "num_predict": 2000, "think": False}}, timeout=120)
        if resp.status_code == 200: return resp.json().get("message", {}).get("content", "").strip()
    except Exception as e: logger.error(f"LLM error: {e}")
    return ""

def _get_client():
    config = get_config()
    obs = config.get("obsidian", {})
    return ObsidianClient(base_url=obs.get("api_url","http://172.19.16.1:27123"), api_key=obs.get("api_key",""))

def _load_log():
    if os.path.exists(FITNESS_FILE):
        with open(FITNESS_FILE, "r") as f: return json.load(f)
    return {"workouts": [], "goals": {}, "stats": {"total_workouts": 0, "streak": 0, "last_workout": None}}

def _save_log(log):
    os.makedirs(os.path.dirname(FITNESS_FILE), exist_ok=True)
    with open(FITNESS_FILE, "w") as f: json.dump(log, f, indent=2)

def log_workout(workout_type, exercises=None, duration=None, notes=None):
    """Log a workout session."""
    log = _load_log()
    entry = {"date": date.today().isoformat(), "type": workout_type, "exercises": exercises or [], "duration_min": duration, "notes": notes, "timestamp": datetime.now().isoformat()}
    log["workouts"].append(entry)
    log["stats"]["total_workouts"] += 1
    last = log["stats"].get("last_workout")
    if last and (date.today() - date.fromisoformat(last)).days <= 2:
        log["stats"]["streak"] += 1
    else:
        log["stats"]["streak"] = 1
    log["stats"]["last_workout"] = date.today().isoformat()
    _save_log(log)
    # Save to Obsidian
    client = _get_client()
    if client.health():
        md = f"---\ntags:\n  - fitness\n  - workout\n  - {workout_type}\ndate: {date.today().isoformat()}\n---\n\n# Workout — {date.today().isoformat()}\n\n**Type:** {workout_type}\n"
        if duration: md += f"**Duration:** {duration} minutes\n"
        if exercises:
            md += "\n## Exercises\n"
            for ex in exercises:
                if isinstance(ex, dict): md += f"- {ex.get('name','')}: {ex.get('sets','')}x{ex.get('reps','')} @ {ex.get('weight','')}\n"
                else: md += f"- {ex}\n"
        if notes: md += f"\n## Notes\n{notes}\n"
        client.save_note(f"Daily/{date.today().isoformat()}-workout.md", md)
    return entry

def get_stats():
    """Get fitness statistics."""
    log = _load_log()
    stats = log.get("stats", {})
    recent = log["workouts"][-10:] if log["workouts"] else []
    types = {}
    for w in log["workouts"]:
        t = w.get("type", "other")
        types[t] = types.get(t, 0) + 1
    return {"total_workouts": stats.get("total_workouts", 0), "streak": stats.get("streak", 0), "last_workout": stats.get("last_workout"), "workout_types": types, "recent": recent}

def generate_plan(goal="general fitness", days=7):
    """Generate a training plan using ARIA."""
    client = _get_client()
    vault_context = ""
    for note_name in ["Knowledge/Training.md", "Knowledge/Mma.md"]:
        content = client.get_note(note_name)
        if content: vault_context += f"\n{content[:500]}"
    log = _load_log()
    recent = log["workouts"][-5:]
    recent_text = json.dumps(recent, indent=2) if recent else "No recent workouts"
    prompt = f"Generate a {days}-day training plan.\n\nGOAL: {goal}\n\nPREVIOUS TRAINING NOTES:\n{vault_context[:1000]}\n\nRECENT WORKOUTS:\n{recent_text}\n\nCreate a detailed plan with specific exercises, sets, reps, and rest days. Format as clean markdown."
    plan = _query_llm(prompt)
    if plan and client.health():
        note = f"---\ntags:\n  - fitness\n  - training\n  - plan\ndate: {date.today().isoformat()}\n---\n\n{plan}"
        client.save_note(f"Daily/{date.today().isoformat()}-training-plan.md", note)
    return plan

def interactive_log():
    """Interactive workout logging."""
    C = "\033[96m"; G = "\033[92m"; Y = "\033[93m"; B = "\033[1m"; D = "\033[2m"; X = "\033[0m"
    print(f"\n{C}{B}ARIA Workout Logger{X}")
    wtype = input(f"Workout type (mma/lifting/cardio/other): ").strip() or "other"
    duration = input(f"Duration in minutes: ").strip()
    duration = int(duration) if duration.isdigit() else None
    exercises = []
    print(f"{D}Add exercises (empty line to finish):{X}")
    while True:
        ex = input(f"  Exercise (e.g. 'bench press 3x10 185lbs'): ").strip()
        if not ex: break
        exercises.append(ex)
    notes = input(f"Notes (optional): ").strip() or None
    entry = log_workout(wtype, exercises, duration, notes)
    print(f"\n{G}Workout logged!{X}")
    stats = get_stats()
    print(f"  Streak: {stats['streak']} days")
    print(f"  Total workouts: {stats['total_workouts']}")
