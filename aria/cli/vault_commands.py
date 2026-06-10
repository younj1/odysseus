"""ARIA CLI — Vault Librarian commands."""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class Colors:
    CYAN = "[96m"
    GREEN = "[92m"
    YELLOW = "[93m"
    RED = "[91m"
    BOLD = "[1m"
    DIM = "[2m"
    RESET = "[0m"


def _get_librarian():
    from aria.vault.librarian import VaultLibrarian
    lib = VaultLibrarian()
    if not lib.client.health():
        print(f"{Colors.RED}Cannot connect to Obsidian REST API. Is Obsidian open?{Colors.RESET}")
        return None
    return lib


def vault_status():
    """Show vault connection status and stats."""
    lib = _get_librarian()
    if not lib:
        return

    print(f"{Colors.CYAN}{Colors.BOLD}Obsidian Vault Status{Colors.RESET}")
    print(f"{Colors.DIM}{'=' * 40}{Colors.RESET}")
    print(f"  API: {Colors.GREEN}Connected{Colors.RESET}")

    lib.taxonomy.refresh()
    print(f"  Tags: {len(lib.taxonomy.tags)}")
    print(f"  Top folders: {', '.join(lib.taxonomy.folders[:8])}")
    print(f"  Top tags: {', '.join(lib.taxonomy.top_tags(10))}")


def vault_scan(auto_approve=False):
    """Scan vault and propose tags for untagged notes."""
    lib = _get_librarian()
    if not lib:
        return

    print(f"{Colors.CYAN}Scanning vault for untagged notes...{Colors.RESET}")
    proposals = lib.scan_and_propose_tags()

    if not proposals:
        print(f"{Colors.GREEN}All notes are already tagged!{Colors.RESET}")
        return

    print(f"\nFound {len(proposals)} untagged notes:\n")

    for i, p in enumerate(proposals, 1):
        print(f"  {Colors.BOLD}{i}. {p.note_path}{Colors.RESET}")
        print(f"     Tags: {Colors.CYAN}{', '.join(p.proposed_tags)}{Colors.RESET}")
        if p.suggested_folder:
            print(f"     Move to: {Colors.YELLOW}{p.suggested_folder}/{Colors.RESET}")
        print()

    if auto_approve:
        print(f"{Colors.YELLOW}Auto-approving all proposals...{Colors.RESET}")
        for p in proposals:
            lib.approve_and_apply(p)
            print(f"  {Colors.GREEN}Tagged: {p.note_path}{Colors.RESET}")
        filed = lib.auto_file()
        if filed:
            print(f"  {Colors.GREEN}Filed {filed} notes into folders{Colors.RESET}")
    else:
        print(f"{Colors.DIM}Run with --approve to apply these tags.{Colors.RESET}")
        print(f"{Colors.DIM}Or approve individually with: aria vault approve <number>{Colors.RESET}")

    return proposals


def vault_approve(index: int, proposals=None):
    """Approve a specific tag proposal by index."""
    lib = _get_librarian()
    if not lib:
        return

    if not lib.pending_proposals:
        print("No pending proposals. Run 'aria vault scan' first.")
        return

    if index < 1 or index > len(lib.pending_proposals):
        print(f"Invalid index. Choose 1-{len(lib.pending_proposals)}")
        return

    p = lib.pending_proposals[index - 1]
    lib.approve_and_apply(p)
    print(f"{Colors.GREEN}Applied tags to {p.note_path}: {', '.join(p.proposed_tags)}{Colors.RESET}")

    if p.suggested_folder:
        from aria.vault.filer import move_note
        move_note(lib.client, p.note_path, p.suggested_folder)
        print(f"{Colors.GREEN}Moved to {p.suggested_folder}/{Colors.RESET}")


def vault_link(threshold=0.75):
    """Find related notes and add backlinks."""
    lib = _get_librarian()
    if not lib:
        return

    print(f"{Colors.CYAN}Finding related notes in Knowledge folder...{Colors.RESET}")
    linked = lib.auto_link(threshold=threshold)
    print(f"{Colors.GREEN}Added backlinks to {linked} notes{Colors.RESET}")


def vault_tags():
    """Show all tags in the vault."""
    lib = _get_librarian()
    if not lib:
        return

    lib.taxonomy.refresh()
    tags = lib.taxonomy.tags

    print(f"{Colors.CYAN}{Colors.BOLD}Vault Tags ({len(tags)} total){Colors.RESET}")
    print(f"{Colors.DIM}{'=' * 40}{Colors.RESET}")

    for tag, count in sorted(tags.items(), key=lambda x: -x[1]):
        bar = "#" * min(count, 30)
        print(f"  {tag:25s} {count:3d} {Colors.DIM}{bar}{Colors.RESET}")


def vault_search(query):
    """Search notes in the vault."""
    lib = _get_librarian()
    if not lib:
        return

    print(f"{Colors.CYAN}Searching vault for: {query}{Colors.RESET}\n")
    results = lib.client.search(query)

    if not results:
        print("No results found.")
        return

    for r in results[:10]:
        filename = r.get("filename", "unknown")
        print(f"  {Colors.BOLD}{filename}{Colors.RESET}")
        matches = r.get("matches", [])
        for m in matches[:2]:
            context = m.get("match", {}).get("content", "")[:120]
            if context:
                print(f"    {Colors.DIM}{context}{Colors.RESET}")
        print()
