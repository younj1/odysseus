"""ARIA CLI — Git helper commands."""

import sys
import os
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class Colors:
    CYAN = "[96m"
    GREEN = "[92m"
    YELLOW = "[93m"
    RED = "[91m"
    BOLD = "[1m"
    DIM = "[2m"
    RESET = "[0m"


def _run(cmd, cwd=None):
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.stdout.strip()


def _query_llm(prompt, model="qwen2.5-coder:7b"):
    import httpx
    try:
        resp = httpx.post(
            "http://172.19.16.1:11434/api/chat",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 1000, "think": False},
            },
            timeout=120,
        )
        if resp.status_code == 200:
            return resp.json().get("message", {}).get("content", "").strip()
    except Exception as e:
        print(f"{Colors.RED}LLM error: {e}{Colors.RESET}")
    return ""


def git_commit_msg(repo_path="."):
    """Generate a commit message from staged changes."""
    diff = _run(["git", "diff", "--cached"], cwd=repo_path)
    if not diff:
        print(f"{Colors.YELLOW}No staged changes. Stage files with 'git add' first.{Colors.RESET}")
        return

    print(f"{Colors.CYAN}Analyzing staged changes...{Colors.RESET}")

    prompt = f"""Generate a git commit message using conventional commit format.
Type(scope): description. Types: feat, fix, docs, style, refactor, test, chore.
Keep the first line under 72 chars.

DIFF:
{diff[:3000]}

Return ONLY the commit message:"""

    message = _query_llm(prompt)
    if message:
        print(f"\n{Colors.GREEN}{Colors.BOLD}Suggested commit message:{Colors.RESET}")
        print(f"\n  {message}")
        print(f"\n{Colors.DIM}To use: git commit -m \"{message.split(chr(10))[0]}\"{Colors.RESET}")


def git_scan(repo_path="."):
    """Security scan staged changes."""
    import re
    diff = _run(["git", "diff", "--cached"], cwd=repo_path)
    if not diff:
        diff = _run(["git", "diff"], cwd=repo_path)
    if not diff:
        print(f"{Colors.GREEN}No changes to scan.{Colors.RESET}")
        return

    print(f"{Colors.CYAN}Scanning for security issues...{Colors.RESET}")
    patterns = [
        (r"password\s*=\s*[\"\'][^\"\']+[\"\']", "Hardcoded password"),
        (r"api_key\s*=\s*[\"\'][^\"\']+[\"\']", "Hardcoded API key"),
        (r"SECRET\s*=\s*[\"\'][^\"\']+[\"\']", "Hardcoded secret"),
        (r"eval\s*\(", "eval() usage"),
        (r"exec\s*\(", "exec() usage"),
        (r"os\.system\s*\(", "os.system() usage"),
        (r"http://(?!localhost|127\.0\.0\.1)", "Non-HTTPS URL"),
    ]
    issues = []
    for i, line in enumerate(diff.split("\n")):
        if line.startswith("+") and not line.startswith("+++"):
            for pattern, desc in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    issues.append((i, desc, line[:100]))

    if issues:
        print(f"\n{Colors.RED}{Colors.BOLD}Found {len(issues)} security issues:{Colors.RESET}\n")
        for line_num, desc, line in issues:
            print(f"  {Colors.YELLOW}[WARNING]{Colors.RESET} {desc}")
            print(f"  {Colors.DIM}{line}{Colors.RESET}\n")
    else:
        print(f"\n{Colors.GREEN}No security issues found. Safe to push!{Colors.RESET}")


def git_pr(repo_path=".", base="main"):
    """Generate a PR summary."""
    branch = _run(["git", "branch", "--show-current"], cwd=repo_path)
    diff = _run(["git", "diff", f"{base}...{branch}"], cwd=repo_path)
    log = _run(["git", "log", f"{base}...{branch}", "--oneline"], cwd=repo_path)

    if not diff:
        print(f"{Colors.YELLOW}No differences between {branch} and {base}.{Colors.RESET}")
        return

    print(f"{Colors.CYAN}Generating PR summary for {branch} -> {base}...{Colors.RESET}")

    prompt = f"""Generate a pull request summary for merging '{branch}' into '{base}'.

COMMITS:
{log[:1000]}

DIFF:
{diff[:3000]}

Format with ## Summary, ## Changes, ## Testing sections.
Return ONLY the PR summary:"""

    summary = _query_llm(prompt)
    if summary:
        print(f"\n{summary}")
