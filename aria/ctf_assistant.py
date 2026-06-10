"""ARIA CTF/Lab Assistant — Helps during security challenges."""

import json, os, logging, httpx, subprocess
from datetime import datetime, date
from aria.aria_config import get_config
from aria.vault.obsidian_client import ObsidianClient

logger = logging.getLogger(__name__)
OLLAMA_URL = "http://172.19.16.1:11434"
CTF_LOG_FILE = "data/ctf_sessions.json"

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

def _load_sessions():
    if os.path.exists(CTF_LOG_FILE):
        with open(CTF_LOG_FILE, "r") as f: return json.load(f)
    return {"sessions": [], "challenges_completed": []}

def _save_sessions(data):
    os.makedirs(os.path.dirname(CTF_LOG_FILE), exist_ok=True)
    with open(CTF_LOG_FILE, "w") as f: json.dump(data, f, indent=2)

def hint(challenge_type, difficulty="low", context=""):
    """Get a hint for a CTF challenge without giving away the answer."""
    prompt = f"""I'm practicing on a {challenge_type} challenge at {difficulty} security level.

Context: {context if context else 'DVWA or similar vulnerable web app'}

Give me a HINT — not the answer. Guide my thinking:
1. What should I look for?
2. What tool or technique should I try?
3. What's the general approach?

Be educational. Help me learn, don't just solve it."""
    return _query_llm(prompt)

def explain_tool(tool_name, command=""):
    """Explain what a security tool does and how to use it."""
    prompt = f"Explain the security tool '{tool_name}' briefly."
    if command:
        prompt = f"Explain this command and its output:\n\n{command}\n\nWhat does each flag do? What should I look for in the results?"
    return _query_llm(prompt)

def analyze_output(tool_output, tool_name=""):
    """Analyze output from a security tool."""
    prompt = f"""Analyze this {tool_name or 'security tool'} output. What are the key findings?

OUTPUT:
{tool_output[:2000]}

Identify:
1. Important findings
2. Potential vulnerabilities
3. Next steps to investigate"""
    return _query_llm(prompt)

def generate_writeup(challenge_name, challenge_type, steps, findings):
    """Generate a CTF writeup and save to Obsidian."""
    prompt = f"""Generate a CTF writeup in markdown format.

Challenge: {challenge_name}
Type: {challenge_type}
Steps taken: {steps}
Findings: {findings}

Format with sections: Overview, Methodology, Findings, Remediation, Lessons Learned."""
    writeup = _query_llm(prompt)
    if writeup:
        client = _get_client()
        if client.health():
            note = f"---\ntags:\n  - cybersecurity\n  - ctf\n  - {challenge_type}\n  - writeup\ndate: {date.today().isoformat()}\n---\n\n{writeup}"
            path = f"Knowledge/CTF-Writeups/{date.today().isoformat()}-{challenge_name.replace(' ','-')}.md"
            client.save_note(path, note)
            logger.info(f"Writeup saved: {path}")
    return writeup

def dvwa_guide(vulnerability_type, level="low"):
    """Get a guided walkthrough for a DVWA challenge."""
    prompt = f"""Guide me through exploiting {vulnerability_type} on DVWA at {level} security level.

Structure your response as:
1. **Setup**: What to check/configure first
2. **Reconnaissance**: How to identify the vulnerability
3. **Exploitation**: Step-by-step attack (educational)
4. **What to observe**: What the successful exploit looks like
5. **Defense**: How to fix this vulnerability
6. **Try next**: What to try at medium/high security

Be detailed and educational. This is for authorized lab practice."""
    return _query_llm(prompt)

def interactive_session():
    """Run an interactive CTF assistance session."""
    C = "\033[96m"; G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"; B = "\033[1m"; D = "\033[2m"; X = "\033[0m"
    print(f"\n{C}{B}ARIA CTF Assistant{X}")
    print(f"{D}Commands: hint, explain, analyze, dvwa, writeup, quit{X}\n")
    session_log = []
    while True:
        try:
            cmd = input(f"{G}{B}ctf > {X}").strip().lower()
            if not cmd: continue
            if cmd in ("quit", "exit", "q"): break
            elif cmd == "hint":
                ctype = input(f"  Challenge type (sqli/xss/rce/csrf/upload/other): ").strip()
                level = input(f"  Difficulty (low/medium/high): ").strip() or "low"
                context = input(f"  Additional context (optional): ").strip()
                result = hint(ctype, level, context)
                print(f"\n{C}{result}{X}\n")
                session_log.append(f"Hint: {ctype} ({level})")
            elif cmd == "explain":
                tool = input(f"  Tool or command: ").strip()
                result = explain_tool(tool)
                print(f"\n{C}{result}{X}\n")
                session_log.append(f"Explain: {tool}")
            elif cmd == "analyze":
                print(f"  Paste tool output (empty line to finish):")
                lines = []
                while True:
                    line = input()
                    if not line: break
                    lines.append(line)
                output = "\n".join(lines)
                tool = input(f"  Tool name (optional): ").strip()
                result = analyze_output(output, tool)
                print(f"\n{C}{result}{X}\n")
                session_log.append(f"Analyze: {tool or 'output'}")
            elif cmd == "dvwa":
                vuln = input(f"  Vulnerability (sqli/xss/csrf/command-injection/file-upload/file-inclusion): ").strip()
                level = input(f"  Security level (low/medium/high): ").strip() or "low"
                result = dvwa_guide(vuln, level)
                print(f"\n{C}{result}{X}\n")
                session_log.append(f"DVWA: {vuln} ({level})")
            elif cmd == "writeup":
                name = input(f"  Challenge name: ").strip()
                ctype = input(f"  Type (sqli/xss/etc): ").strip()
                steps = input(f"  Steps taken (brief): ").strip()
                findings = input(f"  Key findings: ").strip()
                result = generate_writeup(name, ctype, steps, findings)
                if result:
                    print(f"\n{G}Writeup generated and saved to vault!{X}")
                    print(f"\n{C}{result[:500]}...{X}\n")
                session_log.append(f"Writeup: {name}")
            else:
                result = _query_llm(f"I'm doing a CTF/security lab. Help with: {cmd}")
                print(f"\n{C}{result}{X}\n")
        except KeyboardInterrupt:
            print(f"\n{D}CTF session ended.{X}")
            break
    if session_log:
        data = _load_sessions()
        data["sessions"].append({"date": date.today().isoformat(), "actions": session_log})
        _save_sessions(data)
        print(f"{D}Session logged ({len(session_log)} actions).{X}")
