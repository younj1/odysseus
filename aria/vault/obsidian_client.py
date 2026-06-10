"""Obsidian REST API client."""

import httpx
import json
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class ObsidianClient:
    """Client for the Obsidian Local REST API."""

    def __init__(self, base_url: str = "http://172.19.16.1:27123", api_key: str = ""):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.headers = {"Authorization": f"Bearer {api_key}"}

    def _get(self, path: str, **kwargs) -> Optional[Dict]:
        try:
            resp = httpx.get(f"{self.base_url}{path}", headers=self.headers, timeout=15, **kwargs)
            if resp.status_code == 200:
                return resp.json()
            logger.error(f"GET {path}: {resp.status_code}")
            return None
        except Exception as e:
            logger.error(f"GET {path} failed: {e}")
            return None

    def _put(self, path: str, content: str, **kwargs) -> bool:
        try:
            resp = httpx.put(
                f"{self.base_url}{path}",
                content=content.encode("utf-8"),
                headers={**self.headers, "Content-Type": "text/markdown"},
                timeout=15,
                **kwargs,
            )
            return resp.status_code in (200, 204)
        except Exception as e:
            logger.error(f"PUT {path} failed: {e}")
            return False

    def _patch(self, path: str, content: str, **kwargs) -> bool:
        try:
            resp = httpx.patch(
                f"{self.base_url}{path}",
                content=content.encode("utf-8"),
                headers={**self.headers, "Content-Type": "text/markdown", "Target-Type": "note"},
                timeout=15,
                **kwargs,
            )
            return resp.status_code in (200, 204)
        except Exception as e:
            logger.error(f"PATCH {path} failed: {e}")
            return False

    def health(self) -> bool:
        data = self._get("/")
        return data is not None and data.get("status") == "OK"

    def list_files(self, folder: str = "/") -> List[str]:
        clean = folder.strip("/")
        if clean:
            path = f"/vault/{clean}/"
        else:
            path = "/vault/"
        data = self._get(path)
        if data:
            return data.get("files", [])
        return []

    def get_note(self, path: str) -> Optional[str]:
        try:
            resp = httpx.get(
                f"{self.base_url}/vault/{path.lstrip('/')}",
                headers={**self.headers, "Accept": "text/markdown"},
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.text
            return None
        except Exception as e:
            logger.error(f"Get note {path} failed: {e}")
            return None

    def save_note(self, path: str, content: str) -> bool:
        return self._put(f"/vault/{path.lstrip('/')}", content)

    def append_to_note(self, path: str, content: str) -> bool:
        """Append content to the end of a note by reading then rewriting."""
        existing = self.get_note(path)
        if existing is None:
            return False
        new_content = existing + content
        return self.save_note(path, new_content)

    def get_tags(self) -> List[Dict]:
        data = self._get("/tags/")
        if data:
            return data.get("tags", [])
        return []

    def search(self, query: str) -> List[Dict]:
        try:
            resp = httpx.post(
                f"{self.base_url}/search/simple/",
                headers={**self.headers, "Content-Type": "application/json"},
                json={"query": query},
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
