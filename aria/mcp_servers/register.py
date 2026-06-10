"""Register ARIA MCP servers with Odysseus."""
import json
import sys
import os
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.database import SessionLocal, McpServer


def register_server(name: str, script: str):
    db = SessionLocal()
    try:
        existing = db.query(McpServer).filter(McpServer.name == name).first()
        if existing:
            print(f"  {name}: already registered (id={existing.id})")
            return

        server_id = str(uuid.uuid4())[:8]
        srv = McpServer(
            id=server_id,
            name=name,
            transport="stdio",
            command=sys.executable,
            args=json.dumps([script]),
            is_enabled=True,
        )
        db.add(srv)
        db.commit()
        print(f"  {name}: registered (id={server_id})")
    finally:
        db.close()


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    servers = [
        ("ARIA System Monitor", os.path.join(base, "system_monitor.py")),
        ("ARIA Code Analyzer", os.path.join(base, "code_analyzer.py")),
        ("ARIA Security Scanner", os.path.join(base, "security_scanner.py")),
    ]
    print("Registering ARIA MCP servers...")
    for name, script in servers:
        register_server(name, script)
    print("Done!")


if __name__ == "__main__":
    main()
