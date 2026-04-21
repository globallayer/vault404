"""
Local Storage Backend for vault404

Stores all data locally in ~/.vault404/ with optional encryption.
No network calls, no external dependencies beyond Python stdlib + pydantic.

DATA PROTECTION GUARANTEES:
1. Automatic migration from legacy locations (.clawdex)
2. Automatic backups before every write
3. Index recovery from individual record files if corrupted
4. Atomic writes (write to temp, then rename)
5. Never overwrite data with empty state
"""

import json
import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional
from difflib import SequenceMatcher
import tempfile

from .schemas import ErrorFix, Decision, Pattern, Context, VulnerabilityReport
from ..security.encryption import get_encryptor, CRYPTO_AVAILABLE
from ..search.ranker import temporal_decay, calculate_score
from ..search.strategies import multi_strategy_text_score
from ..search import embeddings


# Magic bytes to identify encrypted files
ENCRYPTED_MARKER = b"VAULT404_ENCRYPTED:"

# Legacy data directories to migrate from
LEGACY_DATA_DIRS = [".clawdex"]

# Maximum number of backups to keep
MAX_BACKUPS = 10


class LocalStorage:
    """
    Local file-based storage for vault404.

    Structure:
        ~/.vault404/
        ├── errors/          # Error/fix records (JSON files)
        ├── decisions/       # Decision records
        ├── patterns/        # Pattern records
        ├── backups/         # Automatic backups
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
        self.vulns_dir = self.data_dir / "vulnerabilities"
        self.backups_dir = self.data_dir / "backups"
        self.index_path = self.data_dir / "index.json"
        self.config_path = self.data_dir / "config.json"

        # Create directories
        for d in [self.errors_dir, self.decisions_dir, self.patterns_dir, self.vulns_dir, self.backups_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # Set restrictive permissions (Unix only)
        if os.name != "nt":
            os.chmod(self.data_dir, 0o700)

        # CRITICAL: Migrate from legacy locations BEFORE anything else
        self._migrate_legacy_data()

        # Initialize encryption
        self.encrypted = encrypted or self._load_config().get("encrypted", False)
        self._encryptor = None
        if self.encrypted and CRYPTO_AVAILABLE:
            self._encryptor = get_encryptor(self.data_dir, password)
            self._save_config({"encrypted": True})

        # Load index with recovery
        self._index = self._load_index_with_recovery()

    # =========================================================================
    # DATA PROTECTION: Migration, Backup, Recovery
    # =========================================================================

    def _migrate_legacy_data(self) -> None:
        """
        Migrate data from legacy locations (e.g., .clawdex).

        CRITICAL: This runs on EVERY startup to ensure no data is ever lost
        due to package renaming or directory changes.
        """
        home = Path.home()

        for legacy_name in LEGACY_DATA_DIRS:
            legacy_dir = home / legacy_name
            if not legacy_dir.exists():
                continue

            # Check if legacy has data we don't have
            legacy_index = legacy_dir / "index.json"
            if legacy_index.exists():
                try:
                    legacy_data = json.loads(legacy_index.read_text(encoding="utf-8"))
                    legacy_count = (
                        len(legacy_data.get("errors", []))
                        + len(legacy_data.get("decisions", []))
                        + len(legacy_data.get("patterns", []))
                    )

                    # Check current data count
                    current_count = 0
                    if self.index_path.exists():
                        try:
                            current_data = json.loads(self.index_path.read_text(encoding="utf-8"))
                            current_count = (
                                len(current_data.get("errors", []))
                                + len(current_data.get("decisions", []))
                                + len(current_data.get("patterns", []))
                            )
                        except (json.JSONDecodeError, IOError):
                            pass

                    # Only migrate if legacy has MORE data (never lose data)
                    if legacy_count > current_count:
                        self._do_migration(legacy_dir)

                except (json.JSONDecodeError, IOError):
                    # Try to migrate individual files anyway
                    self._migrate_individual_files(legacy_dir)

    def _do_migration(self, legacy_dir: Path) -> None:
        """Perform the actual migration from legacy directory."""
        # Copy all files, preserving existing ones
        for subdir in ["errors", "decisions", "patterns"]:
            legacy_subdir = legacy_dir / subdir
            current_subdir = self.data_dir / subdir

            if legacy_subdir.exists():
                for filepath in legacy_subdir.glob("*.json"):
                    dest = current_subdir / filepath.name
                    if not dest.exists():
                        shutil.copy2(filepath, dest)

        # Copy index if we don't have one or legacy is newer
        legacy_index = legacy_dir / "index.json"
        if legacy_index.exists():
            if not self.index_path.exists():
                shutil.copy2(legacy_index, self.index_path)
            else:
                # Merge indexes
                self._merge_legacy_index(legacy_index)

    def _migrate_individual_files(self, legacy_dir: Path) -> None:
        """Migrate individual record files even if index is corrupted."""
        for subdir in ["errors", "decisions", "patterns"]:
            legacy_subdir = legacy_dir / subdir
            current_subdir = self.data_dir / subdir

            if legacy_subdir.exists():
                for filepath in legacy_subdir.glob("*.json"):
                    dest = current_subdir / filepath.name
                    if not dest.exists():
                        shutil.copy2(filepath, dest)

    def _merge_legacy_index(self, legacy_index_path: Path) -> None:
        """Merge legacy index into current index."""
        try:
            legacy_data = json.loads(legacy_index_path.read_text(encoding="utf-8"))
            current_data = json.loads(self.index_path.read_text(encoding="utf-8"))

            # Get existing IDs
            current_error_ids = {e["id"] for e in current_data.get("errors", [])}
            current_decision_ids = {d["id"] for d in current_data.get("decisions", [])}
            current_pattern_ids = {p["id"] for p in current_data.get("patterns", [])}

            # Add missing entries from legacy
            for error in legacy_data.get("errors", []):
                if error["id"] not in current_error_ids:
                    current_data.setdefault("errors", []).append(error)

            for decision in legacy_data.get("decisions", []):
                if decision["id"] not in current_decision_ids:
                    current_data.setdefault("decisions", []).append(decision)

            for pattern in legacy_data.get("patterns", []):
                if pattern["id"] not in current_pattern_ids:
                    current_data.setdefault("patterns", []).append(pattern)

            # Save merged index
            self._atomic_write(
                self.index_path, json.dumps(current_data, indent=2, ensure_ascii=False)
            )

        except (json.JSONDecodeError, IOError):
            pass

    def _load_index_with_recovery(self) -> dict:
        """
        Load index with automatic recovery from individual files if corrupted.

        CRITICAL: Never return empty index if files exist on disk.
        """
        index = {"errors": [], "decisions": [], "patterns": [], "vulnerabilities": []}

        # Try to load existing index
        if self.index_path.exists():
            try:
                content = self._read_file(self.index_path)
                index = json.loads(content)
                self._migrate_index(index)
            except (json.JSONDecodeError, IOError, ValueError):
                # Index corrupted - will rebuild from files
                pass

        # CRITICAL: Verify index matches files on disk
        # If files exist but index is empty, rebuild
        index = self._verify_and_recover_index(index)

        return index

    def _verify_and_recover_index(self, index: dict) -> dict:
        """
        Verify index matches files on disk. Rebuild if necessary.

        CRITICAL: This ensures we NEVER lose data even if index is corrupted.
        """
        # Count files on disk
        error_files = list(self.errors_dir.glob("*.json"))
        decision_files = list(self.decisions_dir.glob("*.json"))
        pattern_files = list(self.patterns_dir.glob("*.json"))
        vuln_files = list(self.vulns_dir.glob("*.json"))

        files_on_disk = len(error_files) + len(decision_files) + len(pattern_files) + len(vuln_files)
        entries_in_index = (
            len(index.get("errors", []))
            + len(index.get("decisions", []))
            + len(index.get("patterns", []))
            + len(index.get("vulnerabilities", []))
        )

        # If index is missing entries, rebuild from files
        if files_on_disk > entries_in_index:
            index = self._rebuild_index_from_files()
            self._save_index_internal(index)

        return index

    def _rebuild_index_from_files(self) -> dict:
        """Rebuild entire index from individual record files."""
        index = {"errors": [], "decisions": [], "patterns": [], "vulnerabilities": []}

        # Rebuild errors
        for filepath in self.errors_dir.glob("*.json"):
            try:
                content = self._read_file(filepath)
                data = json.loads(content)
                index["errors"].append(
                    {
                        "id": data.get("id", filepath.stem),
                        "error_message": data.get("error", {}).get("message", "")[:200],
                        "solution": data.get("solution", {}).get("description", "")[:200],
                        "context": data.get("context", {}),
                        "timestamp": data.get("timestamp", datetime.now().isoformat()),
                        "verified": data.get("verified", False),
                        "usage_count": data.get("usage_count", 0),
                        "last_accessed": data.get("last_accessed"),
                        "success_count": data.get("success_count", 0),
                        "failure_count": data.get("failure_count", 0),
                        "embedding": data.get("embedding"),
                    }
                )
            except (json.JSONDecodeError, IOError, ValueError):
                continue

        # Rebuild decisions
        for filepath in self.decisions_dir.glob("*.json"):
            try:
                content = self._read_file(filepath)
                data = json.loads(content)
                index["decisions"].append(
                    {
                        "id": data.get("id", filepath.stem),
                        "title": data.get("title", ""),
                        "choice": data.get("choice", ""),
                        "context": data.get("context", {}),
                        "timestamp": data.get("timestamp", datetime.now().isoformat()),
                        "embedding": data.get("embedding"),
                    }
                )
            except (json.JSONDecodeError, IOError, ValueError):
                continue

        # Rebuild patterns
        for filepath in self.patterns_dir.glob("*.json"):
            try:
                content = self._read_file(filepath)
                data = json.loads(content)
                index["patterns"].append(
                    {
                        "id": data.get("id", filepath.stem),
                        "name": data.get("name", ""),
                        "category": data.get("category", ""),
                        "problem": data.get("problem", "")[:200],
                        "solution": data.get("solution", "")[:200],
                        "timestamp": data.get("timestamp", datetime.now().isoformat()),
                        "embedding": data.get("embedding"),
                    }
                )
            except (json.JSONDecodeError, IOError, ValueError):
                continue

        # Rebuild vulnerabilities
        for filepath in self.vulns_dir.glob("*.json"):
            try:
                content = self._read_file(filepath)
                data = json.loads(content)
                index["vulnerabilities"].append(
                    {
                        "id": data.get("id", filepath.stem),
                        "vuln_type": data.get("vuln_type", ""),
                        "severity": data.get("severity", ""),
                        "cwe_id": data.get("cwe_id"),
                        "language": data.get("language"),
                        "framework": data.get("framework"),
                        "description": data.get("description", "")[:200],
                        "pattern_snippet": data.get("pattern_snippet", "")[:200],
                        "disclosure_status": data.get("disclosure_status", "open"),
                        "is_public": data.get("is_public", False),
                        "reported_by_agent": data.get("reported_by_agent", "unknown"),
                        "verified_count": data.get("verified_count", 0),
                        "false_positive_count": data.get("false_positive_count", 0),
                        "timestamp": data.get("timestamp", datetime.now().isoformat()),
                        "embedding": data.get("embedding"),
                    }
                )
            except (json.JSONDecodeError, IOError, ValueError):
                continue

        return index

    def _create_backup(self) -> None:
        """Create a backup of the current index before any write operation."""
        if not self.index_path.exists():
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backups_dir / f"index_{timestamp}.json"

        try:
            shutil.copy2(self.index_path, backup_path)
        except IOError:
            pass  # Don't fail if backup fails

        # Clean up old backups
        self._cleanup_old_backups()

    def _cleanup_old_backups(self) -> None:
        """Keep only the most recent backups."""
        backups = sorted(self.backups_dir.glob("index_*.json"), reverse=True)
        for old_backup in backups[MAX_BACKUPS:]:
            try:
                old_backup.unlink()
            except IOError:
                pass

    def _atomic_write(self, filepath: Path, content: str) -> None:
        """
        Write content atomically to prevent corruption.

        Writes to a temp file first, then renames (atomic on most filesystems).
        """
        # Create temp file in same directory (important for atomic rename)
        fd, temp_path = tempfile.mkstemp(
            dir=filepath.parent, prefix=f".{filepath.stem}_", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)

            # Atomic rename
            temp_path_obj = Path(temp_path)
            temp_path_obj.replace(filepath)
        except Exception:
            # Clean up temp file on failure
            try:
                Path(temp_path).unlink()
            except IOError:
                pass
            raise

    # =========================================================================
    # File I/O
    # =========================================================================

    def _load_config(self) -> dict:
        """Load configuration."""
        if self.config_path.exists():
            try:
                return json.loads(self.config_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, IOError):
                pass
        return {}

    def _save_config(self, config: dict) -> None:
        """Save configuration."""
        existing = self._load_config()
        existing.update(config)
        self.config_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    def _write_file(self, filepath: Path, content: str) -> None:
        """Write content to file, encrypting if enabled."""
        if self._encryptor:
            encrypted = self._encryptor.encrypt(content)
            filepath.write_bytes(ENCRYPTED_MARKER + encrypted)
        else:
            self._atomic_write(filepath, content)

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
            encrypted_data = raw[len(ENCRYPTED_MARKER) :]
            return self._encryptor.decrypt(encrypted_data)
        else:
            return raw.decode("utf-8")

    def _migrate_index(self, index: dict) -> None:
        """
        Add missing fields to existing index entries.

        This ensures backward compatibility when new fields are added.
        """
        migrated = False

        for entry in index.get("errors", []):
            if "usage_count" not in entry:
                entry["usage_count"] = 0
                migrated = True
            if "last_accessed" not in entry:
                entry["last_accessed"] = None
                migrated = True
            if "success_count" not in entry:
                entry["success_count"] = 0
                migrated = True
            if "failure_count" not in entry:
                entry["failure_count"] = 0
                migrated = True

        # Ensure vulnerabilities list exists
        if "vulnerabilities" not in index:
            index["vulnerabilities"] = []
            migrated = True

        # Migrate vulnerability entries
        for entry in index.get("vulnerabilities", []):
            if "verified_count" not in entry:
                entry["verified_count"] = 0
                migrated = True
            if "false_positive_count" not in entry:
                entry["false_positive_count"] = 0
                migrated = True
            if "is_public" not in entry:
                entry["is_public"] = False
                migrated = True
            if "disclosure_status" not in entry:
                entry["disclosure_status"] = "open"
                migrated = True

        if migrated:
            self._save_index_internal(index)

    def _save_index_internal(self, index: dict) -> None:
        """Internal index save (used during init before self._index is set)."""
        content = json.dumps(index, indent=2, ensure_ascii=False)
        self._write_file(self.index_path, content)

    def _save_index(self) -> None:
        """
        Save search index to disk with backup.

        CRITICAL: Creates backup before write and validates data.
        """
        # Create backup before any write
        self._create_backup()

        # CRITICAL: Never write empty index if files exist
        files_on_disk = (
            len(list(self.errors_dir.glob("*.json")))
            + len(list(self.decisions_dir.glob("*.json")))
            + len(list(self.patterns_dir.glob("*.json")))
            + len(list(self.vulns_dir.glob("*.json")))
        )
        entries_in_index = (
            len(self._index.get("errors", []))
            + len(self._index.get("decisions", []))
            + len(self._index.get("patterns", []))
            + len(self._index.get("vulnerabilities", []))
        )

        if files_on_disk > 0 and entries_in_index == 0:
            # Something is wrong - rebuild instead of overwriting
            self._index = self._rebuild_index_from_files()

        content = json.dumps(self._index, indent=2, ensure_ascii=False)
        self._write_file(self.index_path, content)

    # =========================================================================
    # Error/Fix Storage
    # =========================================================================

    async def store_error_fix(self, record: ErrorFix) -> dict:
        """Store an error/fix record."""
        filepath = self.errors_dir / f"{record.id}.json"

        # Compute embedding for semantic search
        embedding_text = embeddings.combine_text_for_embedding(
            record.error.message, record.context.model_dump() if record.context else None
        )
        embedding_vector = embeddings.get_embedding(embedding_text)

        # Store embedding on record if available
        if embedding_vector:
            record.embedding = embedding_vector

        # Serialize to JSON
        data = record.model_dump(mode="json")
        data["timestamp"] = record.timestamp.isoformat()

        content = json.dumps(data, indent=2, ensure_ascii=False)
        self._write_file(filepath, content)

        # Update index
        self._index["errors"].append(
            {
                "id": record.id,
                "error_message": record.error.message[:200],
                "solution": record.solution.description[:200],
                "context": record.context.model_dump(),
                "timestamp": record.timestamp.isoformat(),
                "verified": record.verified,
                "usage_count": record.usage_count,
                "last_accessed": record.last_accessed.isoformat() if record.last_accessed else None,
                "success_count": record.success_count,
                "failure_count": record.failure_count,
                "embedding": embedding_vector,
            }
        )
        self._save_index()

        return {
            "success": True,
            "record_id": record.id,
            "filepath": str(filepath),
            "has_embedding": embedding_vector is not None,
        }

    async def find_solutions(
        self,
        error_message: str,
        context: Optional[Context] = None,
        limit: int = 5,
    ) -> list[dict]:
        """
        Find solutions for an error using hybrid semantic + text matching.
        """
        results = []
        now = datetime.now()

        # Compute query embedding for semantic search
        query_embedding_text = embeddings.combine_text_for_embedding(
            error_message, context.model_dump() if context else None
        )
        query_embedding = embeddings.get_embedding(query_embedding_text)
        semantic_available = query_embedding is not None

        for entry in self._index.get("errors", []):
            # Semantic similarity (if embeddings available)
            semantic_sim = 0.0
            if semantic_available and entry.get("embedding"):
                semantic_sim = embeddings.cosine_similarity(query_embedding, entry["embedding"])

            # Multi-strategy text similarity (fallback/complement)
            text_sim = multi_strategy_text_score(
                error_message.lower(), entry["error_message"].lower()
            )

            # Hybrid similarity
            if semantic_available and entry.get("embedding"):
                combined_sim = 0.7 * semantic_sim + 0.3 * text_sim
            else:
                combined_sim = text_sim

            # Context match score
            ctx_score = 0.0
            if context and entry.get("context"):
                ctx = Context(**entry["context"])
                ctx_score = context.match_score(ctx)

            # Temporal decay
            try:
                timestamp = datetime.fromisoformat(entry["timestamp"])
                temporal = temporal_decay(timestamp, half_life_days=30, now=now)
            except (ValueError, KeyError):
                temporal = 0.5

            # Calculate combined score
            score = calculate_score(
                text_similarity=combined_sim,
                context_match=ctx_score,
                temporal_factor=temporal,
                verified=entry.get("verified", False),
                success_count=entry.get("success_count", 0),
                failure_count=entry.get("failure_count", 0),
                usage_count=entry.get("usage_count", 0),
            )

            if score > 0.15:
                results.append(
                    {
                        "id": entry["id"],
                        "error": entry["error_message"],
                        "solution": entry["solution"],
                        "context": entry.get("context", {}),
                        "score": min(score, 1.0),
                        "verified": entry.get("verified", False),
                        "timestamp": entry.get("timestamp"),
                        "semantic_match": semantic_sim > 0.5 if semantic_available else None,
                    }
                )

        results.sort(key=lambda x: x["score"], reverse=True)
        top_results = results[:limit]

        self._track_usage([r["id"] for r in top_results])

        return top_results

    def _track_usage(self, record_ids: list[str]) -> None:
        """Update usage stats for records returned in search results."""
        if not record_ids:
            return

        now = datetime.now().isoformat()
        updated = False

        for entry in self._index.get("errors", []):
            if entry["id"] in record_ids:
                entry["usage_count"] = entry.get("usage_count", 0) + 1
                entry["last_accessed"] = now
                updated = True

        if updated:
            self._save_index()

    # =========================================================================
    # Decision Storage
    # =========================================================================

    async def store_decision(self, record: Decision) -> dict:
        """Store a decision record."""
        filepath = self.decisions_dir / f"{record.id}.json"

        embedding_text = f"{record.title} | {record.choice} | {' '.join(record.alternatives)}"
        embedding_vector = embeddings.get_embedding(embedding_text)

        if embedding_vector:
            record.embedding = embedding_vector

        data = record.model_dump(mode="json")
        data["timestamp"] = record.timestamp.isoformat()

        content = json.dumps(data, indent=2, ensure_ascii=False)
        self._write_file(filepath, content)

        self._index["decisions"].append(
            {
                "id": record.id,
                "title": record.title,
                "choice": record.choice,
                "context": record.context.model_dump(),
                "timestamp": record.timestamp.isoformat(),
                "embedding": embedding_vector,
            }
        )
        self._save_index()

        return {
            "success": True,
            "record_id": record.id,
            "filepath": str(filepath),
            "has_embedding": embedding_vector is not None,
        }

    async def find_decisions(
        self,
        topic: str,
        context: Optional[Context] = None,
        limit: int = 5,
    ) -> list[dict]:
        """Find past decisions on a topic."""
        results = []

        query_embedding = embeddings.get_embedding(topic)
        semantic_available = query_embedding is not None

        for entry in self._index.get("decisions", []):
            semantic_sim = 0.0
            if semantic_available and entry.get("embedding"):
                semantic_sim = embeddings.cosine_similarity(query_embedding, entry["embedding"])

            title_sim = self._text_similarity(topic.lower(), entry["title"].lower())
            choice_sim = self._text_similarity(topic.lower(), entry["choice"].lower())
            text_sim = max(title_sim, choice_sim)

            if semantic_available and entry.get("embedding"):
                similarity = 0.7 * semantic_sim + 0.3 * text_sim
            else:
                similarity = text_sim

            if similarity > 0.1:
                results.append(
                    {
                        "id": entry["id"],
                        "title": entry["title"],
                        "choice": entry["choice"],
                        "similarity": similarity,
                    }
                )

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:limit]

    # =========================================================================
    # Pattern Storage
    # =========================================================================

    async def store_pattern(self, record: Pattern) -> dict:
        """Store a pattern record."""
        filepath = self.patterns_dir / f"{record.id}.json"

        embedding_text = f"{record.name} | {record.problem} | {record.solution}"
        embedding_vector = embeddings.get_embedding(embedding_text)

        if embedding_vector:
            record.embedding = embedding_vector

        data = record.model_dump(mode="json")
        data["timestamp"] = record.timestamp.isoformat()

        content = json.dumps(data, indent=2, ensure_ascii=False)
        self._write_file(filepath, content)

        self._index["patterns"].append(
            {
                "id": record.id,
                "name": record.name,
                "category": record.category,
                "problem": record.problem[:200],
                "solution": record.solution[:200],
                "timestamp": record.timestamp.isoformat(),
                "embedding": embedding_vector,
            }
        )
        self._save_index()

        return {
            "success": True,
            "record_id": record.id,
            "filepath": str(filepath),
            "has_embedding": embedding_vector is not None,
        }

    async def find_patterns(
        self,
        problem: str,
        category: Optional[str] = None,
        limit: int = 5,
    ) -> list[dict]:
        """Find patterns for a problem."""
        results = []

        query_embedding = embeddings.get_embedding(problem)
        semantic_available = query_embedding is not None

        for entry in self._index.get("patterns", []):
            if category and entry.get("category", "").lower() != category.lower():
                continue

            semantic_sim = 0.0
            if semantic_available and entry.get("embedding"):
                semantic_sim = embeddings.cosine_similarity(query_embedding, entry["embedding"])

            problem_sim = self._text_similarity(problem.lower(), entry["problem"].lower())
            name_sim = self._text_similarity(problem.lower(), entry["name"].lower())
            text_sim = max(problem_sim, name_sim)

            if semantic_available and entry.get("embedding"):
                similarity = 0.7 * semantic_sim + 0.3 * text_sim
            else:
                similarity = text_sim

            if similarity > 0.1:
                results.append(
                    {
                        "id": entry["id"],
                        "name": entry["name"],
                        "category": entry["category"],
                        "problem": entry["problem"],
                        "solution": entry["solution"],
                        "similarity": similarity,
                    }
                )

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:limit]

    # =========================================================================
    # Vulnerability Storage
    # =========================================================================

    async def store_vulnerability(self, record: VulnerabilityReport) -> dict:
        """Store a vulnerability report."""
        filepath = self.vulns_dir / f"{record.id}.json"

        # Compute embedding for semantic search
        embedding_text = f"{record.vuln_type} | {record.severity} | {record.description} | {record.pattern_snippet}"
        embedding_vector = embeddings.get_embedding(embedding_text)

        if embedding_vector:
            record.embedding = embedding_vector

        # Serialize to JSON
        data = record.model_dump(mode="json")
        data["timestamp"] = record.timestamp.isoformat()

        content = json.dumps(data, indent=2, ensure_ascii=False)
        self._write_file(filepath, content)

        # Update index
        self._index.setdefault("vulnerabilities", []).append(
            {
                "id": record.id,
                "vuln_type": record.vuln_type,
                "severity": record.severity,
                "cwe_id": record.cwe_id,
                "language": record.language,
                "framework": record.framework,
                "description": record.description[:200],
                "pattern_snippet": record.pattern_snippet[:200],
                "disclosure_status": record.disclosure_status,
                "is_public": record.is_public,
                "reported_by_agent": record.reported_by_agent,
                "verified_count": record.verified_count,
                "false_positive_count": record.false_positive_count,
                "timestamp": record.timestamp.isoformat(),
                "embedding": embedding_vector,
            }
        )
        self._save_index()

        return {
            "success": True,
            "record_id": record.id,
            "filepath": str(filepath),
            "has_embedding": embedding_vector is not None,
        }

    async def find_vulnerabilities(
        self,
        query: str,
        vuln_type: Optional[str] = None,
        severity: Optional[str] = None,
        language: Optional[str] = None,
        framework: Optional[str] = None,
        include_private: bool = False,
        limit: int = 10,
    ) -> list[dict]:
        """
        Find vulnerabilities using hybrid semantic + text matching.

        Args:
            query: Search query (description, pattern, etc.)
            vuln_type: Filter by vulnerability type (SQLi, XSS, etc.)
            severity: Filter by severity (Critical, High, Medium, Low)
            language: Filter by programming language
            framework: Filter by framework
            include_private: Include non-public vulnerabilities (default False)
            limit: Maximum results to return
        """
        results = []
        now = datetime.now()

        # Compute query embedding for semantic search
        query_embedding = embeddings.get_embedding(query)
        semantic_available = query_embedding is not None

        for entry in self._index.get("vulnerabilities", []):
            # Filter by disclosure status (respect responsible disclosure)
            if not include_private and not entry.get("is_public", False):
                # Check if disclosure delay has passed
                try:
                    timestamp = datetime.fromisoformat(entry["timestamp"])
                    disclosure_hours = 72  # Default 72-hour delay
                    from datetime import timedelta
                    deadline = timestamp + timedelta(hours=disclosure_hours)
                    if now < deadline and entry.get("disclosure_status") == "open":
                        continue  # Skip - not ready for disclosure
                except (ValueError, KeyError):
                    continue

            # Apply filters
            if vuln_type and entry.get("vuln_type", "").lower() != vuln_type.lower():
                continue
            if severity and entry.get("severity", "").lower() != severity.lower():
                continue
            if language and entry.get("language", "").lower() != language.lower():
                continue
            if framework and entry.get("framework", "").lower() != framework.lower():
                continue

            # Semantic similarity
            semantic_sim = 0.0
            if semantic_available and entry.get("embedding"):
                semantic_sim = embeddings.cosine_similarity(query_embedding, entry["embedding"])

            # Text similarity
            desc_sim = self._text_similarity(query.lower(), entry.get("description", "").lower())
            pattern_sim = self._text_similarity(query.lower(), entry.get("pattern_snippet", "").lower())
            text_sim = max(desc_sim, pattern_sim)

            # Hybrid similarity
            if semantic_available and entry.get("embedding"):
                similarity = 0.7 * semantic_sim + 0.3 * text_sim
            else:
                similarity = text_sim

            # Boost by verification count
            verification_boost = min(entry.get("verified_count", 0) * 0.05, 0.2)
            similarity += verification_boost

            # Penalize false positives
            fp_penalty = min(entry.get("false_positive_count", 0) * 0.1, 0.3)
            similarity -= fp_penalty

            if similarity > 0.1:
                results.append(
                    {
                        "id": entry["id"],
                        "vuln_type": entry["vuln_type"],
                        "severity": entry["severity"],
                        "cwe_id": entry.get("cwe_id"),
                        "language": entry.get("language"),
                        "framework": entry.get("framework"),
                        "description": entry["description"],
                        "pattern_snippet": entry["pattern_snippet"],
                        "disclosure_status": entry.get("disclosure_status"),
                        "reported_by_agent": entry.get("reported_by_agent"),
                        "verified_count": entry.get("verified_count", 0),
                        "similarity": max(0, min(similarity, 1.0)),
                        "timestamp": entry.get("timestamp"),
                    }
                )

        results.sort(key=lambda x: x["similarity"], reverse=True)
        top_results = results[:limit]

        # Track usage
        self._track_vuln_usage([r["id"] for r in top_results])

        return top_results

    def _track_vuln_usage(self, record_ids: list[str]) -> None:
        """Update usage stats for vulnerability records."""
        if not record_ids:
            return

        now = datetime.now().isoformat()
        updated = False

        for entry in self._index.get("vulnerabilities", []):
            if entry["id"] in record_ids:
                entry["view_count"] = entry.get("view_count", 0) + 1
                entry["last_accessed"] = now
                updated = True

        if updated:
            self._save_index()

    async def verify_vulnerability(
        self,
        record_id: str,
        is_valid: bool,
        disclosure_status: Optional[str] = None,
    ) -> dict:
        """
        Verify a vulnerability report.

        Args:
            record_id: The vulnerability ID
            is_valid: True if vulnerability is confirmed, False if false positive
            disclosure_status: Update status (open, patched, mitigated, wontfix)
        """
        for entry in self._index.get("vulnerabilities", []):
            if entry["id"] == record_id:
                if is_valid:
                    entry["verified_count"] = entry.get("verified_count", 0) + 1
                else:
                    entry["false_positive_count"] = entry.get("false_positive_count", 0) + 1

                if disclosure_status:
                    entry["disclosure_status"] = disclosure_status
                    # Mark as public if patched/mitigated/wontfix
                    if disclosure_status in ("patched", "mitigated", "wontfix"):
                        entry["is_public"] = True

                entry["verification_date"] = datetime.now().isoformat()
                break

        self._save_index()

        # Update the file as well
        filepath = self.vulns_dir / f"{record_id}.json"
        if filepath.exists():
            content = self._read_file(filepath)
            data = json.loads(content)
            if is_valid:
                data["verified_count"] = data.get("verified_count", 0) + 1
            else:
                data["false_positive_count"] = data.get("false_positive_count", 0) + 1
            if disclosure_status:
                data["disclosure_status"] = disclosure_status
                if disclosure_status in ("patched", "mitigated", "wontfix"):
                    data["is_public"] = True
            self._write_file(filepath, json.dumps(data, indent=2))

        return {
            "success": True,
            "record_id": record_id,
            "is_valid": is_valid,
            "disclosure_status": disclosure_status,
        }

    async def get_vulnerability_feed(
        self,
        limit: int = 20,
        offset: int = 0,
        severity: Optional[str] = None,
        vuln_type: Optional[str] = None,
    ) -> list[dict]:
        """
        Get live vulnerability feed (most recent first).

        Only returns publicly disclosable vulnerabilities.
        """
        now = datetime.now()
        from datetime import timedelta

        feed = []
        for entry in self._index.get("vulnerabilities", []):
            # Check if ready for public disclosure
            is_public = entry.get("is_public", False)
            disclosure_status = entry.get("disclosure_status", "open")

            if not is_public and disclosure_status == "open":
                try:
                    timestamp = datetime.fromisoformat(entry["timestamp"])
                    deadline = timestamp + timedelta(hours=72)
                    if now < deadline:
                        continue  # Not ready for disclosure
                except (ValueError, KeyError):
                    continue

            # Apply filters
            if severity and entry.get("severity", "").lower() != severity.lower():
                continue
            if vuln_type and entry.get("vuln_type", "").lower() != vuln_type.lower():
                continue

            feed.append(entry)

        # Sort by timestamp (most recent first)
        feed.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        return feed[offset : offset + limit]

    # =========================================================================
    # Maintenance
    # =========================================================================

    async def verify_solution(self, record_id: str, success: bool) -> dict:
        """Mark a solution as verified or not."""
        for entry in self._index.get("errors", []):
            if entry["id"] == record_id:
                entry["verified"] = success if success else entry.get("verified", False)
                entry["verification_date"] = datetime.now().isoformat()
                entry["success_count"] = entry.get("success_count", 0) + (1 if success else 0)
                entry["failure_count"] = entry.get("failure_count", 0) + (0 if success else 1)
                break

        self._save_index()

        filepath = self.errors_dir / f"{record_id}.json"
        if filepath.exists():
            content = self._read_file(filepath)
            data = json.loads(content)
            data["verified"] = success if success else data.get("verified", False)
            data["success_count"] = data.get("success_count", 0) + (1 if success else 0)
            data["failure_count"] = data.get("failure_count", 0) + (0 if success else 1)
            self._write_file(filepath, json.dumps(data, indent=2))

        return {"success": True, "record_id": record_id, "verified": success}

    async def get_stats(self) -> dict:
        """Get statistics about the knowledge base."""
        vulns = self._index.get("vulnerabilities", [])

        # Count vulnerabilities by severity
        severity_counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
        for v in vulns:
            sev = v.get("severity", "")
            if sev in severity_counts:
                severity_counts[sev] += 1

        # Count by disclosure status
        status_counts = {"open": 0, "patched": 0, "mitigated": 0, "wontfix": 0}
        for v in vulns:
            status = v.get("disclosure_status", "open")
            if status in status_counts:
                status_counts[status] += 1

        return {
            "total_records": (
                len(self._index.get("errors", []))
                + len(self._index.get("decisions", []))
                + len(self._index.get("patterns", []))
                + len(vulns)
            ),
            "errors": len(self._index.get("errors", [])),
            "decisions": len(self._index.get("decisions", [])),
            "patterns": len(self._index.get("patterns", [])),
            "vulnerabilities": len(vulns),
            "vuln_by_severity": severity_counts,
            "vuln_by_status": status_counts,
            "data_dir": str(self.data_dir),
            "backups": len(list(self.backups_dir.glob("index_*.json"))),
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

        vulnerabilities = []
        for filepath in self.vulns_dir.glob("*.json"):
            try:
                content = self._read_file(filepath)
                vulnerabilities.append(json.loads(content))
            except (json.JSONDecodeError, IOError, ValueError):
                pass

        return {
            "errors": errors,
            "decisions": decisions,
            "patterns": patterns,
            "vulnerabilities": vulnerabilities,
        }

    # =========================================================================
    # Helpers
    # =========================================================================

    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity using SequenceMatcher."""
        if text1 in text2 or text2 in text1:
            return 0.8

        words1 = set(text1.split())
        words2 = set(text2.split())
        if words1 and words2:
            overlap = len(words1 & words2) / max(len(words1), len(words2))
            if overlap > 0.3:
                return 0.5 + overlap * 0.3

        return SequenceMatcher(None, text1, text2).ratio()
