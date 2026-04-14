"""
Community Brain API Client for vault404

Connects to the shared knowledge repository where verified solutions
from all vault404 users are aggregated.

The community brain:
- Only accepts VERIFIED solutions
- All data is ANONYMIZED before upload
- Ranks results by verification count and recency
- Provides federated search (local + community)
"""

import os
import hashlib
from datetime import datetime
from typing import Optional, List, Dict

# Try to import httpx for async HTTP (preferred), fallback to requests
try:
    import httpx
    HTTP_CLIENT = "httpx"
except ImportError:
    try:
        import requests  # noqa: F401 - used conditionally when HTTP_CLIENT == "requests"
        HTTP_CLIENT = "requests"
    except ImportError:
        HTTP_CLIENT = None


# Default community brain endpoint
DEFAULT_API_URL = "https://sbbhtxxegxkqjbfqcrwz.supabase.co/rest/v1"
DEFAULT_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNiYmh0eHhlZ3hrcWpiZnFjcnd6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzM3ODU4MjcsImV4cCI6MjA4OTM2MTgyN30.L4D9egjGWUbfpbGkZogVWPia4y6GBKjvJ0FhjB8fuIc"

# Environment variable overrides
API_URL = os.environ.get("VAULT404_API_URL", DEFAULT_API_URL)
API_KEY = os.environ.get("VAULT404_API_KEY", DEFAULT_ANON_KEY)


class CommunityBrainError(Exception):
    """Raised when community brain operations fail."""
    pass


class CommunityBrain:
    """
    Client for the vault404 Community Brain.

    The community brain stores anonymized, verified solutions from all users.
    """

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.api_url = api_url or API_URL
        self.api_key = api_key or API_KEY
        self._client = None

        if not HTTP_CLIENT:
            raise CommunityBrainError(
                "No HTTP client available. Install httpx: pip install httpx"
            )

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests."""
        headers = {
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        if self.api_key:
            headers["apikey"] = self.api_key
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def contribute(self, anonymized_record: dict) -> dict:
        """
        Contribute an anonymized solution to the community brain.

        IMPORTANT: Only verified solutions should be contributed.
        The record should already be anonymized via anonymize_record().

        Args:
            anonymized_record: Pre-anonymized record from anonymizer.py

        Returns:
            dict with contribution status
        """
        if not anonymized_record.get("verified"):
            return {
                "success": False,
                "reason": "Only verified solutions can be contributed",
            }

        # Generate contributor ID (anonymous but consistent for dedup)
        machine_id = self._get_machine_id()

        payload = {
            "content_hash": anonymized_record.get("content_hash"),
            "record_type": anonymized_record.get("type", "error_fix"),
            "category": anonymized_record.get("category"),
            "language": anonymized_record.get("language"),
            "framework": anonymized_record.get("framework"),
            "database": anonymized_record.get("database"),
            "platform": anonymized_record.get("platform"),
            "error_data": anonymized_record.get("error"),
            "solution_data": anonymized_record.get("solution"),
            "contributor_hash": machine_id,
            "verification_count": anonymized_record.get("success_count", 1),
            "contributed_at": datetime.utcnow().isoformat(),
        }

        try:
            if HTTP_CLIENT == "httpx":
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self.api_url}/community_solutions",
                        headers=self._get_headers(),
                        json=payload,
                        timeout=10.0,
                    )
                    response.raise_for_status()
                    data = response.json()
            else:
                # Sync fallback
                import requests
                response = requests.post(
                    f"{self.api_url}/community_solutions",
                    headers=self._get_headers(),
                    json=payload,
                    timeout=10,
                )
                response.raise_for_status()
                data = response.json()

            return {
                "success": True,
                "message": "Contributed to community brain",
                "record_id": data[0].get("id") if isinstance(data, list) else data.get("id"),
            }

        except Exception as e:
            return {
                "success": False,
                "reason": f"Failed to contribute: {str(e)}",
                "offline_mode": True,
            }

    async def search_solutions(
        self,
        query: str,
        context: Optional[dict] = None,
        limit: int = 5,
    ) -> List[dict]:
        """
        Search the community brain for solutions.

        Args:
            query: Error message or search query
            context: Optional context (language, framework, etc.)
            limit: Maximum results to return

        Returns:
            List of matching solutions from community
        """
        params = {
            "select": "*",
            "order": "verification_count.desc,contributed_at.desc",
            "limit": limit,
        }

        # Add context filters
        if context:
            if context.get("language"):
                params["language"] = f"eq.{context['language']}"
            if context.get("framework"):
                params["framework"] = f"eq.{context['framework']}"
            if context.get("database"):
                params["database"] = f"eq.{context['database']}"
            if context.get("platform"):
                params["platform"] = f"eq.{context['platform']}"

        try:
            if HTTP_CLIENT == "httpx":
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{self.api_url}/community_solutions",
                        headers=self._get_headers(),
                        params=params,
                        timeout=10.0,
                    )
                    response.raise_for_status()
                    results = response.json()
            else:
                import requests
                response = requests.get(
                    f"{self.api_url}/community_solutions",
                    headers=self._get_headers(),
                    params=params,
                    timeout=10,
                )
                response.raise_for_status()
                results = response.json()

            # Transform to standard format
            return [
                {
                    "id": r.get("id"),
                    "source": "community",
                    "error": r.get("error_data", {}).get("message", ""),
                    "solution": r.get("solution_data", {}).get("description", ""),
                    "context": {
                        "language": r.get("language"),
                        "framework": r.get("framework"),
                        "database": r.get("database"),
                        "platform": r.get("platform"),
                    },
                    "verification_count": r.get("verification_count", 0),
                    "score": self._calculate_relevance(query, r),
                }
                for r in results
            ]

        except Exception:
            # Fail silently - local results will still work
            return []

    async def search_decisions(
        self,
        topic: str,
        context: Optional[dict] = None,
        limit: int = 5,
    ) -> List[dict]:
        """Search community for architectural decisions."""
        params = {
            "select": "*",
            "record_type": "eq.decision",
            "order": "verification_count.desc",
            "limit": limit,
        }

        try:
            if HTTP_CLIENT == "httpx":
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{self.api_url}/community_solutions",
                        headers=self._get_headers(),
                        params=params,
                        timeout=10.0,
                    )
                    response.raise_for_status()
                    return response.json()
            else:
                import requests
                response = requests.get(
                    f"{self.api_url}/community_solutions",
                    headers=self._get_headers(),
                    params=params,
                    timeout=10,
                )
                response.raise_for_status()
                return response.json()
        except Exception:
            return []

    async def search_patterns(
        self,
        problem: str,
        category: Optional[str] = None,
        limit: int = 5,
    ) -> List[dict]:
        """Search community for reusable patterns."""
        params = {
            "select": "*",
            "record_type": "eq.pattern",
            "order": "verification_count.desc",
            "limit": limit,
        }

        if category:
            params["category"] = f"eq.{category}"

        try:
            if HTTP_CLIENT == "httpx":
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{self.api_url}/community_solutions",
                        headers=self._get_headers(),
                        params=params,
                        timeout=10.0,
                    )
                    response.raise_for_status()
                    return response.json()
            else:
                import requests
                response = requests.get(
                    f"{self.api_url}/community_solutions",
                    headers=self._get_headers(),
                    params=params,
                    timeout=10,
                )
                response.raise_for_status()
                return response.json()
        except Exception:
            return []

    async def upvote(self, record_id: str) -> dict:
        """
        Upvote a community solution (increases verification count).

        Called when a user confirms a community solution worked for them.
        """
        try:
            if HTTP_CLIENT == "httpx":
                async with httpx.AsyncClient() as client:
                    # Increment verification_count
                    response = await client.patch(
                        f"{self.api_url}/community_solutions",
                        headers=self._get_headers(),
                        params={"id": f"eq.{record_id}"},
                        json={"verification_count": "verification_count + 1"},
                        timeout=10.0,
                    )
                    response.raise_for_status()
            return {"success": True, "message": "Upvoted solution"}
        except Exception as e:
            return {"success": False, "reason": str(e)}

    def _get_machine_id(self) -> str:
        """Generate anonymous but consistent machine identifier."""
        # Use a hash of machine-specific info
        import platform
        import uuid

        machine_info = f"{platform.node()}-{platform.machine()}-{uuid.getnode()}"
        return hashlib.sha256(machine_info.encode()).hexdigest()[:16]

    def _calculate_relevance(self, query: str, record: dict) -> float:
        """Calculate relevance score between query and record."""
        error_msg = record.get("error_data", {}).get("message", "").lower()
        solution = record.get("solution_data", {}).get("description", "").lower()
        query_lower = query.lower()

        # Simple word overlap scoring
        query_words = set(query_lower.split())
        error_words = set(error_msg.split())
        solution_words = set(solution.split())

        error_overlap = len(query_words & error_words) / max(len(query_words), 1)
        solution_overlap = len(query_words & solution_words) / max(len(query_words), 1)

        # Boost by verification count
        verification_boost = min(record.get("verification_count", 0) / 100, 0.2)

        return min((error_overlap * 0.6 + solution_overlap * 0.2 + verification_boost), 1.0)


# Global instance
_community: Optional[CommunityBrain] = None


def get_community_brain() -> CommunityBrain:
    """Get the community brain client instance."""
    global _community
    if _community is None:
        _community = CommunityBrain()
    return _community


async def federated_search(
    query: str,
    local_results: List[dict],
    context: Optional[dict] = None,
    limit: int = 5,
) -> List[dict]:
    """
    Combine local and community results into ranked list.

    Local results are prioritized (you trust your own fixes).
    Community results fill in gaps.

    Args:
        query: Search query
        local_results: Results from local storage
        context: Optional context filters
        limit: Max total results

    Returns:
        Combined, ranked list of results
    """
    community = get_community_brain()

    # Get community results
    community_results = await community.search_solutions(query, context, limit)

    # Combine and deduplicate
    seen_hashes = set()
    combined = []

    # Local results first (higher trust)
    for r in local_results:
        hash_key = f"{r.get('error', '')[:50]}-{r.get('solution', '')[:50]}"
        content_hash = hashlib.md5(hash_key.encode()).hexdigest()

        if content_hash not in seen_hashes:
            seen_hashes.add(content_hash)
            r["source"] = "local"
            r["trust"] = "high"
            combined.append(r)

    # Community results (lower trust)
    for r in community_results:
        hash_key = f"{r.get('error', '')[:50]}-{r.get('solution', '')[:50]}"
        content_hash = hashlib.md5(hash_key.encode()).hexdigest()

        if content_hash not in seen_hashes:
            seen_hashes.add(content_hash)
            r["trust"] = "community"
            combined.append(r)

    # Sort by score (local bias already applied)
    combined.sort(key=lambda x: x.get("score", 0), reverse=True)

    return combined[:limit]
