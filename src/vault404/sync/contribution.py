"""
Contribution Manager for vault404

Handles opt-in contribution of anonymized knowledge to community indexes.
This is the bridge between local storage and shared learning.

PHASE 2 DESIGN:
- Local: Always works, stores everything
- Contribution: Opt-in, anonymized, verified-only
- Community: Query for solutions not in local

IMPORTANT: This module does NOT upload anything automatically.
User must explicitly call contribute() with full understanding.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional
from .anonymizer import anonymize_record


class ContributionManager:
    """
    Manages the contribution of local knowledge to shared repositories.

    Current implementation: Export to shareable files.
    Future: API integration with community index.
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path.home() / ".vault404"
        self.contributions_dir = self.data_dir / "contributions"
        self.contributions_dir.mkdir(parents=True, exist_ok=True)

        # Track what's been contributed (to avoid duplicates)
        self.contributed_path = self.contributions_dir / "contributed.json"
        self._contributed = self._load_contributed()

    def _load_contributed(self) -> set:
        """Load set of already-contributed record IDs."""
        if self.contributed_path.exists():
            try:
                data = json.loads(self.contributed_path.read_text(encoding='utf-8'))
                return set(data.get("ids", []))
            except (json.JSONDecodeError, IOError):
                pass
        return set()

    def _save_contributed(self) -> None:
        """Save the set of contributed record IDs."""
        self.contributed_path.write_text(
            json.dumps({"ids": list(self._contributed)}, indent=2),
            encoding='utf-8'
        )

    async def prepare_contribution(self, record: dict) -> dict:
        """
        Prepare a record for contribution.

        Returns the anonymized version for user review BEFORE contributing.
        User should verify nothing sensitive remains.
        """
        # Only verified solutions can be contributed
        if not record.get("verified"):
            return {
                "success": False,
                "reason": "Only verified solutions can be contributed. Call verify_solution(id, True) first.",
            }

        # Anonymize
        anon = anonymize_record(record)

        return {
            "success": True,
            "original_id": record.get("id"),
            "anonymized": anon,
            "message": "Review this anonymized version. If it looks safe, call confirm_contribution().",
        }

    async def confirm_contribution(self, record_id: str, anonymized: dict) -> dict:
        """
        Confirm and save a contribution.

        CURRENT: Saves to local contributions folder for manual sharing.
        FUTURE: Will POST to community API.
        """
        if record_id in self._contributed:
            return {
                "success": False,
                "reason": "This record has already been contributed.",
            }

        # Save to contributions folder
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        content_hash = anonymized.get("content_hash", "unknown")[:8]
        filename = f"{timestamp}-{content_hash}.json"

        contribution = {
            "contributed_at": datetime.now().isoformat(),
            "source": "claw-dex",
            "version": "0.1.0",
            "data": anonymized,
        }

        filepath = self.contributions_dir / filename
        filepath.write_text(
            json.dumps(contribution, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )

        # Track as contributed
        self._contributed.add(record_id)
        self._save_contributed()

        return {
            "success": True,
            "message": f"Contribution saved to {filename}",
            "filepath": str(filepath),
            "note": "In Phase 2, this will sync to the community index automatically.",
        }

    async def export_all_contributions(self, output_path: Optional[str] = None) -> dict:
        """
        Export all pending contributions to a single shareable file.

        This can be:
        - Uploaded manually to community repository
        - Shared with other developers
        - Submitted as a PR to knowledge packs
        """
        contributions = []

        for filepath in self.contributions_dir.glob("*.json"):
            if filepath.name == "contributed.json":
                continue
            try:
                data = json.loads(filepath.read_text(encoding='utf-8'))
                contributions.append(data)
            except (json.JSONDecodeError, IOError):
                pass

        if not contributions:
            return {
                "success": False,
                "message": "No contributions to export. Use prepare_contribution() and confirm_contribution() first.",
            }

        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d")
            output_path = str(Path.home() / f"vault404-contributions-{timestamp}.json")

        export = {
            "exported_at": datetime.now().isoformat(),
            "source": "claw-dex",
            "version": "0.1.0",
            "count": len(contributions),
            "contributions": contributions,
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export, f, indent=2, ensure_ascii=False)

        return {
            "success": True,
            "message": f"Exported {len(contributions)} contributions",
            "filepath": output_path,
            "next_steps": [
                "Share this file with other developers",
                "Submit as PR to community knowledge packs",
                "In Phase 2: Auto-sync to community API",
            ],
        }

    async def get_contribution_stats(self) -> dict:
        """Get stats about contributions."""
        pending = 0
        for filepath in self.contributions_dir.glob("*.json"):
            if filepath.name != "contributed.json":
                pending += 1

        return {
            "total_contributed": len(self._contributed),
            "pending_export": pending,
            "contributions_dir": str(self.contributions_dir),
        }
