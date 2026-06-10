"""Interactive chat and one-shot query handlers."""

import sys
import signal
from aria.cli.client import create_session, send_message_stream, check_odysseus

# Colors for terminal output
class Colors:
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def _print_banner():
    print(f"""
{Colors.CYAN}{Colors.BOLD}╔══════════════════════════════════════╗
║          ARIA Terminal Chat          ║
║   Autonomous Retrieval & Intelligence║
╚══════════════════════════════════════╝{Colors.RESET}
{Colors.DIM}Type 'exit' or 'quit' to end the session.
Type 'clear' to start a new session.{Colors.RESET}
""")


def interactive_chat(model: str = None, session_id: str = None):
    """Run an interactive chat loop."""
    if not check_odysseus():
        print(f"{Colors.RED}Cannot connect to Odysseus. Is it running at localhost:7000?{Colors.RESET}")
        sys.exit(1)

    _print_banner()

    # Create session if not resuming
    if not session_id:
        session_id = create_session(model=model)
        if not session_id:
            print(f"{Colors.RED}Failed to create session.{Colors.RESET}")
            sys.exit(1)
        print(f"{Colors.DIM}Session: {session_id}{Colors.RESET}")

    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        print(f"\n{Colors.DIM}Goodbye!{Colors.RESET}")
        sys.exit(0)
    signal.signal(signal.SIGINT, signal_handler)

    while True:
        try:
            # Get user input
            user_input = input(f"\n{Colors.GREEN}{Colors.BOLD}You > {Colors.RESET}").strip()

            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit", "q"):
                print(f"{Colors.DIM}Goodbye!{Colors.RESET}")
                break

            if user_input.lower() == "clear":
                session_id = create_session(model=model)
                if session_id:
                    print(f"{Colors.DIM}New session: {session_id}{Colors.RESET}")
                else:
                    print(f"{Colors.RED}Failed to create new session.{Colors.RESET}")
                continue

            # Stream response
            print(f"\n{Colors.CYAN}{Colors.BOLD}ARIA > {Colors.RESET}", end="", flush=True)

            full_response = ""
            for chunk in send_message_stream(session_id, user_input, model=model):
                print(chunk, end="", flush=True)
                full_response += chunk

            print()  # newline after response

        except EOFError:
            print(f"\n{Colors.DIM}Goodbye!{Colors.RESET}")
            break
        except KeyboardInterrupt:
            print(f"\n{Colors.DIM}Goodbye!{Colors.RESET}")
            break


def one_shot(question: str, model: str = None):
    """Ask a single question and print the answer."""
    if not check_odysseus():
        print(f"{Colors.RED}Cannot connect to Odysseus at localhost:7000.{Colors.RESET}")
        sys.exit(1)

    session_id = create_session(model=model)
    if not session_id:
        print(f"{Colors.RED}Failed to create session.{Colors.RESET}")
        sys.exit(1)

    for chunk in send_message_stream(session_id, question, model=model):
        print(chunk, end="", flush=True)

    print()  # newline at end
