"""Vault Librarian — orchestrates tagging, filing, and linking."""

import logging
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from aria.aria_config import get_config
from aria.vault.obsidian_client import ObsidianClient
from aria.vault.taxonomy import Taxonomy
from aria.vault.tagger import propose_tags, apply_tags, _extract_frontmatter_tags
from aria.vault.filer import suggest_folder, move_note
from aria.vault.linker import find_related_notes, add_backlinks

logger = logging.getLogger(__name__)


@dataclass
class TagProposal:
    """A pending tag proposal for user approval."""
    note_path: str
    proposed_tags: List[str]
    reasoning: str
    suggested_folder: Optional[str] = None
    status: str = "pending"  # pending, approved, rejected, applied


@dataclass
class LibrarianReport:
    """Results of a librarian run."""
    notes_scanned: int = 0
    notes_already_tagged: int = 0
    tag_proposals: List[TagProposal] = field(default_factory=list)
    notes_filed: int = 0
    notes_linked: int = 0
    errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0


class VaultLibrarian:
    """Main orchestrator for vault organization."""

    def __init__(self):
        config = get_config()
        obs_config = config.get("obsidian", {})
        self.client = ObsidianClient(
            base_url=obs_config.get("api_url", "http://172.19.16.1:27123"),
            api_key=obs_config.get("api_key", ""),
        )
        self.taxonomy = Taxonomy(self.client)
        self._pending_proposals: List[TagProposal] = []

    def _get_all_notes(self, folder: str = "/", recursive: bool = True) -> List[str]:
        """Get all .md files in a folder."""
        notes = []
        files = self.client.list_files(folder)
        for f in files:
            if f.endswith("/"):
                if recursive and not f.startswith("_") and not f.startswith("."):
                    subfolder = f"{folder}/{f.rstrip('/')}".strip("/")
                    notes.extend(self._get_all_notes(subfolder, recursive))
            elif f.endswith(".md"):
                path = f"{folder}/{f}".strip("/")
                if path.startswith("/"):
                    path = path[1:]
                notes.append(path)
        return notes

    def scan_and_propose_tags(
        self,
        folders: List[str] = None,
        force: bool = False,
    ) -> List[TagProposal]:
        """Scan notes and create tag proposals.

        Args:
            folders: Folders to scan. Default: Inbox + root
            force: If True, re-tag already-tagged notes
        """
        self.taxonomy.refresh()

        if folders is None:
            folders = ["Inbox", "/"]

        proposals = []
        for folder in folders:
            notes = self._get_all_notes(folder, recursive=(folder != "/"))
            # For root, only process files directly in root
            if folder == "/":
                notes = [n for n in notes if "/" not in n and n.endswith(".md")]

            for note_path in notes:
                content = self.client.get_note(note_path)
                if content is None:
                    continue

                existing_tags = _extract_frontmatter_tags(content)
                if existing_tags and not force:
                    continue

                tags, reasoning = propose_tags(note_path, content, self.taxonomy)
                if not tags:
                    continue

                folder_suggestion = suggest_folder(note_path, tags, self.taxonomy)

                proposal = TagProposal(
                    note_path=note_path,
                    proposed_tags=tags,
                    reasoning=reasoning,
                    suggested_folder=folder_suggestion,
                )
                proposals.append(proposal)

        self._pending_proposals = proposals
        return proposals

    def approve_and_apply(self, proposal: TagProposal) -> bool:
        """Apply an approved tag proposal."""
        success = apply_tags(self.client, proposal.note_path, proposal.proposed_tags)
        if success:
            proposal.status = "applied"
            logger.info(f"Applied tags to {proposal.note_path}: {proposal.proposed_tags}")
        else:
            proposal.status = "error"
            logger.error(f"Failed to apply tags to {proposal.note_path}")
        return success

    def auto_file(self, proposals: List[TagProposal] = None) -> int:
        """Auto-file notes based on their tags."""
        if proposals is None:
            proposals = [p for p in self._pending_proposals if p.status == "applied"]

        filed = 0
        for proposal in proposals:
            if proposal.suggested_folder and proposal.suggested_folder != "Inbox":
                parts = proposal.note_path.strip("/").split("/")
                if len(parts) == 1 or parts[0] == "Inbox":
                    success = move_note(
                        self.client,
                        proposal.note_path,
                        proposal.suggested_folder,
                    )
                    if success:
                        filed += 1
        return filed

    def auto_link(self, note_paths: List[str] = None, threshold: float = 0.75) -> int:
        """Find and add backlinks between related notes."""
        if note_paths is None:
            note_paths = self._get_all_notes("Knowledge")

        all_notes = []
        for path in note_paths:
            content = self.client.get_note(path)
            if content:
                all_notes.append((path, content))

        linked = 0
        for path, content in all_notes:
            related = find_related_notes(path, content, all_notes, threshold=threshold)
            if related:
                success = add_backlinks(self.client, path, related)
                if success:
                    linked += 1
        return linked

    def full_run(self, auto_approve: bool = False) -> LibrarianReport:
        """Run the full librarian pipeline."""
        start = time.time()
        report = LibrarianReport()

        try:
            # Step 1: Scan and propose tags
            proposals = self.scan_and_propose_tags()
            report.tag_proposals = proposals
            report.notes_scanned = len(proposals)

            if auto_approve:
                for p in proposals:
                    self.approve_and_apply(p)

                # Step 2: Auto-file
                report.notes_filed = self.auto_file()

            report.duration_seconds = time.time() - start

        except Exception as e:
            report.errors.append(str(e))
            logger.error(f"Librarian run failed: {e}")

        return report

    @property
    def pending_proposals(self) -> List[TagProposal]:
        return [p for p in self._pending_proposals if p.status == "pending"]
