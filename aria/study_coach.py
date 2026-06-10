import json, os, time, random, logging, httpx
from datetime import datetime, date, timedelta
from aria.aria_config import get_config
from aria.vault.obsidian_client import ObsidianClient

logger = logging.getLogger(__name__)
OLLAMA_URL = "http://172.19.16.1:11434"
PROGRESS_FILE = "data/study_progress.json"

def _query_llm(prompt, model="qwen3:8b"):
    try:
        resp = httpx.post(f"{OLLAMA_URL}/api/chat", json={"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False, "options": {"temperature": 0.7, "num_predict": 1500, "think": False}}, timeout=120)
        if resp.status_code == 200: return resp.json().get("message", {}).get("content", "").strip()
    except Exception as e: logger.error(f"LLM error: {e}")
    return ""

def _get_client():
    config = get_config()
    obs = config.get("obsidian", {})
    return ObsidianClient(base_url=obs.get("api_url","http://172.19.16.1:27123"), api_key=obs.get("api_key",""))

def _load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f: return json.load(f)
    return {"cards": {}, "sessions": [], "stats": {"total_reviews": 0, "correct": 0, "streak": 0}}

def _save_progress(progress):
    os.makedirs(os.path.dirname(PROGRESS_FILE), exist_ok=True)
    with open(PROGRESS_FILE, "w") as f: json.dump(progress, f, indent=2)

def _sm2_update(card, quality):
    """SM-2 spaced repetition algorithm. quality: 0-5 (0=forgot, 5=perfect)"""
    if quality < 3:
        card["repetitions"] = 0
        card["interval"] = 1
    else:
        if card["repetitions"] == 0: card["interval"] = 1
        elif card["repetitions"] == 1: card["interval"] = 6
        else: card["interval"] = round(card["interval"] * card["ease_factor"])
        card["repetitions"] += 1
    card["ease_factor"] = max(1.3, card["ease_factor"] + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
    card["next_review"] = (date.today() + timedelta(days=card["interval"])).isoformat()
    card["last_reviewed"] = date.today().isoformat()
    return card

def generate_cards(topic=None):
    """Generate flashcards from vault notes."""
    client = _get_client()
    progress = _load_progress()
    notes = client.list_files("Knowledge")
    generated = 0
    for f in notes:
        if not f.endswith(".md"): continue
        if topic and topic.lower() not in f.lower(): continue
        note_path = f"Knowledge/{f}"
        content = client.get_note(note_path)
        if not content or len(content) < 100: continue
        title = f.replace(".md", "")
        if any(c.get("source") == note_path for c in progress["cards"].values()):
            continue
        prompt = f"Generate 3-5 flashcard questions from this note. Each card tests a specific fact or concept.\n\nNOTE: {title}\n{content[:2000]}\n\nReturn ONLY a JSON array of objects with 'question' and 'answer' fields. Example: [{{\"question\": \"What is X?\", \"answer\": \"X is...\"}}]"
        response = _query_llm(prompt)
        try:
            clean = response.replace("\n", " ")
            start = clean.find("[")
            end = clean.rfind("]") + 1
            if start >= 0 and end > start:
                cards = json.loads(clean[start:end])
                for card in cards:
                    card_id = f"{title}_{len(progress['cards'])}"
                    progress["cards"][card_id] = {"question": card["question"], "answer": card["answer"], "source": note_path, "topic": title, "ease_factor": 2.5, "interval": 1, "repetitions": 0, "next_review": date.today().isoformat(), "last_reviewed": None, "times_correct": 0, "times_wrong": 0}
                    generated += 1
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Card parse error for {title}: {e}")
    _save_progress(progress)
    return generated

def get_due_cards(limit=10):
    """Get cards due for review today."""
    progress = _load_progress()
    today = date.today().isoformat()
    due = []
    for card_id, card in progress["cards"].items():
        if card.get("next_review", "") <= today:
            due.append((card_id, card))
    random.shuffle(due)
    return due[:limit]

def review_card(card_id, quality):
    """Record a review result. quality: 1=forgot, 3=hard, 4=good, 5=easy"""
    progress = _load_progress()
    if card_id not in progress["cards"]: return False
    card = progress["cards"][card_id]
    card = _sm2_update(card, quality)
    if quality >= 3: card["times_correct"] = card.get("times_correct", 0) + 1
    else: card["times_wrong"] = card.get("times_wrong", 0) + 1
    progress["cards"][card_id] = card
    progress["stats"]["total_reviews"] += 1
    if quality >= 3: progress["stats"]["correct"] += 1
    _save_progress(progress)
    return True

def get_stats():
    """Get study statistics."""
    progress = _load_progress()
    total = len(progress["cards"])
    today = date.today().isoformat()
    due = sum(1 for c in progress["cards"].values() if c.get("next_review", "") <= today)
    mastered = sum(1 for c in progress["cards"].values() if c.get("repetitions", 0) >= 5)
    stats = progress.get("stats", {})
    topics = {}
    for c in progress["cards"].values():
        t = c.get("topic", "Unknown")
        if t not in topics: topics[t] = {"total": 0, "due": 0, "mastered": 0}
        topics[t]["total"] += 1
        if c.get("next_review", "") <= today: topics[t]["due"] += 1
        if c.get("repetitions", 0) >= 5: topics[t]["mastered"] += 1
    return {"total_cards": total, "due_today": due, "mastered": mastered, "total_reviews": stats.get("total_reviews", 0), "accuracy": round(stats.get("correct", 0) / max(stats.get("total_reviews", 1), 1) * 100, 1), "topics": topics}

def run_session(limit=10):
    """Run an interactive study session."""
    C = "\033[96m"; G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"; B = "\033[1m"; D = "\033[2m"; X = "\033[0m"
    due = get_due_cards(limit)
    if not due:
        print(f"{G}No cards due for review! Generate more with: aria study generate{X}")
        return
    print(f"\n{C}{B}ARIA Study Session{X}")
    print(f"{D}{len(due)} cards due for review{X}\n")
    correct = 0
    total = 0
    for card_id, card in due:
        total += 1
        print(f"{B}[{total}/{len(due)}] {card['question']}{X}")
        print(f"{D}Topic: {card.get('topic', 'Unknown')}{X}")
        input(f"\n{Y}Press Enter to reveal answer...{X}")
        print(f"\n{G}{card['answer']}{X}\n")
        while True:
            rating = input(f"Rate: {R}1=forgot{X} {Y}3=hard{X} {G}4=good{X} {C}5=easy{X} > ").strip()
            if rating in ("1", "2", "3", "4", "5"): break
            print("Enter 1-5")
        quality = int(rating)
        review_card(card_id, quality)
        if quality >= 3: correct += 1
        print()
    pct = round(correct / max(total, 1) * 100)
    print(f"\n{B}Session Complete!{X}")
    print(f"  Score: {correct}/{total} ({pct}%)")
    if pct >= 80: print(f"  {G}Great job!{X}")
    elif pct >= 60: print(f"  {Y}Keep practicing!{X}")
    else: print(f"  {R}Review these topics again soon.{X}")
