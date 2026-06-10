"""HTTP client for talking to the Odysseus API."""

import httpx
import json
import os
import logging
from typing import Optional, Generator

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://127.0.0.1:7000"
DEFAULT_OLLAMA_URL = "http://172.19.16.1:11434"


def get_base_url() -> str:
    return os.environ.get("ARIA_BASE_URL", DEFAULT_BASE_URL)


def get_ollama_url() -> str:
    return os.environ.get("ARIA_OLLAMA_URL", DEFAULT_OLLAMA_URL)


def _get_auth_headers() -> dict:
    """Get auth headers. Uses API token if set, otherwise tries session cookie."""
    token = os.environ.get("ARIA_API_TOKEN", "")
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def create_session(model: str = None) -> Optional[str]:
    """Create a new chat session, returns session ID."""
    base = get_base_url()
    headers = _get_auth_headers()
    try:
        resp = httpx.post(
            f"{base}/api/session",
            data={
                "model": model or "qwen3:8b",
                "name": "",
                "endpoint_id": "52c003d1",
            },
            headers=headers,
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("id") or data.get("session_id")
        else:
            logger.error(f"Failed to create session: {resp.status_code} {resp.text[:200]}")
            return None
    except Exception as e:
        logger.error(f"Connection error: {e}")
        return None


def send_message_stream(session_id: str, message: str, model: str = None) -> Generator[str, None, None]:
    """Send a message and yield streamed response chunks."""
    base = get_base_url()
    headers = _get_auth_headers()

    form_data = {
        "message": message,
        "session": session_id,
        "mode": "chat",
    }

    try:
        with httpx.stream(
            "POST",
            f"{base}/api/chat_stream",
            data=form_data,
            headers=headers,
            timeout=300,
        ) as resp:
            if resp.status_code != 200:
                yield f"[Error: HTTP {resp.status_code}]"
                return

            buffer = ""
            for chunk in resp.iter_text():
                buffer += chunk
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            return
                        try:
                            data = json.loads(data_str)
                            if isinstance(data, dict):
                                # Skip thinking tokens
                                if data.get("thinking"):
                                    continue
                                # Odysseus format: {"delta": "text"}
                                delta = data.get("delta", "")
                                if delta:
                                    yield delta
                                # Also check content field
                                content = data.get("content", "")
                                if content and not delta:
                                    yield content
                        except json.JSONDecodeError:
                            pass
    except httpx.ConnectError:
        yield "[Error: Cannot connect to Odysseus at " + base + ". Is it running?]"
    except httpx.ReadTimeout:
        yield "[Error: Response timed out]"
    except Exception as e:
        yield f"[Error: {e}]"


def send_message_sync(session_id: str, message: str, model: str = None) -> str:
    """Send a message and return the complete response."""
    chunks = []
    for chunk in send_message_stream(session_id, message, model=model):
        chunks.append(chunk)
    return "".join(chunks)


def check_odysseus() -> bool:
    """Check if Odysseus is reachable."""
    try:
        resp = httpx.get(f"{get_base_url()}/api/health", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


def check_ollama() -> bool:
    """Check if Ollama is reachable."""
    try:
        resp = httpx.get(f"{get_ollama_url()}/api/tags", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


def list_ollama_models() -> list:
    """Get list of models from Ollama."""
    try:
        resp = httpx.get(f"{get_ollama_url()}/api/tags", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return [m.get("name", "") for m in data.get("models", [])]
    except Exception:
        pass
    return []
