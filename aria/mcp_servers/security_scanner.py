"""
ARIA Security Scanner MCP Server
Network scanning and basic security assessment tools.
"""
import asyncio
import json
import subprocess
import sys
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

server = Server("aria-security-scanner")


def _run_cmd(cmd: list, timeout: int = 120) -> str:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return (result.stdout + result.stderr).strip()
    except FileNotFoundError:
        return f"Command not found: {cmd[0]}. Install it first."
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout}s"
    except Exception as e:
        return f"Error: {e}"


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="port_scan",
            description="Scan a target for open ports using nmap. Only use on authorized targets.",
            inputSchema={
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "IP address or hostname to scan"},
                    "ports": {"type": "string", "description": "Port range (e.g. '1-1000', '22,80,443')", "default": "1-1000"},
                    "scan_type": {"type": "string", "enum": ["quick", "full", "stealth"], "default": "quick"},
                },
                "required": ["target"],
            },
        ),
        Tool(
            name="check_ssl",
            description="Check SSL/TLS certificate details for a domain.",
            inputSchema={
                "type": "object",
                "properties": {"domain": {"type": "string", "description": "Domain to check (e.g. example.com)"}},
                "required": ["domain"],
            },
        ),
        Tool(
            name="dns_lookup",
            description="Perform DNS lookups for a domain.",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "description": "Domain to look up"},
                    "record_type": {"type": "string", "enum": ["A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA"], "default": "A"},
                },
                "required": ["domain"],
            },
        ),
        Tool(
            name="whois_lookup",
            description="Perform a WHOIS lookup for a domain.",
            inputSchema={
                "type": "object",
                "properties": {"domain": {"type": "string", "description": "Domain to look up"}},
                "required": ["domain"],
            },
        ),
        Tool(
            name="check_headers",
            description="Check HTTP security headers for a URL.",
            inputSchema={
                "type": "object",
                "properties": {"url": {"type": "string", "description": "URL to check (e.g. https://example.com)"}},
                "required": ["url"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "port_scan":
        target = arguments.get("target", "")
        ports = arguments.get("ports", "1-1000")
        scan_type = arguments.get("scan_type", "quick")

        if not target:
            return [TextContent(type="text", text="Target is required")]

        cmd = ["nmap"]
        if scan_type == "stealth":
            cmd.extend(["-sS", "-T2"])
        elif scan_type == "full":
            cmd.extend(["-sV", "-sC"])
        else:
            cmd.extend(["-T4"])

        cmd.extend(["-p", ports, target])
        output = _run_cmd(cmd, timeout=120)
        return [TextContent(type="text", text=output)]

    elif name == "check_ssl":
        domain = arguments.get("domain", "")
        if not domain:
            return [TextContent(type="text", text="Domain is required")]
        output = _run_cmd(["openssl", "s_client", "-connect", f"{domain}:443", "-servername", domain], timeout=10)
        cert_text = _run_cmd(["bash", "-c", f"echo | openssl s_client -connect {domain}:443 -servername {domain} 2>/dev/null | openssl x509 -noout -dates -subject -issuer"], timeout=15)
        return [TextContent(type="text", text=cert_text or output)]

    elif name == "dns_lookup":
        domain = arguments.get("domain", "")
        record_type = arguments.get("record_type", "A")
        if not domain:
            return [TextContent(type="text", text="Domain is required")]
        output = _run_cmd(["dig", "+short", domain, record_type], timeout=10)
        if not output or "not found" in output.lower():
            output = _run_cmd(["nslookup", domain], timeout=10)
        return [TextContent(type="text", text=output)]

    elif name == "whois_lookup":
        domain = arguments.get("domain", "")
        if not domain:
            return [TextContent(type="text", text="Domain is required")]
        output = _run_cmd(["whois", domain], timeout=15)
        return [TextContent(type="text", text=output[:3000])]

    elif name == "check_headers":
        url = arguments.get("url", "")
        if not url:
            return [TextContent(type="text", text="URL is required")]
        output = _run_cmd(["curl", "-sI", "-L", "--max-time", "10", url])
        security_headers = ["Strict-Transport-Security", "Content-Security-Policy", "X-Frame-Options",
                          "X-Content-Type-Options", "X-XSS-Protection", "Referrer-Policy",
                          "Permissions-Policy", "Cross-Origin-Opener-Policy"]
        analysis = ["\nSecurity Header Analysis:"]
        for header in security_headers:
            if header.lower() in output.lower():
                analysis.append(f"  [PASS] {header}: Present")
            else:
                analysis.append(f"  [MISSING] {header}: Not set")
        return [TextContent(type="text", text=output + "\n".join(analysis))]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream)


if __name__ == "__main__":
    asyncio.run(main())
