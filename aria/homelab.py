"""ARIA Homelab Dashboard — Monitor your infrastructure."""

import json, logging, subprocess, httpx
from datetime import datetime

logger = logging.getLogger(__name__)

def _run(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except: return ""

def docker_status():
    """Get status of all Docker containers."""
    output = _run(["docker", "ps", "-a", "--format", "{{.Names}}\t{{.Status}}\t{{.Ports}}\t{{.Image}}"])
    if not output: return "Docker not available or no containers running."
    containers = []
    for line in output.split("\n"):
        parts = line.split("\t")
        if len(parts) >= 4:
            containers.append({"name": parts[0], "status": parts[1], "ports": parts[2], "image": parts[3]})
    return containers

def system_health():
    """Get system health metrics."""
    cpu_load = _run(["cat", "/proc/loadavg"]).split()[:3]
    mem = _run(["free", "-h"]).split("\n")
    mem_parts = mem[1].split() if len(mem) > 1 else []
    disk = _run(["df", "-h", "/"])
    gpu = _run(["nvidia-smi", "--query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu", "--format=csv,noheader,nounits"])
    uptime = _run(["uptime", "-p"])
    return {
        "cpu_load": {"1m": cpu_load[0] if cpu_load else "?", "5m": cpu_load[1] if len(cpu_load) > 1 else "?", "15m": cpu_load[2] if len(cpu_load) > 2 else "?"},
        "memory": {"total": mem_parts[1] if len(mem_parts) > 1 else "?", "used": mem_parts[2] if len(mem_parts) > 2 else "?", "available": mem_parts[6] if len(mem_parts) > 6 else "?"},
        "gpu": gpu or "Not available",
        "uptime": uptime or "Unknown",
    }

def network_info():
    """Get basic network information."""
    interfaces = _run(["ip", "-brief", "addr"])
    routes = _run(["ip", "route", "show", "default"])
    dns = _run(["cat", "/etc/resolv.conf"])
    listening = _run(["ss", "-tlnp"])
    return {"interfaces": interfaces, "default_route": routes, "dns": dns, "listening_ports": listening}

def check_services():
    """Check if key services are reachable."""
    services = [
        ("Odysseus", "http://127.0.0.1:7000"),
        ("Ollama", "http://172.19.16.1:11434"),
        ("ChromaDB", "http://127.0.0.1:8100"),
        ("SearXNG", "http://127.0.0.1:8080"),
        ("Obsidian API", "http://172.19.16.1:27123"),
        ("ntfy", "http://127.0.0.1:8091"),
    ]
    results = []
    for name, url in services:
        try:
            r = httpx.get(url, timeout=3)
            results.append({"name": name, "url": url, "status": "online", "code": r.status_code})
        except:
            results.append({"name": name, "url": url, "status": "offline", "code": None})
    return results

def full_dashboard():
    """Generate complete homelab dashboard."""
    C = "\033[96m"; G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"; B = "\033[1m"; D = "\033[2m"; X = "\033[0m"
    print(f"\n{C}{B}ARIA Homelab Dashboard{X}")
    print(f"{D}{'=' * 50}{X}")
    # Services
    print(f"\n{B}Services{X}")
    for svc in check_services():
        icon = f"{G}ONLINE{X}" if svc["status"] == "online" else f"{R}OFFLINE{X}"
        print(f"  {svc['name']:15s} {icon:s}  {svc['url']}")
    # System
    health = system_health()
    print(f"\n{B}System Health{X}")
    print(f"  CPU Load: {health['cpu_load']['1m']} / {health['cpu_load']['5m']} / {health['cpu_load']['15m']}")
    print(f"  Memory: {health['memory']['used']} / {health['memory']['total']} (Available: {health['memory']['available']})")
    print(f"  GPU: {health['gpu']}")
    print(f"  Uptime: {health['uptime']}")
    # Docker
    print(f"\n{B}Docker Containers{X}")
    containers = docker_status()
    if isinstance(containers, list):
        for c in containers:
            status = c["status"]
            icon = f"{G}UP{X}" if "Up" in status else f"{R}DOWN{X}"
            print(f"  {c['name']:30s} {icon}  {D}{c['image']}{X}")
    else:
        print(f"  {containers}")
    # Network
    print(f"\n{B}Network{X}")
    net = network_info()
    print(f"  Default route: {net['default_route']}")
    print(f"\n{D}Listening ports:{X}")
    for line in (net.get("listening_ports","") or "").split("\n")[:10]:
        if line.strip() and "LISTEN" in line:
            print(f"  {D}{line.strip()}{X}")
