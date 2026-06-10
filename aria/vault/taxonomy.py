"""Learns and manages the existing tag taxonomy from the vault."""

import logging
from typing import List, Dict, Set
from aria.vault.obsidian_client import ObsidianClient

logger = logging.getLogger(__name__)


class Taxonomy:
    """Manages the vault tag taxonomy."""

    def __init__(self, client: ObsidianClient):
        self.client = client
        self._tags: Dict[str, int] = {}
        self._folder_structure: List[str] = []

    def refresh(self):
        """Reload tags and folder structure from vault."""
        tags = self.client.get_tags()
        self._tags = {t["name"]: t["count"] for t in tags}
        files = self.client.list_files("/") or []
        self._folder_structure = [f.rstrip("/") for f in files if f.endswith("/")]
        logger.info(f"Taxonomy: {len(self._tags)} tags, {len(self._folder_structure)} top folders")

    @property
    def tags(self) -> Dict[str, int]:
        if not self._tags:
            self.refresh()
        return self._tags

    @property
    def tag_names(self) -> List[str]:
        return sorted(self.tags.keys())

    @property
    def folders(self) -> List[str]:
        if not self._folder_structure:
            self.refresh()
        return self._folder_structure

    def top_tags(self, n: int = 30) -> List[str]:
        return [t for t, _ in sorted(self.tags.items(), key=lambda x: -x[1])[:n]]

    def suggest_folder(self, tags: List[str]) -> str:
        """Suggest the best folder based on tags."""
        tag_to_folder = {
            "cybersecurity": "Knowledge",
            "red-team": "Knowledge",
            "blue-team": "Knowledge",
            "networking": "Knowledge",
            "homelab": "Knowledge",
            "pfsense": "Knowledge",
            "kali": "Knowledge",
            "dvwa": "Knowledge",
            "certifications": "Knowledge",
            "career": "Knowledge",
            "academic": "Knowledge",
            "study-plan": "Knowledge",
            "research": "Knowledge",
            "hci": "Knowledge",
            "orgo": "Knowledge",
            "math": "Knowledge",
            "investing": "Knowledge",
            "etf": "Knowledge",
            "finance": "Knowledge",
            "roth-ira": "Knowledge",
            "training": "Knowledge",
            "fitness": "Knowledge",
            "mma": "Knowledge",
            "nutrition": "Knowledge",
            "breathwork": "Knowledge",
            "airforce": "Knowledge",
            "military": "Knowledge",
            "afoqt": "Knowledge",
            "travel": "Knowledge",
            "firearms": "Knowledge",
            "fashion": "Knowledge",
            "splunk": "Knowledge",
            "ollama": "Knowledge",
            "rag": "Knowledge",
            "fastapi": "Knowledge",
            "aria": "projects",
            "hub": "Hubs",
            "dashboard": "Dashboards",
            "daily": "Daily",
            "tasks": "Tasks",
        }
        for tag in tags:
            tag_lower = tag.lower()
            if tag_lower in tag_to_folder:
                return tag_to_folder[tag_lower]
        return "Inbox"
