"""
ARIA Code Analyzer MCP Server
Static analysis, dependency auditing, security checks on code files.
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

server = Server("aria-code-analyzer")


def _run_cmd(cmd: list, timeout: int = 30, cwd: str = None) -> str:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
        return (result.stdout + result.stderr).strip()
    except FileNotFoundError:
        return f"Command not found: {cmd[0]}"
    except Exception as e:
        return f"Error: {e}"


def _analyze_python(filepath: str) -> str:
    results = []
    try:
        with open(filepath, "r") as f:
            content = f.read()
            lines = content.split("\n")
    except Exception as e:
        return f"Cannot read file: {e}"

    # Basic checks
    results.append(f"File: {filepath}")
    results.append(f"Lines: {len(lines)}")

    # Security patterns
    security_issues = []
    patterns = [
        (r"eval\s*\(", "eval() usage — potential code injection"),
        (r"exec\s*\(", "exec() usage — potential code injection"),
        (r"__import__\s*\(", "Dynamic import — potential security risk"),
        (r"subprocess\.call\(.*shell\s*=\s*True", "shell=True in subprocess — command injection risk"),
        (r"os\.system\s*\(", "os.system() — prefer subprocess"),
        (r"pickle\.loads?\s*\(", "pickle usage — deserialization risk"),
        (r"password\s*=\s*["'][^"']+["']", "Hardcoded password detected"),
        (r"api_key\s*=\s*["'][^"']+["']", "Hardcoded API key detected"),
        (r"SECRET\s*=\s*["'][^"']+["']", "Hardcoded secret detected"),
        (r"http://", "HTTP (non-HTTPS) URL found"),
    ]
    for i, line in enumerate(lines, 1):
        for pattern, msg in patterns:
            if re.search(pattern, line, re.IGNORECASE):
                security_issues.append(f"  Line {i}: {msg}")

    if security_issues:
        results.append(f"\nSecurity Issues ({len(security_issues)}):")
        results.extend(security_issues)
    else:
        results.append("\nNo security issues detected.")

    # Import analysis
    imports = [l.strip() for l in lines if l.strip().startswith(("import ", "from "))]
    if imports:
        results.append(f"\nImports ({len(imports)}):")
        for imp in imports[:20]:
            results.append(f"  {imp}")

    # Function/class count
    functions = [l for l in lines if re.match(r"\s*def\s+", l)]
    classes = [l for l in lines if re.match(r"\s*class\s+", l)]
    results.append(f"\nFunctions: {len(functions)}, Classes: {len(classes)}")

    # TODO/FIXME/HACK comments
    todos = [(i, l.strip()) for i, l in enumerate(lines, 1) if re.search(r"#\s*(TODO|FIXME|HACK|XXX)", l, re.IGNORECASE)]
    if todos:
        results.append(f"\nTODO/FIXME ({len(todos)}):")
        for num, line in todos[:10]:
            results.append(f"  Line {num}: {line}")

    return "\n".join(results)


def _check_requirements(filepath: str) -> str:
    results = []
    try:
        with open(filepath, "r") as f:
            deps = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    except Exception as e:
        return f"Cannot read file: {e}"

    results.append(f"Dependencies: {len(deps)}")
    unpinned = [d for d in deps if "==" not in d and ">=" not in d and "<=" not in d]
    if unpinned:
        results.append(f"\nUnpinned dependencies ({len(unpinned)}):")
        for d in unpinned:
            results.append(f"  {d}")

    return "\n".join(results)


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="analyze_file",
            description="Analyze a Python file for security issues, code quality, and structure.",
            inputSchema={
                "type": "object",
                "properties": {"filepath": {"type": "string", "description": "Path to the Python file to analyze"}},
                "required": ["filepath"],
            },
        ),
        Tool(
            name="check_dependencies",
            description="Check a requirements.txt for unpinned or risky dependencies.",
            inputSchema={
                "type": "object",
                "properties": {"filepath": {"type": "string", "description": "Path to requirements.txt"}},
                "required": ["filepath"],
            },
        ),
        Tool(
            name="find_secrets",
            description="Scan a directory for hardcoded secrets, API keys, and passwords.",
            inputSchema={
                "type": "object",
                "properties": {"directory": {"type": "string", "description": "Directory to scan"}},
                "required": ["directory"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "analyze_file":
        filepath = arguments.get("filepath", "")
        if not os.path.exists(filepath):
            return [TextContent(type="text", text=f"File not found: {filepath}")]
        return [TextContent(type="text", text=_analyze_python(filepath))]

    elif name == "check_dependencies":
        filepath = arguments.get("filepath", "")
        if not os.path.exists(filepath):
            return [TextContent(type="text", text=f"File not found: {filepath}")]
        return [TextContent(type="text", text=_check_requirements(filepath))]

    elif name == "find_secrets":
        directory = arguments.get("directory", ".")
        if not os.path.isdir(directory):
            return [TextContent(type="text", text=f"Directory not found: {directory}")]
        results = []
        patterns = [
            (r"password\s*=\s*["'][^"']+["']", "Hardcoded password"),
            (r"api_key\s*=\s*["'][^"']+["']", "Hardcoded API key"),
            (r"SECRET_KEY\s*=\s*["'][^"']+["']", "Hardcoded secret key"),
            (r"token\s*=\s*["'][A-Za-z0-9_\-]{20,}["']", "Hardcoded token"),
        ]
        for root, dirs, fls in os.walk(directory):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "node_modules" and d != "__pycache__"]
            for fn in fls:
                if fn.endswith((".py", ".js", ".ts", ".env", ".yaml", ".yml", ".json", ".toml")):
                    fpath = os.path.join(root, fn)
                    try:
                        with open(fpath, "r", errors="ignore") as f:
                            for i, line in enumerate(f, 1):
                                for pat, desc in patterns:
                                    if re.search(pat, line, re.IGNORECASE):
                                        results.append(f"{fpath}:{i} — {desc}")
                    except Exception:
                        pass
        if results:
            return [TextContent(type="text", text=f"Found {len(results)} potential secrets:\n" + "\n".join(results[:50]))]
        return [TextContent(type="text", text="No hardcoded secrets found.")]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream)


if __name__ == "__main__":
    asyncio.run(main())
