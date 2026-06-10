"""ARIA Multi-Agent System — Coordinate specialized agents for complex tasks."""

import json, logging, httpx, time
from datetime import date
from aria.aria_config import get_config

logger = logging.getLogger(__name__)
OLLAMA_URL = "http://172.19.16.1:11434"

C = "\033[96m"; G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"; B = "\033[1m"; D = "\033[2m"; X = "\033[0m"

AGENT_PROMPTS = {
    "planner": "You are a project planner. Break complex tasks into clear, ordered subtasks. Return a JSON array of subtask objects with 'task', 'agent' (coder/security/writer/researcher), and 'description' fields.",
    "coder": "You are a senior software engineer. Write clean, production-quality code. Include error handling, type hints, and comments. If you see security issues, flag them.",
    "security": "You are a cybersecurity expert. Review for vulnerabilities, suggest mitigations, and follow security best practices. Check for OWASP Top 10 issues.",
    "writer": "You are a technical writer. Create clear, well-structured documentation. Use markdown formatting with headers, code blocks, and examples.",
    "researcher": "You are a research analyst. Provide thorough, factual analysis with citations and multiple perspectives.",
}

def _query_agent(prompt, agent_type="coder", model=None):
    if model is None:
        model = "qwen2.5-coder:7b"
    system = AGENT_PROMPTS.get(agent_type, AGENT_PROMPTS["coder"])
    try:
        resp = httpx.post(f"{OLLAMA_URL}/api/chat", json={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "options": {"temperature": 0.4, "num_predict": 3000}, "think": False,
        }, timeout=180)
        if resp.status_code == 200:
            return resp.json().get("message", {}).get("content", "").strip()
    except Exception as e: logger.error(f"Agent error: {e}")
    return ""

def plan_task(task_description):
    """Break a complex task into subtasks assigned to specialized agents."""
    print(f"\n{C}{B}ARIA Multi-Agent Planner{X}")
    print(f"{D}Task: {task_description}{X}\n")
    print(f"{Y}Planning subtasks...{X}")

    prompt = f"""Break this task into 3-6 ordered subtasks. Assign each to the best agent.

TASK: {task_description}

AVAILABLE AGENTS:
- coder: writes code
- security: reviews security
- writer: writes documentation
- researcher: researches topics

Return ONLY a JSON array like:
[{{"task": "Write the API endpoint", "agent": "coder", "description": "Create a FastAPI route for..."}}]"""

    response = _query_agent(prompt, "planner")
    subtasks = []
    try:
        clean = response.replace("\n", " ")
        start = clean.find("[")
        end = clean.rfind("]") + 1
        if start >= 0 and end > start:
            subtasks = json.loads(clean[start:end])
    except Exception as e:
        logger.warning(f"Plan parse error: {e}")
        print(f"{R}Could not parse plan. Running as single task.{X}")
        subtasks = [{"task": task_description, "agent": "coder", "description": task_description}]

    print(f"\n{B}Execution Plan ({len(subtasks)} steps):{X}")
    for i, st in enumerate(subtasks, 1):
        print(f"  {i}. [{st.get('agent','coder').upper()}] {st.get('task','')}")
    print()
    return subtasks

def execute_plan(subtasks, auto=False):
    """Execute a plan by running each subtask through its assigned agent."""
    results = []
    context = ""

    for i, st in enumerate(subtasks, 1):
        agent = st.get("agent", "coder")
        task = st.get("task", "")
        desc = st.get("description", task)

        print(f"{Y}[{i}/{len(subtasks)}] {agent.upper()}: {task}{X}")

        if not auto:
            choice = input(f"  {D}Run this step? (y/n/skip): {X}").strip().lower()
            if choice in ("n", "skip"):
                results.append({"step": i, "agent": agent, "task": task, "result": "SKIPPED", "status": "skipped"})
                continue

        prompt = f"""Previous context from earlier steps:
{context[:2000]}

Current task: {desc}

Complete this task thoroughly:"""

        result = _query_agent(prompt, agent)
        results.append({"step": i, "agent": agent, "task": task, "result": result, "status": "done"})

        # Add to rolling context for next agent
        context += f"\nStep {i} ({agent}): {task}\nResult: {result[:500]}\n---"

        print(f"{G}  Done.{X}")
        if result:
            # Show first 300 chars
            preview = result[:300]
            print(f"{D}  {preview}{'...' if len(result) > 300 else ''}{X}\n")

    return results

def run_multi_agent(task_description, auto=False):
    """Plan and execute a complex task with multiple agents."""
    subtasks = plan_task(task_description)

    if not auto:
        choice = input(f"\n{B}Execute this plan? (y/n): {X}").strip().lower()
        if choice != "y":
            print(f"{D}Plan cancelled.{X}")
            return []

    print(f"\n{C}{B}Executing plan...{X}\n")
    results = execute_plan(subtasks, auto=auto)

    # Summary
    done = sum(1 for r in results if r["status"] == "done")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    print(f"\n{G}{B}Complete!{X} {done} done, {skipped} skipped")

    return results

def display_results(results):
    """Display full results from a multi-agent run."""
    for r in results:
        if r["status"] == "skipped": continue
        print(f"\n{B}Step {r['step']} — {r['agent'].upper()}: {r['task']}{X}")
        print(f"{r['result']}")
        print(f"{D}{'-'*50}{X}")
