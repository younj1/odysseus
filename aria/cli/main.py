#!/usr/bin/env python3
"""ARIA CLI — Access your local AI assistant from the terminal."""

import click
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


@click.group()
@click.version_option(version="0.1.0", prog_name="aria")
def cli():
    """ARIA — Your local AI assistant, from the terminal."""
    pass


@cli.command()
@click.option("--model", "-m", default=None, help="Override model (e.g. qwen3:8b)")
@click.option("--session", "-s", default=None, help="Resume a session by ID")
def chat(model, session):
    """Start an interactive chat session."""
    from aria.cli.chat import interactive_chat
    interactive_chat(model=model, session_id=session)


@cli.command()
@click.argument("question", nargs=-1, required=True)
@click.option("--model", "-m", default=None, help="Override model")
def ask(question, model):
    """Ask a single question and get an answer."""
    from aria.cli.chat import one_shot
    one_shot(" ".join(question), model=model)


@cli.command()
@click.option("--limit", "-n", default=20, help="Number of entries to show")
def audit(limit):
    """View the ARIA audit log."""
    from aria.cli.commands import show_audit
    show_audit(limit=limit)


@cli.command()
def status():
    """Check ARIA system status."""
    from aria.cli.commands import show_status
    show_status()


@cli.command()
def models():
    """List available models."""
    from aria.cli.commands import list_models
    list_models()


@cli.command()
def domains():
    """List available ARIA prompt domains."""
    from aria.cli.commands import list_domains
    list_domains()


@cli.group()
def vault():
    """Obsidian Vault Librarian commands."""
    pass


@vault.command(name="status")
def vault_status_cmd():
    """Check vault connection and stats."""
    from aria.cli.vault_commands import vault_status
    vault_status()


@vault.command(name="scan")
@click.option("--approve", is_flag=True, help="Auto-approve all tag proposals")
def vault_scan_cmd(approve):
    """Scan vault and propose tags for untagged notes."""
    from aria.cli.vault_commands import vault_scan
    vault_scan(auto_approve=approve)


@vault.command(name="link")
def vault_link_cmd():
    """Find related notes and add backlinks."""
    from aria.cli.vault_commands import vault_link
    vault_link()


@vault.command(name="tags")
def vault_tags_cmd():
    """Show all vault tags."""
    from aria.cli.vault_commands import vault_tags
    vault_tags()


@vault.command(name="search")
@click.argument("query", nargs=-1, required=True)
def vault_search_cmd(query):
    """Search notes in the vault."""
    from aria.cli.vault_commands import vault_search
    vault_search(" ".join(query))


@cli.group()
def git():
    """Git helper commands."""
    pass


@git.command(name="commit")
@click.option("--repo", "-r", default=".", help="Path to git repo")
def git_commit_cmd(repo):
    """Generate a commit message from staged changes."""
    from aria.cli.git_commands import git_commit_msg
    git_commit_msg(repo_path=repo)


@git.command(name="scan")
@click.option("--repo", "-r", default=".", help="Path to git repo")
def git_scan_cmd(repo):
    """Security scan staged changes before pushing."""
    from aria.cli.git_commands import git_scan
    git_scan(repo_path=repo)


@git.command(name="pr")
@click.option("--repo", "-r", default=".", help="Path to git repo")
@click.option("--base", "-b", default="main", help="Base branch")
def git_pr_cmd(repo, base):
    """Generate a PR summary."""
    from aria.cli.git_commands import git_pr
    git_pr(repo_path=repo, base=base)


@cli.group()
def finetune():
    """Fine-tuning pipeline commands."""
    pass


@finetune.command(name="prepare")
def finetune_prepare_cmd():
    """Prepare training data from conversations and vault."""
    from aria.finetune.prepare_data import prepare_dataset
    prepare_dataset()


@finetune.command(name="generate")
def finetune_generate_cmd():
    """Generate the training script."""
    from aria.finetune.train import generate_train_script
    generate_train_script()


@finetune.command(name="modelfile")
def finetune_modelfile_cmd():
    """Create an Ollama Modelfile for the fine-tuned model."""
    from aria.finetune.train import create_modelfile
    create_modelfile()

@cli.command()
def briefing():
    """Generate today's daily briefing."""
    from aria.briefing import generate_briefing
    briefing = generate_briefing()
    print("\n" + briefing)


@cli.command()
def clipboard():
    """Start the smart clipboard monitor."""
    from aria.clipboard import monitor
    monitor()

@cli.group()
def study():
    """Study session coach with spaced repetition."""
    pass


@study.command(name="generate")
@click.option("--topic", "-t", default=None, help="Generate cards for a specific topic")
def study_generate_cmd(topic):
    """Generate flashcards from vault notes."""
    from aria.study_coach import generate_cards
    count = generate_cards(topic=topic)
    print(f"Generated {count} new flashcards.")


@study.command(name="review")
@click.option("--limit", "-n", default=10, help="Max cards to review")
def study_review_cmd(limit):
    """Start a study review session."""
    from aria.study_coach import run_session
    run_session(limit=limit)


@study.command(name="stats")
def study_stats_cmd():
    """Show study statistics."""
    from aria.study_coach import get_stats
    stats = get_stats()
    C = "\033[96m"; B = "\033[1m"; D = "\033[2m"; X = "\033[0m"
    print(f"{C}{B}Study Stats{X}")
    print(f"  Cards: {stats['total_cards']} ({stats['due_today']} due today)")
    print(f"  Mastered: {stats['mastered']}")
    print(f"  Reviews: {stats['total_reviews']}")
    print(f"  Accuracy: {stats['accuracy']}%")
    if stats['topics']:
        print(f"\n  {B}By Topic:{X}")
        for topic, data in sorted(stats['topics'].items()):
            print(f"    {topic}: {data['total']} cards, {data['due']} due, {data['mastered']} mastered")


@cli.group()
def fitness():
    """Fitness tracking and training plans."""
    pass


@fitness.command(name="log")
def fitness_log_cmd():
    """Log a workout interactively."""
    from aria.fitness_coach import interactive_log
    interactive_log()


@fitness.command(name="stats")
def fitness_stats_cmd():
    """Show fitness statistics."""
    from aria.fitness_coach import get_stats
    stats = get_stats()
    C = "\033[96m"; B = "\033[1m"; D = "\033[2m"; X = "\033[0m"
    print(f"{C}{B}Fitness Stats{X}")
    print(f"  Total workouts: {stats['total_workouts']}")
    print(f"  Streak: {stats['streak']} days")
    print(f"  Last workout: {stats['last_workout'] or 'Never'}")
    if stats['workout_types']:
        print(f"\n  {B}By Type:{X}")
        for wtype, count in sorted(stats['workout_types'].items(), key=lambda x: -x[1]):
            print(f"    {wtype}: {count}")


@fitness.command(name="plan")
@click.option("--goal", "-g", default="general fitness", help="Training goal")
@click.option("--days", "-d", default=7, help="Number of days")
def fitness_plan_cmd(goal, days):
    """Generate a training plan."""
    from aria.fitness_coach import generate_plan
    plan = generate_plan(goal=goal, days=days)
    if plan:
        print(plan)
    else:
        print("Failed to generate plan.")

@cli.command()
def homelab():
    """Show homelab dashboard."""
    from aria.homelab import full_dashboard
    full_dashboard()


@cli.group()
def ctf():
    """CTF and security lab assistant."""
    pass


@ctf.command(name="session")
def ctf_session_cmd():
    """Start interactive CTF assistant."""
    from aria.ctf_assistant import interactive_session
    interactive_session()


@ctf.command(name="dvwa")
@click.argument("vulnerability")
@click.option("--level", "-l", default="low", help="Security level")
def ctf_dvwa_cmd(vulnerability, level):
    """Get DVWA challenge guide."""
    from aria.ctf_assistant import dvwa_guide
    print(dvwa_guide(vulnerability, level))


@ctf.command(name="hint")
@click.argument("challenge_type")
@click.option("--level", "-l", default="low", help="Difficulty level")
def ctf_hint_cmd(challenge_type, level):
    """Get a hint for a CTF challenge."""
    from aria.ctf_assistant import hint
    print(hint(challenge_type, level))

@cli.group()
def invest():
    """Investment portfolio tracker."""
    pass


@invest.command(name="portfolio")
def invest_portfolio_cmd():
    """Show portfolio with live prices."""
    from aria.investment_tracker import display_portfolio
    display_portfolio()


@invest.command(name="add")
@click.argument("symbol")
@click.argument("shares", type=float)
@click.argument("cost", type=float)
def invest_add_cmd(symbol, shares, cost):
    """Add a holding. Usage: aria invest add VOO 10 420.50"""
    from aria.investment_tracker import add_holding
    add_holding(symbol, shares, cost)
    print(f"Added {shares} shares of {symbol.upper()} at ${cost}")


@invest.command(name="sell")
@click.argument("symbol")
@click.option("--shares", "-s", type=float, default=None, help="Shares to sell (all if omitted)")
def invest_sell_cmd(symbol, shares):
    """Sell a holding."""
    from aria.investment_tracker import remove_holding
    if remove_holding(symbol, shares):
        print(f"Sold {shares or 'all'} shares of {symbol.upper()}")
    else:
        print(f"Holding not found: {symbol.upper()}")


@invest.command(name="watch")
@click.argument("symbol")
def invest_watch_cmd(symbol):
    """Add a symbol to watchlist."""
    from aria.investment_tracker import add_to_watchlist
    add_to_watchlist(symbol)
    print(f"Added {symbol.upper()} to watchlist")


@invest.command(name="analyze")
def invest_analyze_cmd():
    """Get AI analysis of your portfolio."""
    from aria.investment_tracker import analyze_portfolio
    analysis = analyze_portfolio()
    if analysis:
        print(analysis)
    else:
        print("Analysis failed. Add holdings first.")

@cli.command()
@click.argument("topic", nargs=-1, required=True)
@click.option("--depth", "-d", default="standard", help="quick/standard/deep")
def research(topic, depth):
    """Run autonomous research on a topic."""
    from aria.research_agent import research as run_research
    report = run_research(" ".join(topic), depth=depth)
    print(report)


@cli.command()
@click.argument("task", nargs=-1, required=True)
@click.option("--auto", is_flag=True, help="Auto-execute without confirmation")
def agents(task, auto):
    """Run multi-agent system on a complex task."""
    from aria.multi_agent import run_multi_agent, display_results
    results = run_multi_agent(" ".join(task), auto=auto)
    if results:
        show = input("\nShow full results? (y/n): ").strip().lower()
        if show == "y":
            display_results(results)

@cli.command()
@click.option("--duration", "-d", default=5, help="Recording duration in seconds")
def voice(duration):
    """Start voice chat with ARIA."""
    from aria.voice import voice_chat
    voice_chat(record_seconds=duration)


@cli.group()
def pdf():
    """PDF reading and analysis."""
    pass


@pdf.command(name="read")
@click.argument("filepath")
def pdf_read_cmd(filepath):
    """Open interactive PDF reader."""
    from aria.pdf_reader import interactive_pdf
    interactive_pdf(filepath)


@pdf.command(name="ask")
@click.argument("filepath")
@click.argument("question", nargs=-1, required=True)
def pdf_ask_cmd(filepath, question):
    """Ask a question about a PDF."""
    from aria.pdf_reader import ask_pdf
    answer = ask_pdf(filepath, " ".join(question))
    print(answer)


@pdf.command(name="summarize")
@click.argument("filepath")
def pdf_summarize_cmd(filepath):
    """Summarize a PDF."""
    from aria.pdf_reader import summarize_pdf
    print(summarize_pdf(filepath))


@pdf.command(name="ingest")
@click.argument("filepath")
@click.option("--folder", "-f", default="Knowledge", help="Vault folder to save to")
def pdf_ingest_cmd(filepath, folder):
    """Convert PDF to markdown and save to Obsidian vault."""
    from aria.pdf_reader import ingest_to_vault
    path, msg = ingest_to_vault(filepath, folder)
    print(msg)


@pdf.command(name="info")
@click.argument("filepath")
def pdf_info_cmd(filepath):
    """Show PDF metadata and stats."""
    from aria.pdf_reader import get_pdf_info
    info = get_pdf_info(filepath)
    for k, v in info.items():
        print(f"  {k}: {v}")


@cli.command(name="dashboard")
@click.option("--web", is_flag=True, help="Open in browser")
def dashboard_cmd(web):
    """Show ARIA dashboard with all stats."""
    if web:
        from aria.dashboard import serve_dashboard
        serve_dashboard()
    else:
        from aria.dashboard import print_dashboard
        print_dashboard()


@cli.group()
def monitor():
    """Web scraping and site monitoring."""
    pass


@monitor.command(name="add")
@click.argument("url")
@click.option("--name", "-n", default=None, help="Friendly name")
def monitor_add_cmd(url, name):
    """Add a site to monitor for changes."""
    from aria.web_monitor import add_site
    add_site(url, name)


@monitor.command(name="remove")
@click.argument("url")
def monitor_remove_cmd(url):
    """Remove a monitored site."""
    from aria.web_monitor import remove_site
    remove_site(url)


@monitor.command(name="check")
def monitor_check_cmd():
    """Check all monitored sites for changes."""
    from aria.web_monitor import check_all
    check_all()


@monitor.command(name="list")
def monitor_list_cmd():
    """List monitored sites."""
    from aria.web_monitor import list_sites
    list_sites()


@cli.command()
@click.argument("url")
@click.argument("question", nargs=-1, required=False)
def scrape(url, question):
    """Scrape a webpage and optionally ask a question about it."""
    from aria.web_monitor import scrape as do_scrape
    q = " ".join(question) if question else None
    result = do_scrape(url, q)
    if result:
        print(result)


@cli.command(name="do")
@click.argument("command", nargs=-1, required=True)
def do_cmd(command):
    """Natural language command gateway. Example: aria do 'save a note about Docker'"""
    from aria.gateway import process_command
    result = process_command(" ".join(command))
    print(result)


@cli.command(name="gateway")
def gateway_cmd():
    """Interactive natural language command interface."""
    from aria.gateway import interactive_gateway
    interactive_gateway()


@cli.group(name="import")
def import_group():
    """Import conversations from Claude, ChatGPT, markdown, text."""
    pass


@import_group.command(name="file")
@click.argument("filepath")
@click.option("--no-vault", is_flag=True, help="Skip saving to vault")
@click.option("--no-training", is_flag=True, help="Skip adding to training data")
def import_file_cmd(filepath, no_vault, no_training):
    """Import a single file (JSON, MD, TXT, ZIP)."""
    from aria.importer import import_file
    import_file(filepath, to_vault=not no_vault, to_training=not no_training)


@import_group.command(name="folder")
@click.argument("folder")
@click.option("--no-vault", is_flag=True, help="Skip saving to vault")
@click.option("--no-training", is_flag=True, help="Skip adding to training data")
def import_folder_cmd(folder, no_vault, no_training):
    """Import all files from a folder."""
    from aria.importer import import_folder
    import_folder(folder, to_vault=not no_vault, to_training=not no_training)


def main():
    cli()


if __name__ == "__main__":
    main()
