"""Auto-filing engine — moves notes to the right folders."""

import logging
from typing import Optional
from aria.vault.obsidian_client import ObsidianClient
from aria.vault.taxonomy import Taxonomy

logger = logging.getLogger(__name__)


def suggest_folder(
    note_path: str,
    tags: list,
    taxonomy: Taxonomy,
) -> Optional[str]:
    """Suggest the best folder for a note based on its tags.

    Only suggests for notes in root or Inbox.
    Returns None if note is already filed.
    """
    parts = note_path.strip("/").split("/")
    filename = parts[-1]

    if len(parts) > 1:
        current_folder = parts[0]
        if current_folder not in ("Inbox",):
            return None

    folder = taxonomy.suggest_folder(tags)
    return folder


def move_note(
    client: ObsidianClient,
    old_path: str,
    new_folder: str,
) -> bool:
    """Move a note to a new folder by reading, saving to new path, then deleting old."""
    content = client.get_note(old_path)
    if content is None:
        logger.error(f"Cannot read note: {old_path}")
        return False

    filename = old_path.strip("/").split("/")[-1]
    new_path = f"{new_folder}/{filename}"

    existing = client.get_note(new_path)
    if existing is not None:
        logger.warning(f"Note already exists at {new_path}, skipping move")
        return False

    if client.save_note(new_path, content):
        logger.info(f"Moved: {old_path} -> {new_path}")
        return True
    else:
        logger.error(f"Failed to save note to {new_path}")
        return False
