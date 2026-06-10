"""
ARIA Git Helper MCP Server
Auto-generate commit messages, security scan before push, PR summaries.
"""
import asyncio
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

server = Server("aria-git-helper")

OLLAMA_URL = "http://172.19.16.1:11434"


def _run_cmd(cmd: list, timeout: int = 30, cwd: str = None) -> str:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
        return (result.stdout + result.stderr).strip()
    except FileNotFoundError:
        return f"Command not found: {cmd[0]}"
    except Exception as e:
        return f"Error: {e}"


def _query_llm(prompt: str, model: str = "qwen3:8b") -> str:
    try:
        import httpx
        resp = httpx.post(
            f"{OLLAMA_URL}/api/chat",
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
        return ""
    except Exception as e:
        return f"LLM error: {e}"


def _get_diff(cwd: str = None, staged: bool = True) -> str:
    if staged:
        return _run_cmd(["git", "diff", "--cached"], cwd=cwd)
    return _run_cmd(["git", "diff"], cwd=cwd)


def _get_log(cwd: str = None, count: int = 10) -> str:
    return _run_cmd(["git", "log", f"--oneline", f"-{count}"], cwd=cwd)


def _get_status(cwd: str = None) -> str:
    return _run_cmd(["git", "status", "--short"], cwd=cwd)


def _get_branch(cwd: str = None) -> str:
    return _run_cmd(["git", "branch", "--show-current"], cwd=cwd)


def _scan_diff_for_security(diff: str) -> list:
    issues = []
    patterns = [
        (r"password\s*=\s*["'][^"']+["']", "Hardcoded password"),
        (r"api_key\s*=\s*["'][^"']+["']", "Hardcoded API key"),
        (r"SECRET\s*=\s*["'][^"']+["']", "Hardcoded secret"),
        (r"token\s*=\s*["'][A-Za-z0-9_\-]{20,}["']", "Hardcoded token"),
        (r"eval\s*\(", "eval() usage"),
        (r"exec\s*\(", "exec() usage"),
        (r"subprocess\.call\(.*shell\s*=\s*True", "shell=True in subprocess"),
        (r"os\.system\s*\(", "os.system() usage"),
        (r"pickle\.loads?\s*\(", "Pickle deserialization"),
        (r"http://(?!localhost|127\.0\.0\.1)", "Non-HTTPS URL"),
        (r"chmod\s+777", "chmod 777"),
        (r"rm\s+-rf\s+/", "Dangerous rm -rf /"),
    ]
    for i, line in enumerate(diff.split("\n")):
        if line.startswith("+") and not line.startswith("+++"):
            for pattern, desc in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    issues.append(f"Line {i}: {desc} -> {line[:100]}")
    return issues


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="generate_commit_message",
            description="Generate a commit message from staged changes (git diff --cached).",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {"type": "string", "description": "Path to the git repository", "default": "."},
                    "style": {"type": "string", "enum": ["conventional", "descriptive", "brief"], "default": "conventional"},
                },
                "required": [],
            },
        ),
        Tool(
            name="security_scan",
            description="Scan staged or unstaged changes for security issues before pushing.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {"type": "string", "description": "Path to the git repository", "default": "."},
                    "staged_only": {"type": "boolean", "description": "Only scan staged changes", "default": True},
                },
                "required": [],
            },
        ),
        Tool(
            name="pr_summary",
            description="Generate a pull request summary from the diff between current branch and main/master.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {"type": "string", "description": "Path to the git repository", "default": "."},
                    "base_branch": {"type": "string", "description": "Base branch to compare against", "default": "main"},
                },
                "required": [],
            },
        ),
        Tool(
            name="git_status",
            description="Get current git status: branch, staged/unstaged changes, recent commits.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {"type": "string", "description": "Path to the git repository", "default": "."},
                },
                "required": [],
            },
        ),
        Tool(
            name="explain_commit",
            description="Explain what a specific commit or range of commits changed.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {"type": "string", "description": "Path to the git repository", "default": "."},
                    "commit": {"type": "string", "description": "Commit hash or range (e.g. HEAD~3..HEAD)", "default": "HEAD"},
                },
                "required": [],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    repo = arguments.get("repo_path", ".")

    if name == "generate_commit_message":
        diff = _get_diff(cwd=repo, staged=True)
        if not diff:
            return [TextContent(type="text", text="No staged changes found. Stage files with 'git add' first.")]

        style = arguments.get("style", "conventional")
        style_guide = {
            "conventional": "Use conventional commit format: type(scope): description. Types: feat, fix, docs, style, refactor, test, chore. Keep the first line under 72 chars. Add a body with bullet points if needed.",
            "descriptive": "Write a clear, descriptive commit message explaining what changed and why. 1-3 sentences.",
            "brief": "Write a one-line commit message under 50 characters.",
        }

        prompt = f"""Generate a git commit message for these changes.

{style_guide.get(style, style_guide["conventional"])}

DIFF:
{diff[:3000]}

Return ONLY the commit message, no other text:"""

        message = _query_llm(prompt, model="qwen2.5-coder:7b")
        return [TextContent(type="text", text=f"Suggested commit message:\n\n{message}")]

    elif name == "security_scan":
        staged = arguments.get("staged_only", True)
        diff = _get_diff(cwd=repo, staged=staged)
        if not diff:
            return [TextContent(type="text", text="No changes to scan.")]

        issues = _scan_diff_for_security(diff)
        if issues:
            report = f"SECURITY ISSUES FOUND ({len(issues)}):\n\n"
            for issue in issues:
                report += f"  [WARNING] {issue}\n"
            report += "\nReview these before pushing!"
            return [TextContent(type="text", text=report)]
        return [TextContent(type="text", text="No security issues detected in the diff. Safe to push.")]

    elif name == "pr_summary":
        base = arguments.get("base_branch", "main")
        branch = _get_branch(cwd=repo)
        diff = _run_cmd(["git", "diff", f"{base}...{branch}"], cwd=repo)
        log = _run_cmd(["git", "log", f"{base}...{branch}", "--oneline"], cwd=repo)

        if not diff:
            return [TextContent(type="text", text=f"No differences between {branch} and {base}.")]

        prompt = f"""Generate a pull request summary for merging '{branch}' into '{base}'.

COMMITS:
{log[:1000]}

DIFF:
{diff[:3000]}

Format:
## Summary
Brief description of changes.

## Changes
- List of specific changes

## Testing
What should be tested.

Return ONLY the PR summary:"""

        summary = _query_llm(prompt, model="qwen2.5-coder:7b")
        return [TextContent(type="text", text=summary)]

    elif name == "git_status":
        branch = _get_branch(cwd=repo)
        status = _get_status(cwd=repo)
        log = _get_log(cwd=repo, count=5)

        report = f"""Repository: {os.path.abspath(repo)}
Branch: {branch}

Status:
{status or '  (clean)'}

Recent commits:
{log}"""
        return [TextContent(type="text", text=report)]

    elif name == "explain_commit":
        commit = arguments.get("commit", "HEAD")
        diff = _run_cmd(["git", "show", commit, "--stat"], cwd=repo)
        full_diff = _run_cmd(["git", "show", commit], cwd=repo)

        prompt = f"""Explain what this git commit changed in plain English.

{full_diff[:3000]}

Give a clear summary of what was changed and why:"""

        explanation = _query_llm(prompt, model="qwen2.5-coder:7b")
        return [TextContent(type="text", text=f"{diff}\n\nExplanation:\n{explanation}")]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream)


if __name__ == "__main__":
    asyncio.run(main())
