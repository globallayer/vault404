"""Adapter for mempalace MCP server - wraps mempalace as storage backend"""

from typing import Optional
from datetime import datetime

from .schemas import ErrorFix, Decision, Pattern, Context


class MempalaceAdapter:
    """
    Wraps mempalace MCP server for Agent Brain storage.

    Uses mempalace's structure:
    - Drawers: Store raw records in AAAK format
    - Knowledge Graph: Store entity relationships
    - Search: Semantic search across records
    - Diary: Session logging
    """

    def __init__(self, wing: str = "agent_brain"):
        self.wing = wing
        self.rooms = {
            "errors": "error_fix records",
            "decisions": "architectural decisions",
            "patterns": "reusable patterns",
            "index": "indexes and stats",
        }

    # =========================================================================
    # Recording Methods
    # =========================================================================

    async def store_error_fix(self, record: ErrorFix) -> dict:
        """Store an error/fix record"""
        # Store in drawer
        drawer_result = await self._add_drawer(
            room="errors",
            content=record.to_aaak(),
            source_file=record.error.file or "",
        )

        # Add to knowledge graph
        await self._kg_add(
            subject=record.error.error_type or "Error",
            predicate="solved_by",
            object=record.solution.description[:50],
            valid_from=record.timestamp.strftime("%Y-%m-%d"),
        )

        # Link to context if present
        if record.context.project:
            await self._kg_add(
                subject=record.context.project,
                predicate="had_error",
                object=record.error.message[:50],
            )

        return {
            "success": True,
            "record_id": record.id,
            "drawer_id": drawer_result.get("drawer_id"),
        }

    async def store_decision(self, record: Decision) -> dict:
        """Store a decision record"""
        drawer_result = await self._add_drawer(
            room="decisions",
            content=record.to_aaak(),
        )

        # Add to knowledge graph
        await self._kg_add(
            subject=record.context.project or "Project",
            predicate="decided",
            object=record.choice,
            valid_from=record.timestamp.strftime("%Y-%m-%d"),
        )

        # Record alternatives considered
        for alt in record.alternatives:
            await self._kg_add(
                subject=record.choice,
                predicate="chosen_over",
                object=alt,
            )

        return {
            "success": True,
            "record_id": record.id,
            "drawer_id": drawer_result.get("drawer_id"),
        }

    async def store_pattern(self, record: Pattern) -> dict:
        """Store a pattern record"""
        drawer_result = await self._add_drawer(
            room="patterns",
            content=record.to_aaak(),
        )

        # Add to knowledge graph
        await self._kg_add(
            subject=record.name,
            predicate="is_type",
            object="Pattern",
        )
        await self._kg_add(
            subject=record.name,
            predicate="solves",
            object=record.problem[:50],
        )
        await self._kg_add(
            subject=record.name,
            predicate="category",
            object=record.category,
        )

        return {
            "success": True,
            "record_id": record.id,
            "drawer_id": drawer_result.get("drawer_id"),
        }

    # =========================================================================
    # Query Methods
    # =========================================================================

    async def find_solutions(
        self,
        error_message: str,
        context: Optional[Context] = None,
        limit: int = 5,
    ) -> list[dict]:
        """
        Find solutions for an error.

        Uses semantic search + context matching for ranking.
        """
        # Semantic search in errors room
        results = await self._search(
            query=error_message,
            room="errors",
            limit=limit * 2,  # Get more, then filter
        )

        # Parse and rank results
        ranked = []
        for result in results:
            parsed = self._parse_aaak_error_fix(result.get("text", ""))
            if not parsed:
                continue

            # Calculate match score
            score = result.get("similarity", 0.5)
            if context and parsed.get("context"):
                ctx_score = self._context_match_score(context, parsed["context"])
                score = (score + ctx_score) / 2

            ranked.append({
                "solution": parsed.get("solution", ""),
                "error": parsed.get("error", ""),
                "context": parsed.get("context", {}),
                "score": score,
                "verified": parsed.get("verified", False),
                "source": result,
            })

        # Sort by score and return top results
        ranked.sort(key=lambda x: x["score"], reverse=True)
        return ranked[:limit]

    async def find_decisions(
        self,
        topic: str,
        context: Optional[Context] = None,
        limit: int = 5,
    ) -> list[dict]:
        """Find past decisions on a topic"""
        results = await self._search(
            query=topic,
            room="decisions",
            limit=limit,
        )

        return [
            {
                "text": r.get("text", ""),
                "similarity": r.get("similarity", 0),
                "source_file": r.get("source_file", ""),
            }
            for r in results
        ]

    async def find_patterns(
        self,
        problem: str,
        category: Optional[str] = None,
        limit: int = 5,
    ) -> list[dict]:
        """Find patterns for a problem"""
        query = f"{category} {problem}" if category else problem
        results = await self._search(
            query=query,
            room="patterns",
            limit=limit,
        )

        return [
            {
                "text": r.get("text", ""),
                "similarity": r.get("similarity", 0),
            }
            for r in results
        ]

    # =========================================================================
    # Maintenance Methods
    # =========================================================================

    async def verify_solution(self, record_id: str, success: bool) -> dict:
        """Record whether a solution worked or not"""
        # This would update the record's success/failure count
        # For now, log to diary
        await self._diary_write(
            entry=f"VERIFY|{record_id}|{'SUCCESS' if success else 'FAILED'}|{datetime.now().isoformat()}",
            topic="verification",
        )
        return {"success": True, "record_id": record_id, "verified": success}

    async def get_stats(self) -> dict:
        """Get statistics about the knowledge base"""
        status = await self._status()
        kg_stats = await self._kg_stats()

        return {
            "total_drawers": status.get("total_drawers", 0),
            "rooms": status.get("rooms", {}),
            "kg_entities": kg_stats.get("entities", 0),
            "kg_triples": kg_stats.get("triples", 0),
            "relationship_types": kg_stats.get("relationship_types", []),
        }

    # =========================================================================
    # Private Methods - Mempalace MCP Wrappers
    # =========================================================================

    async def _add_drawer(
        self,
        room: str,
        content: str,
        source_file: str = "",
    ) -> dict:
        """Wrap mempalace_add_drawer"""
        # In a real implementation, this would call the MCP tool
        # For now, return a mock response
        return {
            "success": True,
            "drawer_id": f"drawer_{self.wing}_{room}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "wing": self.wing,
            "room": room,
        }

    async def _search(
        self,
        query: str,
        room: Optional[str] = None,
        limit: int = 5,
    ) -> list[dict]:
        """Wrap mempalace_search"""
        # In a real implementation, this would call the MCP tool
        return []

    async def _kg_add(
        self,
        subject: str,
        predicate: str,
        object: str,
        valid_from: Optional[str] = None,
    ) -> dict:
        """Wrap mempalace_kg_add"""
        return {"success": True}

    async def _kg_query(self, entity: str) -> dict:
        """Wrap mempalace_kg_query"""
        return {"entity": entity, "facts": []}

    async def _kg_stats(self) -> dict:
        """Wrap mempalace_kg_stats"""
        return {"entities": 0, "triples": 0, "relationship_types": []}

    async def _status(self) -> dict:
        """Wrap mempalace_status"""
        return {"total_drawers": 0, "rooms": {}}

    async def _diary_write(self, entry: str, topic: str = "general") -> dict:
        """Wrap mempalace_diary_write"""
        return {"success": True}

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _parse_aaak_error_fix(self, aaak: str) -> Optional[dict]:
        """Parse an AAAK-formatted error/fix record"""
        if not aaak.startswith("ERROR_FIX|"):
            return None

        parts = aaak.split("|")
        result = {"type": "error_fix", "context": {}}

        for part in parts[1:]:
            if part.startswith("ERR:"):
                result["error"] = part[4:]
            elif part.startswith("SOL:"):
                result["solution"] = part[4:]
            elif part.startswith("PROJ:"):
                result["context"]["project"] = part[5:]
            elif part.startswith("LANG:"):
                result["context"]["language"] = part[5:]
            elif part.startswith("FW:"):
                result["context"]["framework"] = part[3:]
            elif part.startswith("DB:"):
                result["context"]["database"] = part[3:]
            elif part.startswith("PLAT:"):
                result["context"]["platform"] = part[5:]
            elif part.startswith("CONF:"):
                try:
                    result["confidence"] = float(part[5:])
                except ValueError:
                    pass
            elif part == "VERIFIED":
                result["verified"] = True
            elif part == "UNVERIFIED":
                result["verified"] = False

        return result

    def _context_match_score(self, ctx1: Context, ctx2_dict: dict) -> float:
        """Calculate context match score between Context and dict"""
        ctx2 = Context(**ctx2_dict)
        return ctx1.match_score(ctx2)
