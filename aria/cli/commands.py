"""Utility commands for ARIA CLI."""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class Colors:
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def show_status():
    """Display ARIA system status."""
    from aria.cli.client import check_odysseus, check_ollama, get_base_url, get_ollama_url

    print(f"{Colors.CYAN}{Colors.BOLD}ARIA System Status{Colors.RESET}")
    print(f"{Colors.DIM}{'=' * 40}{Colors.RESET}")

    # Odysseus
    ody_ok = check_odysseus()
    status = f"{Colors.GREEN}Online{Colors.RESET}" if ody_ok else f"{Colors.RED}Offline{Colors.RESET}"
    print(f"  Odysseus ({get_base_url()}): {status}")

    # Ollama
    oll_ok = check_ollama()
    status = f"{Colors.GREEN}Online{Colors.RESET}" if oll_ok else f"{Colors.RED}Offline{Colors.RESET}"
    print(f"  Ollama   ({get_ollama_url()}):  {status}")

    # ARIA config
    try:
        from aria.aria_config import get_config
        config = get_config()
        routing = config.get("routing", {})
        guardrails = config.get("guardrails", {})
        print(f"  Routing:    {Colors.GREEN}Enabled{Colors.RESET}" if routing.get("enabled") else f"  Routing:    {Colors.RED}Disabled{Colors.RESET}")
        print(f"  Guardrails: {Colors.GREEN}Enabled{Colors.RESET}" if guardrails.get("enabled") else f"  Guardrails: {Colors.RED}Disabled{Colors.RESET}")
        print(f"  Default model: {routing.get('default_model', 'unknown')}")
    except Exception as e:
        print(f"  ARIA config: {Colors.RED}Error — {e}{Colors.RESET}")


def list_models():
    """List available Ollama models."""
    from aria.cli.client import list_ollama_models, check_ollama

    if not check_ollama():
        print(f"{Colors.RED}Cannot connect to Ollama.{Colors.RESET}")
        return

    models = list_ollama_models()
    if not models:
        print("No models found.")
        return

    print(f"{Colors.CYAN}{Colors.BOLD}Available Models{Colors.RESET}")
    print(f"{Colors.DIM}{'=' * 40}{Colors.RESET}")

    try:
        from aria.aria_config import get_config
        config = get_config()
        model_roles = config.get("routing", {}).get("models", {})
        role_map = {v: k for k, v in model_roles.items()}
    except Exception:
        role_map = {}

    for model in sorted(models):
        role = role_map.get(model, "")
        role_str = f" {Colors.DIM}({role}){Colors.RESET}" if role else ""
        print(f"  {model}{role_str}")


def list_domains():
    """List available ARIA prompt domains."""
    try:
        from aria.router import get_available_domains
        domains = get_available_domains()
        if not domains:
            print("No prompt domains found.")
            return

        print(f"{Colors.CYAN}{Colors.BOLD}ARIA Prompt Domains{Colors.RESET}")
        print(f"{Colors.DIM}{'=' * 40}{Colors.RESET}")
        for domain in domains:
            print(f"  {domain}")
    except Exception as e:
        print(f"{Colors.RED}Error: {e}{Colors.RESET}")


def show_audit(limit: int = 20):
    """Show recent audit log entries."""
    try:
        from aria.guardrails import get_audit_log
        entries = get_audit_log(limit=limit)
        if not entries:
            print("No audit log entries found.")
            return

        print(f"{Colors.CYAN}{Colors.BOLD}ARIA Audit Log (last {limit}){Colors.RESET}")
        print(f"{Colors.DIM}{'=' * 60}{Colors.RESET}")
        for entry in entries:
            ts = entry.get("timestamp", "unknown")[:19]
            domain = entry.get("domain", "")
            user = entry.get("user", "")
            inp = entry.get("input", "")[:80]
            event = entry.get("event", "")

            if event:
                print(f"  {Colors.DIM}{ts}{Colors.RESET} [{Colors.YELLOW}{event}{Colors.RESET}] {inp}")
            else:
                print(f"  {Colors.DIM}{ts}{Colors.RESET} [{Colors.CYAN}{domain}{Colors.RESET}] {inp}")
    except Exception as e:
        print(f"{Colors.RED}Error reading audit log: {e}{Colors.RESET}")
