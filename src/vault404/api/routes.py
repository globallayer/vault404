"""
Route handlers for the Vault404 REST API.

All endpoint handlers that interact with the storage and sync modules.
Includes rate limiting and API key authentication for write operations.
"""

import os
from typing import Optional

from fastapi import APIRouter, Depends, Request

from .models import (
    # Solution models
    SolutionSearchRequest,
    SolutionSearchResponse,
    SolutionResult,
    SolutionLogRequest,
    SolutionLogResponse,
    SolutionVerifyRequest,
    SolutionVerifyResponse,
    # Decision models
    DecisionSearchRequest,
    DecisionSearchResponse,
    DecisionResult,
    DecisionLogRequest,
    DecisionLogResponse,
    # Pattern models
    PatternSearchRequest,
    PatternSearchResponse,
    PatternResult,
    PatternLogRequest,
    PatternLogResponse,
    # Stats & health models
    StatsResponse,
    HealthResponse,
)
from .auth import require_api_key, optional_api_key
from ..storage import get_storage, Context, ErrorFix, Decision, Pattern, ErrorInfo, SolutionInfo
from ..security import redact_secrets
from ..sync.community import federated_search, CommunityBrain
from ..sync.anonymizer import anonymize_record
from ..sync.contribution import ContributionManager


# API version
API_VERSION = "0.1.3"

# Enable community search via environment variable
COMMUNITY_ENABLED = os.environ.get("VAULT404_COMMUNITY", "").lower() in ("true", "1", "yes")

# Rate limit settings (requests per minute)
SEARCH_RATE_LIMIT = os.environ.get("VAULT404_SEARCH_RATE_LIMIT", "60/minute")
WRITE_RATE_LIMIT = os.environ.get("VAULT404_WRITE_RATE_LIMIT", "20/minute")
AUTH_RATE_LIMIT = os.environ.get(
    "VAULT404_AUTH_RATE_LIMIT", "120/minute"
)  # Higher for authenticated

# Create routers
solutions_router = APIRouter(prefix="/solutions", tags=["solutions"])
decisions_router = APIRouter(prefix="/decisions", tags=["decisions"])
patterns_router = APIRouter(prefix="/patterns", tags=["patterns"])
stats_router = APIRouter(tags=["stats"])


# Global contribution manager
_contrib: Optional[ContributionManager] = None


def get_contribution_manager() -> ContributionManager:
    global _contrib
    if _contrib is None:
        _contrib = ContributionManager()
    return _contrib


# Rate limiter helper - will be injected by server.py if enabled
def get_rate_limiter():
    """Get the rate limiter instance if available."""
    try:
        from slowapi import Limiter
        from slowapi.util import get_remote_address

        return Limiter(key_func=get_remote_address)
    except ImportError:
        return None


# =============================================================================
# Solution Routes
# =============================================================================


@solutions_router.post("/search", response_model=SolutionSearchResponse)
async def search_solutions(
    request: SolutionSearchRequest,
    req: Request,
    api_key: Optional[str] = Depends(optional_api_key),
) -> SolutionSearchResponse:
    """
    Find solutions for an error message.

    Searches local storage and optionally the community brain for matching solutions.
    Results are ranked by relevance and context match.

    Rate limit: 60/minute (unauthenticated), 120/minute (authenticated)
    """
    storage = get_storage()

    # Build context from request
    context = None
    if any(
        [request.language, request.framework, request.database, request.platform, request.category]
    ):
        context = Context(
            language=request.language,
            framework=request.framework,
            database=request.database,
            platform=request.platform,
            category=request.category,
        )

    # Search local storage
    local_results = await storage.find_solutions(
        error_message=request.error_message,
        context=context,
        limit=request.limit,
    )

    # Optionally include community results
    all_results = local_results
    source = "local"
    community_count = 0

    if COMMUNITY_ENABLED:
        try:
            context_dict = (
                {
                    "language": request.language,
                    "framework": request.framework,
                    "database": request.database,
                    "platform": request.platform,
                }
                if context
                else None
            )

            all_results = await federated_search(
                request.error_message,
                local_results,
                context_dict,
                request.limit,
            )
            community_count = sum(1 for r in all_results if r.get("source") == "community")
            if community_count > 0:
                source = "federated"
        except Exception:
            pass  # Fall back to local only

    if not all_results:
        return SolutionSearchResponse(
            found=False,
            message="No matching solutions found in Vault404",
            solutions=[],
            source=source,
            suggestion="After fixing this error, use the log endpoint to save the solution.",
        )

    # Transform results
    solutions = [
        SolutionResult(
            id=r.get("id", ""),
            solution=r.get("solution", ""),
            original_error=r.get("error", ""),
            context=r.get("context", {}),
            confidence=round(r.get("score", 0), 2),
            verified=r.get("verified", False),
            source=r.get("source", "local"),
        )
        for r in all_results
    ]

    message = f"Found {len(all_results)} potential solution(s)"
    if community_count > 0:
        message += f" ({community_count} from community)"

    return SolutionSearchResponse(
        found=True,
        message=message,
        solutions=solutions,
        source=source,
    )


@solutions_router.post("/log", response_model=SolutionLogResponse)
async def log_solution(
    request: SolutionLogRequest,
    api_key: str = Depends(require_api_key),
) -> SolutionLogResponse:
    """
    Log an error fix to Vault404.

    **Requires API key authentication.**

    All inputs are automatically scanned for secrets (API keys, passwords, tokens)
    and redacted before storage.

    Rate limit: 20/minute
    """
    storage = get_storage()

    # Redact secrets
    safe_error_message = redact_secrets(request.error_message)
    safe_solution = redact_secrets(request.solution)
    safe_stack_trace = redact_secrets(request.stack_trace) if request.stack_trace else None
    safe_code_change = redact_secrets(request.code_change) if request.code_change else None

    # Create record
    record = ErrorFix(
        error=ErrorInfo(
            message=safe_error_message,
            error_type=request.error_type,
            stack_trace=safe_stack_trace,
            file=request.file,
            line=request.line,
        ),
        solution=SolutionInfo(
            description=safe_solution,
            code_change=safe_code_change,
            files_modified=request.files_modified or [],
        ),
        context=Context(
            project=request.project,
            language=request.language,
            framework=request.framework,
            database=request.database,
            platform=request.platform,
            category=request.category,
        ),
        time_to_solve=request.time_to_solve,
        verified=request.verified,
    )

    # Store
    result = await storage.store_error_fix(record)

    secrets_redacted = (
        safe_error_message != request.error_message or safe_solution != request.solution
    )

    return SolutionLogResponse(
        id=record.id,
        success=result.get("success", False),
        message=f"Logged error fix: {safe_error_message[:50]}... -> {safe_solution[:50]}...",
        secrets_redacted=secrets_redacted,
    )


@solutions_router.post("/verify", response_model=SolutionVerifyResponse)
async def verify_solution(
    request: SolutionVerifyRequest,
    api_key: str = Depends(require_api_key),
) -> SolutionVerifyResponse:
    """
    Mark a solution as verified (worked or didn't work).

    **Requires API key authentication.**

    Verified solutions are automatically contributed to the community brain
    to help other AI agents learn.

    Rate limit: 20/minute
    """
    storage = get_storage()
    contrib = get_contribution_manager()

    # Verify in storage
    await storage.verify_solution(request.id, request.success)

    contributed = False
    message = (
        f"Marked solution {request.id} as {'successful' if request.success else 'unsuccessful'}"
    )

    # Auto-contribute if successful
    if request.success:
        import json

        filepath = storage.errors_dir / f"{request.id}.json"
        if filepath.exists():
            try:
                record = json.loads(filepath.read_text(encoding="utf-8"))
                anon = anonymize_record(record)
                contrib_result = await contrib.confirm_contribution(request.id, anon)

                if contrib_result.get("success"):
                    contributed = True
                    message += " -> Auto-contributed to community brain."
            except Exception:
                pass  # Don't fail verification if contribution fails

    return SolutionVerifyResponse(
        success=True,
        record_id=request.id,
        verified=request.success,
        contributed_to_community=contributed,
        message=message,
    )


# =============================================================================
# Decision Routes
# =============================================================================


@decisions_router.post("/search", response_model=DecisionSearchResponse)
async def search_decisions(
    request: DecisionSearchRequest,
    api_key: Optional[str] = Depends(optional_api_key),
) -> DecisionSearchResponse:
    """
    Find past decisions on a topic.

    Useful for consistency checking before making architectural choices.

    Rate limit: 60/minute (unauthenticated), 120/minute (authenticated)
    """
    storage = get_storage()

    context = None
    if request.project or request.component:
        context = Context(project=request.project, category=request.component)

    results = await storage.find_decisions(
        topic=request.topic,
        context=context,
        limit=request.limit,
    )

    if not results:
        return DecisionSearchResponse(
            found=False,
            message=f"No past decisions found for: {request.topic}",
            decisions=[],
            suggestion="After making a decision, use the log endpoint to save it.",
        )

    decisions = [
        DecisionResult(
            id=r.get("id", ""),
            title=r.get("title", ""),
            choice=r.get("choice", ""),
            relevance=round(r.get("similarity", 0), 2),
        )
        for r in results
    ]

    return DecisionSearchResponse(
        found=True,
        message=f"Found {len(results)} relevant decision(s)",
        decisions=decisions,
    )


@decisions_router.post("/log", response_model=DecisionLogResponse)
async def log_decision(
    request: DecisionLogRequest,
    api_key: str = Depends(require_api_key),
) -> DecisionLogResponse:
    """
    Log an architectural decision to Vault404.

    **Requires API key authentication.**

    Records the decision, alternatives considered, and rationale for future reference.

    Rate limit: 20/minute
    """
    storage = get_storage()

    record = Decision(
        title=request.title,
        choice=request.choice,
        alternatives=request.alternatives or [],
        pros=request.pros or [],
        cons=request.cons or [],
        deciding_factor=request.deciding_factor,
        context=Context(
            project=request.project,
            language=request.language,
            framework=request.framework,
            category=request.component,
        ),
    )

    result = await storage.store_decision(record)

    return DecisionLogResponse(
        id=record.id,
        success=result.get("success", False),
        message=f"Logged decision: {request.title} -> {request.choice}",
    )


# =============================================================================
# Pattern Routes
# =============================================================================


@patterns_router.post("/search", response_model=PatternSearchResponse)
async def search_patterns(
    request: PatternSearchRequest,
    api_key: Optional[str] = Depends(optional_api_key),
) -> PatternSearchResponse:
    """
    Find reusable patterns for a problem.

    Check this before implementing solutions to leverage existing patterns.

    Rate limit: 60/minute (unauthenticated), 120/minute (authenticated)
    """
    storage = get_storage()

    results = await storage.find_patterns(
        problem=request.problem,
        category=request.category,
        limit=request.limit,
    )

    if not results:
        return PatternSearchResponse(
            found=False,
            message=f"No patterns found for: {request.problem}",
            patterns=[],
            suggestion="After solving this, use the log endpoint to save the pattern.",
        )

    patterns = [
        PatternResult(
            id=r.get("id", ""),
            name=r.get("name", ""),
            category=r.get("category", ""),
            problem=r.get("problem", ""),
            solution=r.get("solution", ""),
            relevance=round(r.get("similarity", 0), 2),
        )
        for r in results
    ]

    return PatternSearchResponse(
        found=True,
        message=f"Found {len(results)} relevant pattern(s)",
        patterns=patterns,
    )


@patterns_router.post("/log", response_model=PatternLogResponse)
async def log_pattern(
    request: PatternLogRequest,
    api_key: str = Depends(require_api_key),
) -> PatternLogResponse:
    """
    Log a reusable pattern to Vault404.

    **Requires API key authentication.**

    Code snippets are automatically scanned for secrets and redacted.

    Rate limit: 20/minute
    """
    storage = get_storage()

    # Redact secrets from code
    safe_before = redact_secrets(request.before_code) if request.before_code else None
    safe_after = redact_secrets(request.after_code) if request.after_code else None

    record = Pattern(
        name=request.name,
        category=request.category,
        problem=request.problem,
        solution=request.solution,
        languages=request.languages or [],
        frameworks=request.frameworks or [],
        databases=request.databases or [],
        scenarios=request.scenarios or [],
        before_code=safe_before,
        after_code=safe_after,
        explanation=request.explanation,
    )

    result = await storage.store_pattern(record)

    return PatternLogResponse(
        id=record.id,
        success=result.get("success", False),
        message=f"Logged pattern: {request.name}",
    )


# =============================================================================
# Stats & Health Routes
# =============================================================================


@stats_router.get("/stats", response_model=StatsResponse)
async def get_stats() -> StatsResponse:
    """
    Get knowledge base statistics.

    Returns counts of all stored records and the data directory location.
    """
    storage = get_storage()
    stats = await storage.get_stats()

    return StatsResponse(
        total_records=stats.get("total_records", 0),
        error_fixes=stats.get("errors", 0),
        decisions=stats.get("decisions", 0),
        patterns=stats.get("patterns", 0),
        data_directory=stats.get("data_dir", ""),
    )


@stats_router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.

    Returns API status and version information.
    """
    storage_available = True
    try:
        storage = get_storage()
        # Quick check that storage is accessible
        await storage.get_stats()
    except Exception:
        storage_available = False

    return HealthResponse(
        status="ok" if storage_available else "degraded",
        version=API_VERSION,
        storage_available=storage_available,
    )


@stats_router.get("/badge/{metric}")
async def get_badge(metric: str) -> dict:
    """
    Get a Shields.io compatible badge for community stats.

    Supported metrics:
    - fixes: Total error fixes in the community brain
    - contributors: Unique contributors
    - brain: Total solutions (all types)

    Returns JSON in Shields.io endpoint format:
    https://shields.io/badges/endpoint-badge
    """
    community = CommunityBrain()
    stats = await community.get_stats()

    badges = {
        "fixes": {
            "schemaVersion": 1,
            "label": "fixes",
            "message": str(stats.get("fixes", 0)),
            "color": "blue",
        },
        "contributors": {
            "schemaVersion": 1,
            "label": "contributors",
            "message": str(stats.get("unique_contributors", 0)),
            "color": "green",
        },
        "brain": {
            "schemaVersion": 1,
            "label": "brain size",
            "message": f"{stats.get('total', 0)} solutions",
            "color": "purple",
        },
    }

    return badges.get(metric, badges["brain"])
