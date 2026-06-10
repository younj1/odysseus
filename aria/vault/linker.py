"""Auto-backlinking engine — finds related notes and adds [[wikilinks]]."""

import logging
import httpx
import json
from typing import List, Tuple

from aria.vault.obsidian_client import ObsidianClient

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://172.19.16.1:11434"
RELATED_SECTION = "## Related Notes"


def _get_embedding(text: str, model: str = "nomic-embed-text") -> List[float]:
    """Get embedding vector from Ollama."""
    try:
        resp = httpx.post(
            f"{OLLAMA_URL}/api/embed",
            json={"model": model, "input": text},
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json()
            embeddings = data.get("embeddings", [])
            if embeddings:
                return embeddings[0]
        return []
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        return []


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = sum(x * x for x in a) ** 0.5
    mag_b = sum(x * x for x in b) ** 0.5
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def _has_related_section(content: str) -> bool:
    return RELATED_SECTION in content


def _note_title(path: str) -> str:
    return path.split("/")[-1].replace(".md", "")


def find_related_notes(
    target_path: str,
    target_content: str,
    all_notes: List[Tuple[str, str]],
    threshold: float = 0.75,
    max_links: int = 5,
) -> List[Tuple[str, float]]:
    target_preview = target_content[:1500]
    target_embedding = _get_embedding(target_preview)
    if not target_embedding:
        return []

    similarities = []
    for path, content in all_notes:
        if path == target_path:
            continue
        preview = content[:1500]
        embedding = _get_embedding(preview)
        if not embedding:
            continue
        sim = _cosine_similarity(target_embedding, embedding)
        if sim >= threshold:
            similarities.append((path, sim))

    similarities.sort(key=lambda x: -x[1])
    return similarities[:max_links]


def add_backlinks(
    client: ObsidianClient,
    note_path: str,
    related: List[Tuple[str, float]],
) -> bool:
    if not related:
        return False

    content = client.get_note(note_path)
    if content is None:
        return False

    if _has_related_section(content):
        logger.debug(f"Skipping {note_path} — already has Related Notes section")
        return False

    links = []
    for path, score in related:
        title = _note_title(path)
        links.append("- [[" + title + "]]")

    section = "\n\n" + RELATED_SECTION + "\n" + "\n".join(links) + "\n"

    return client.append_to_note(note_path, section)
