"""
Contribution tools for vault404 - opt-in sharing to community knowledge

This is the bridge between local storage and collective AI learning.

WORKFLOW:
1. Agent solves a bug → log_error_fix()
2. User confirms it works → verify_solution(id, True)
3. User reviews and approves → prepare_contribution(id)
4. User confirms safe → confirm_contribution(id, anonymized)
5. Community benefits → export_contributions() or sync (future)
"""

from typing import Optional
from ..storage.local_storage import LocalStorage
from ..sync.contribution import ContributionManager
from ..sync.anonymizer import anonymize_record


# Global instances
_storage: Optional[LocalStorage] = None
_contrib: Optional[ContributionManager] = None


def get_storage() -> LocalStorage:
    global _storage
    if _storage is None:
        _storage = LocalStorage()
    return _storage


def get_contribution_manager() -> ContributionManager:
    global _contrib
    if _contrib is None:
        _contrib = ContributionManager()
    return _contrib


async def prepare_contribution(record_id: str) -> dict:
    """
    Prepare a verified solution for contribution to community knowledge.

    IMPORTANT: Only verified solutions can be contributed.
    This returns the anonymized version for USER REVIEW before contributing.

    Args:
        record_id: The ID of the error_fix record to contribute

    Returns:
        dict with anonymized record for review
    """
    storage = get_storage()

    # Load the full record
    filepath = storage.errors_dir / f"{record_id}.json"
    if not filepath.exists():
        return {
            "success": False,
            "reason": f"Record {record_id} not found",
        }

    import json
    record = json.loads(filepath.read_text(encoding='utf-8'))

    # Check if verified
    if not record.get("verified"):
        return {
            "success": False,
            "reason": "Only verified solutions can be contributed. Call verify_solution(id, True) first.",
            "tip": "After confirming the fix works, verify it to enable contribution.",
        }

    # Anonymize
    anon = anonymize_record(record)

    return {
        "success": True,
        "record_id": record_id,
        "anonymized": anon,
        "message": "Review this anonymized version below. If nothing sensitive remains, call confirm_contribution().",
        "next_step": f"confirm_contribution('{record_id}')",
    }


async def confirm_contribution(record_id: str) -> dict:
    """
    Confirm and save a contribution after reviewing the anonymized version.

    This saves the contribution locally. In Phase 2, this will sync to community.

    Args:
        record_id: The ID of the error_fix record to contribute

    Returns:
        dict with confirmation
    """
    storage = get_storage()
    contrib = get_contribution_manager()

    # Load and anonymize again (ensure consistency)
    filepath = storage.errors_dir / f"{record_id}.json"
    if not filepath.exists():
        return {
            "success": False,
            "reason": f"Record {record_id} not found",
        }

    import json
    record = json.loads(filepath.read_text(encoding='utf-8'))
    anon = anonymize_record(record)

    # Save contribution
    result = await contrib.confirm_contribution(record_id, anon)

    if result.get("success"):
        return {
            "success": True,
            "message": "Contribution saved! Thank you for helping AI agents learn.",
            "filepath": result.get("filepath"),
            "next_steps": [
                "This contribution is stored locally for now.",
                "Run export_contributions() to create a shareable file.",
                "In Phase 2: Auto-sync to community index.",
            ],
        }

    return result


async def export_contributions(output_path: Optional[str] = None) -> dict:
    """
    Export all pending contributions to a shareable JSON file.

    This file can be:
    - Shared with other developers
    - Submitted to community knowledge packs
    - Uploaded to the community index (Phase 2)

    Args:
        output_path: Where to save the export. Defaults to ~/vault404-contributions-{date}.json

    Returns:
        dict with export location
    """
    contrib = get_contribution_manager()

    result = await contrib.export_all_contributions(output_path)
    return result


async def get_contribution_stats() -> dict:
    """
    Get statistics about contributions.

    Returns:
        dict with contribution counts
    """
    contrib = get_contribution_manager()

    stats = await contrib.get_contribution_stats()

    return {
        "success": True,
        "stats": stats,
        "message": f"You've contributed {stats['total_contributed']} solutions to the community.",
    }
