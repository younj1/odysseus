"""
ARIA System Monitor MCP Server
Exposes system health tools: CPU, RAM, GPU, disk, processes.
"""
import asyncio
import json
import sys
import subprocess
import shutil
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

server = Server("aria-system-monitor")


def _run_cmd(cmd: list, timeout: int = 10) -> str:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip()
    except Exception as e:
        return f"Error: {e}"


def _get_cpu_info() -> dict:
    info = {}
    try:
        load = _run_cmd(["cat", "/proc/loadavg"])
        parts = load.split()
        info["load_1m"] = parts[0]
        info["load_5m"] = parts[1]
        info["load_15m"] = parts[2]
    except Exception:
        pass
    try:
        cpuinfo = _run_cmd(["nproc"])
        info["cores"] = int(cpuinfo)
    except Exception:
        pass
    return info


def _get_memory_info() -> dict:
    try:
        output = _run_cmd(["free", "-h"])
        lines = output.split("\n")
        if len(lines) >= 2:
            parts = lines[1].split()
            return {"total": parts[1], "used": parts[2], "free": parts[3], "available": parts[6] if len(parts) > 6 else "N/A"}
    except Exception:
        pass
    return {}


def _get_disk_info() -> list:
    try:
        output = _run_cmd(["df", "-h", "--type=ext4", "--type=vfat", "--type=ntfs", "--type=fuseblk", "--type=overlay"])
        lines = output.strip().split("\n")[1:]
        disks = []
        for line in lines:
            parts = line.split()
            if len(parts) >= 6:
                disks.append({"filesystem": parts[0], "size": parts[1], "used": parts[2], "available": parts[3], "use_pct": parts[4], "mount": parts[5]})
        return disks
    except Exception:
        return []


def _get_gpu_info() -> str:
    try:
        return _run_cmd(["nvidia-smi", "--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu", "--format=csv,noheader,nounits"])
    except Exception:
        return "GPU info unavailable"


def _get_processes(n: int = 10) -> str:
    try:
        return _run_cmd(["ps", "aux", "--sort=-%mem"], timeout=5)
    except Exception:
        return "Process info unavailable"


def _get_docker_status() -> str:
    try:
        return _run_cmd(["docker", "ps", "--format", "table {{.Names}}\t{{.Status}}\t{{.Ports}}"])
    except Exception:
        return "Docker info unavailable"


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="system_status",
            description="Get full system status: CPU load, RAM, disk, GPU, and Docker containers.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="gpu_status",
            description="Get NVIDIA GPU status: memory usage, utilization, temperature.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="disk_usage",
            description="Get disk space usage for all mounted filesystems.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="top_processes",
            description="Get top processes by memory usage.",
            inputSchema={
                "type": "object",
                "properties": {"count": {"type": "integer", "description": "Number of processes to show", "default": 10}},
                "required": [],
            },
        ),
        Tool(
            name="docker_status",
            description="Get status of running Docker containers.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "system_status":
        cpu = _get_cpu_info()
        mem = _get_memory_info()
        gpu = _get_gpu_info()
        disks = _get_disk_info()
        docker = _get_docker_status()
        report = f"""System Status
=============
CPU: {cpu.get('cores', '?')} cores, Load: {cpu.get('load_1m', '?')} / {cpu.get('load_5m', '?')} / {cpu.get('load_15m', '?')}
RAM: {mem.get('used', '?')} / {mem.get('total', '?')} (Available: {mem.get('available', '?')})
GPU: {gpu}
Disks: {json.dumps(disks, indent=2)}
Docker: {docker}"""
        return [TextContent(type="text", text=report)]

    elif name == "gpu_status":
        return [TextContent(type="text", text=_get_gpu_info())]

    elif name == "disk_usage":
        disks = _get_disk_info()
        return [TextContent(type="text", text=json.dumps(disks, indent=2))]

    elif name == "top_processes":
        return [TextContent(type="text", text=_get_processes())]

    elif name == "docker_status":
        return [TextContent(type="text", text=_get_docker_status())]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream)


if __name__ == "__main__":
    asyncio.run(main())
