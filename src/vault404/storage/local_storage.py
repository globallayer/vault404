"""
Local Storage Backend for vault404

Stores all data locally in ~/.vault404/ with optional encryption.
No network calls, no external dependencies beyond Python stdlib + pydantic.
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Union
from difflib import SequenceMatcher

from .schemas import ErrorFix, Decision, Pattern, Context
from ..security.encryption import get_encryptor, CRYPTO_AVAILABLE


# Magic bytes to identify encrypted files
ENCRYPTED_MARKER = b"VAULT404_ENCRYPTED:"


class LocalStorage:
    """
    Local file-based storage for vault404.

    Structure:
        ~/.vault404/
        ├── errors/          # Error/fix records (JSON files)
        ├── decisions/       # Decision records
        ├── patterns/        # Pattern records
        ├── index.json       # Search index
        └── config.json      # Configuration
    """

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        encrypted: bool = False,
        password: Optional[str] = None,
    ):
        self.data_dir = data_dir or Path.home() / ".vault404"
        self.errors_dir = self.data_dir / "errors"
        self.decisions_dir = self.data_dir / "decisions"
        self.patterns_dir = self.data_dir / "patterns"
        self.index_path = self.data_dir / "index.json"
        self.config_path = self.data_dir / "config.json"

        # Create directories
        for d in [self.errors_dir, self.decisions_dir, self.patterns_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # Set restrictive permissions (Unix only)
        if os.name != 'nt':
            os.chmod(self.data_dir, 0o700)

        # Initialize encryption
        self.encrypted = encrypted or self._load_config().get("encrypted", False)
        self._encryptor = None
        if self.encrypted and CRYPTO_AVAILABLE:
            self._encryptor = get_encryptor(self.data_dir, password)
            self._save_config({"encrypted": True})

        # Load or create index
        self._index = self._load_index()

    def _load_config(self) -> dict:
        """Load configuration."""
        if self.config_path.exists():
            try:
                return json.loads(self.config_path.read_text(encoding='utf-8'))
            except (json.JSONDecodeError, IOError):
                pass
        return {}

    def _save_config(self, config: dict) -> None:
        """Save configuration."""
        existing = self._load_config()
        existing.update(config)
        self.config_path.write_text(
            json.dumps(existing, indent=2),
            encoding='utf-8'
        )

    def _write_file(self, filepath: Path, content: str) -> None:
        """Write content to file, encrypting if enabled."""
        if self._encryptor:
            encrypted = self._encryptor.encrypt(content)
            filepath.write_bytes(ENCRYPTED_MARKER + encrypted)
        else:
            filepath.write_text(content, encoding='utf-8')

    def _read_file(self, filepath: Path) -> str:
        """Read content from file, decrypting if needed."""
        raw = filepath.read_bytes()

        # Check if encrypted
        if raw.startswith(ENCRYPTED_MARKER):
            if not self._encryptor:
                raise ValueError(
                    f"File {filepath} is encrypted but no encryptor available. "
                    "Initialize storage with encrypted=True and correct password."
                )
            encrypted_data = raw[len(ENCRYPTED_MARKER):]
            return self._encryptor.decrypt(encrypted_data)
        else:
            return raw.decode('utf-8')

    def _load_index(self) -> dict:
        """Load search index from disk."""
        if self.index_path.exists():
            try:
                content = self._read_file(self.index_path)
                return json.loads(content)
            except (json.JSONDecodeError, IOError, ValueError):
                pass
        return {"errors": [], "decisions": [], "patterns": []}

    def _save_index(self) -> None:
        """Save search index to disk."""
        content = json.dumps(self._index, indent=2, ensure_ascii=False)
        self._write_file(self.index_path, content)

    # =========================================================================
    # Error/Fix Storage
    # =========================================================================

    async def store_error_fix(self, record: ErrorFix) -> dict:
        """Store an error/fix record."""
        filepath = self.errors_dir / f"{record.id}.json"

        # Serialize to JSON
        data = record.model_dump(mode='json')
        data['timestamp'] = record.timestamp.isoformat()

        content = json.dumps(data, indent=2, ensure_ascii=False)
        self._write_file(filepath, content)

        # Update index
        self._index["errors"].append({
            "id": record.id,
            "error_message": record.error.message[:200],
            "solution": record.solution.description[:200],
            "context": record.context.model_dump(),
            "timestamp": record.timestamp.isoformat(),
            "verified": record.verified,
        })
        self._save_index()

        return {
            "success": True,
            "record_id": record.id,
            "filepath": str(filepath),
        }

    async def find_solutions(
        self,
        error_message: str,
        context: Optional[Context] = None,
        limit: int = 5,
    ) -> list[dict]:
        """Find solutions for an error using semantic matching."""
        results = []

        for entry in self._index.get("errors", []):
            # Calculate text similarity
            similarity = self._text_similarity(
                error_message.lower(),
                entry["error_message"].lower()
            )

            # Boost by context match
            if context and entry.get("context"):
                ctx = Context(**entry["context"])
                ctx_score = context.match_score(ctx)
                similarity = (similarity + ctx_score) / 2

            # Boost verified solutions
            if entry.get("verified"):
                similarity += 0.1

            if similarity > 0.1:  # Minimum threshold
                results.append({
                    "id": entry["id"],
                    "error": entry["error_message"],
                    "solution": entry["solution"],
                    "context": entry.get("context", {}),
                    "score": min(similarity, 1.0),
                    "verified": entry.get("verified", False),
                })

        # Sort by score and return top results
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    # =========================================================================
    # Decision Storage
    # =========================================================================

    async def store_decision(self, record: Decision) -> dict:
        """Store a decision record."""
        filepath = self.decisions_dir / f"{record.id}.json"

        data = record.model_dump(mode='json')
        data['timestamp'] = record.timestamp.isoformat()

        content = json.dumps(data, indent=2, ensure_ascii=False)
        self._write_file(filepath, content)

        # Update index
        self._index["decisions"].append({
            "id": record.id,
            "title": record.title,
            "choice": record.choice,
            "context": record.context.model_dump(),
            "timestamp": record.timestamp.isoformat(),
        })
        self._save_index()

        return {
            "success": True,
            "record_id": record.id,
            "filepath": str(filepath),
        }

    async def find_decisions(
        self,
        topic: str,
        context: Optional[Context] = None,
        limit: int = 5,
    ) -> list[dict]:
        """Find past decisions on a topic."""
        results = []

        for entry in self._index.get("decisions", []):
            # Match against title and choice
            title_sim = self._text_similarity(topic.lower(), entry["title"].lower())
            choice_sim = self._text_similarity(topic.lower(), entry["choice"].lower())
            similarity = max(title_sim, choice_sim)

            if similarity > 0.1:
                results.append({
                    "id": entry["id"],
                    "title": entry["title"],
                    "choice": entry["choice"],
                    "similarity": similarity,
                })

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:limit]

    # =========================================================================
    # Pattern Storage
    # =========================================================================

    async def store_pattern(self, record: Pattern) -> dict:
        """Store a pattern record."""
        filepath = self.patterns_dir / f"{record.id}.json"

        data = record.model_dump(mode='json')
        data['timestamp'] = record.timestamp.isoformat()

        content = json.dumps(data, indent=2, ensure_ascii=False)
        self._write_file(filepath, content)

        # Update index
        self._index["patterns"].append({
            "id": record.id,
            "name": record.name,
            "category": record.category,
            "problem": record.problem[:200],
            "solution": record.solution[:200],
            "timestamp": record.timestamp.isoformat(),
        })
        self._save_index()

        return {
            "success": True,
            "record_id": record.id,
            "filepath": str(filepath),
        }

    async def find_patterns(
        self,
        problem: str,
        category: Optional[str] = None,
        limit: int = 5,
    ) -> list[dict]:
        """Find patterns for a problem."""
        results = []

        for entry in self._index.get("patterns", []):
            # Filter by category if specified
            if category and entry.get("category", "").lower() != category.lower():
                continue

            # Match against problem and name
            problem_sim = self._text_similarity(problem.lower(), entry["problem"].lower())
            name_sim = self._text_similarity(problem.lower(), entry["name"].lower())
            similarity = max(problem_sim, name_sim)

            if similarity > 0.1:
                results.append({
                    "id": entry["id"],
                    "name": entry["name"],
                    "category": entry["category"],
                    "problem": entry["problem"],
                    "solution": entry["solution"],
                    "similarity": similarity,
                })

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:limit]

    # =========================================================================
    # Maintenance
    # =========================================================================

    async def verify_solution(self, record_id: str, success: bool) -> dict:
        """Mark a solution as verified or not."""
        # Update in index
        for entry in self._index.get("errors", []):
            if entry["id"] == record_id:
                entry["verified"] = success
                entry["verification_date"] = datetime.now().isoformat()
                break

        self._save_index()

        # Update the actual file
        filepath = self.errors_dir / f"{record_id}.json"
        if filepath.exists():
            content = self._read_file(filepath)
            data = json.loads(content)
            data["verified"] = success
            data["success_count"] = data.get("success_count", 0) + (1 if success else 0)
            data["failure_count"] = data.get("failure_count", 0) + (0 if success else 1)
            self._write_file(filepath, json.dumps(data, indent=2))

        return {"success": True, "record_id": record_id, "verified": success}

    async def get_stats(self) -> dict:
        """Get statistics about the knowledge base."""
        return {
            "total_records": (
                len(self._index.get("errors", [])) +
                len(self._index.get("decisions", [])) +
                len(self._index.get("patterns", []))
            ),
            "errors": len(self._index.get("errors", [])),
            "decisions": len(self._index.get("decisions", [])),
            "patterns": len(self._index.get("patterns", [])),
            "data_dir": str(self.data_dir),
        }

    async def get_all_records(self) -> dict:
        """Get all records for export."""
        errors = []
        for filepath in self.errors_dir.glob("*.json"):
            try:
                content = self._read_file(filepath)
                errors.append(json.loads(content))
            except (json.JSONDecodeError, IOError, ValueError):
                pass

        decisions = []
        for filepath in self.decisions_dir.glob("*.json"):
            try:
                content = self._read_file(filepath)
                decisions.append(json.loads(content))
            except (json.JSONDecodeError, IOError, ValueError):
                pass

        patterns = []
        for filepath in self.patterns_dir.glob("*.json"):
            try:
                content = self._read_file(filepath)
                patterns.append(json.loads(content))
            except (json.JSONDecodeError, IOError, ValueError):
                pass

        return {
            "errors": errors,
            "decisions": decisions,
            "patterns": patterns,
        }

    # =========================================================================
    # Helpers
    # =========================================================================

    def _text_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate text similarity using SequenceMatcher.

        This is a simple but effective approach for short texts.
        Can be upgraded to embeddings later.
        """
        # Quick check for substring match
        if text1 in text2 or text2 in text1:
            return 0.8

        # Word overlap
        words1 = set(text1.split())
        words2 = set(text2.split())
        if words1 and words2:
            overlap = len(words1 & words2) / max(len(words1), len(words2))
            if overlap > 0.3:
                return 0.5 + overlap * 0.3

        # Sequence matching
        return SequenceMatcher(None, text1, text2).ratio()
