"""Auto-tagging engine — analyzes notes and proposes tags."""

import json
import re
import logging
import httpx
from typing import List, Tuple

from aria.vault.obsidian_client import ObsidianClient
from aria.vault.taxonomy import Taxonomy

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://172.19.16.1:11434"


def _query_llm(prompt: str, model: str = "qwen3:8b") -> str:
    try:
        resp = httpx.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 2000, "think": False},
            },
            timeout=120,
        )
        if resp.status_code == 200:
            data = resp.json()
            response = data.get("message", {}).get("content", "").strip()
            # Strip thinking tags if present
            if "<think>" in response:
                think_end = response.find("</think>")
                if think_end > 0:
                    response = response[think_end + 8:].strip()
            return response
        logger.error(f"LLM call failed: {resp.status_code}")
        return ""
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        return ""


def _extract_frontmatter_tags(content: str) -> List[str]:
    """Extract existing tags from note frontmatter."""
    tags = []
    if not content.strip().startswith("---"):
        return tags
    parts = content.split("---", 2)
    if len(parts) < 3:
        return tags
    frontmatter = parts[1]
    in_tags = False
    for line in frontmatter.split("\n"):
        stripped = line.strip()
        if stripped.startswith("tags:"):
            rest = stripped[5:].strip()
            if rest.startswith("["):
                # Handle both JSON ["a","b"] and YAML [a, b] formats
                inner = rest[1:].rstrip("]").strip()
                if inner:
                    tags = [t.strip().strip('"').strip("'") for t in inner.split(",")]
                    tags = [t for t in tags if t]
                return tags
            in_tags = True
            continue
        if in_tags:
            if stripped.startswith("- "):
                tags.append(stripped[2:].strip())
            elif stripped and not stripped.startswith("-"):
                in_tags = False
    return tags


def _has_frontmatter(content: str) -> bool:
    return content.strip().startswith("---")


def propose_tags(
    note_path: str,
    note_content: str,
    taxonomy: Taxonomy,
    max_tags: int = 6,
) -> Tuple[List[str], str]:
    existing_tags = _extract_frontmatter_tags(note_content)
    if existing_tags:
        return existing_tags, "Note already has tags"

    body = note_content
    if _has_frontmatter(note_content):
        parts = note_content.split("---", 2)
        if len(parts) >= 3:
            body = parts[2]

    body_preview = body[:2000].strip()
    if not body_preview:
        return [], "Note is empty"

    available_tags = taxonomy.top_tags(50)
    tag_list = ", ".join(available_tags)

    prompt = f"""Suggest tags for this note. Choose from existing tags when possible.

EXISTING TAGS: {tag_list}

NOTE TITLE: {note_path.split("/")[-1].replace(".md", "")}

NOTE CONTENT:
{body_preview[:1000]}

Return ONLY a JSON array of tag strings. Example: ["cybersecurity", "networking"]
No other text, no explanation. Just the JSON array:"""

    response = _query_llm(prompt)
    logger.info(f"LLM tag response for {note_path}: {response[:200]}")

    if not response:
        logger.warning(f"Empty LLM response for {note_path}")
        return [], "LLM returned empty response"

    try:
        # Clean up response — remove newlines inside JSON array
        clean = response.replace("\n", " ").replace("\r", " ")
        start = clean.find("[")
        end = clean.rfind("]") + 1
        if start >= 0 and end > start:
            tags = json.loads(clean[start:end])
            tags = [t.strip().lower() for t in tags if isinstance(t, str)]
            return tags[:max_tags], "LLM suggested based on content"
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"JSON parse error: {e}")

    logger.warning(f"Could not parse tags: {response[:200]}")
    return [], "Could not parse LLM response"


def apply_tags(client: ObsidianClient, note_path: str, tags: List[str]) -> bool:
    content = client.get_note(note_path)
    if content is None:
        return False

    tag_lines = "\n".join(f"  - {t}" for t in tags)

    if _has_frontmatter(content):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            fm = parts[1]
            if "tags:" in fm:
                fm = re.sub(
                    r"tags:.*?(?=\n\w|\n---)",
                    f"tags:\n{tag_lines}\n",
                    fm,
                    flags=re.DOTALL,
                )
            else:
                fm = fm.rstrip() + f"\ntags:\n{tag_lines}\n"
            new_content = f"---{fm}---{parts[2]}"
    else:
        new_content = f"---\ntags:\n{tag_lines}\naria_tagged: true\n---\n\n{content}"

    return client.save_note(note_path, new_content)
