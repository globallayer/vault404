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
    # Vulnerability models
    VulnerabilityReportRequest,
    VulnerabilityReportResponse,
    VulnerabilitySearchRequest,
    VulnerabilitySearchResponse,
    VulnerabilitySearchResult,
    VulnerabilityFeedResponse,
    VulnerabilityFeedItem,
    VulnerabilityVerifyRequest,
    VulnerabilityVerifyResponse,
    VulnerabilityStatsResponse,
    # Stats & health models
    StatsResponse,
    HealthResponse,
)
from .auth import require_api_key, optional_api_key
from ..storage import get_storage, Context, ErrorFix, Decision, Pattern, ErrorInfo, SolutionInfo, VulnerabilityReport
from ..security import redact_secrets, full_vulnerability_redaction
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
vulns_router = APIRouter(prefix="/vulns", tags=["vulnerabilities"])
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
# Vulnerability Routes
# =============================================================================


@vulns_router.post("/report", response_model=VulnerabilityReportResponse)
async def report_vulnerability(
    request: VulnerabilityReportRequest,
    api_key: str = Depends(require_api_key),
) -> VulnerabilityReportResponse:
    """
    Report an AI-discovered vulnerability.

    **Requires API key authentication.**

    Vulnerabilities follow responsible disclosure:
    - 72-hour delay before unpatched vulns appear in public feed
    - Patched/mitigated vulns are immediately public
    - Pattern snippets are anonymized (no file paths, repo names, variable names)

    Rate limit: 20/minute
    """
    storage = get_storage()

    # Full anonymization - secrets + file paths + identifiers
    safe_pattern = full_vulnerability_redaction(request.pattern_snippet)
    safe_fix = full_vulnerability_redaction(request.fix_snippet) if request.fix_snippet else None
    safe_description = full_vulnerability_redaction(request.description)
    safe_remediation = full_vulnerability_redaction(request.remediation) if request.remediation else None

    # Create vulnerability record
    record = VulnerabilityReport(
        vuln_type=request.vuln_type,
        severity=request.severity,
        cwe_id=request.cwe_id,
        language=request.language,
        framework=request.framework,
        database=request.database,
        platform=request.platform,
        pattern_snippet=safe_pattern,
        fix_snippet=safe_fix,
        description=safe_description,
        impact=request.impact,
        remediation=safe_remediation,
        disclosure_status="open",  # New vulns always start as open
        disclosure_delay_hours=72,  # Default 72-hour responsible disclosure
        reported_by_agent=request.reported_by_agent or "unknown",
    )

    # Store
    result = await storage.store_vulnerability(record)

    secrets_redacted = (
        safe_pattern != request.pattern_snippet
        or safe_description != request.description
    )

    return VulnerabilityReportResponse(
        id=record.id,
        success=result.get("success", False),
        message=f"Reported {request.severity} {request.vuln_type} vulnerability",
        disclosure_delay_hours=record.disclosure_delay_hours,
        is_public=record.is_public,
    )


@vulns_router.get("/feed", response_model=VulnerabilityFeedResponse)
async def get_vulnerability_feed(
    limit: int = 20,
    offset: int = 0,
    severity: str = None,
    vuln_type: str = None,
    api_key: str = Depends(optional_api_key),
) -> VulnerabilityFeedResponse:
    """
    Get the live vulnerability feed.

    Returns publicly disclosable vulnerabilities (most recent first).
    Respects 72-hour responsible disclosure delay for unpatched vulns.

    Query parameters:
    - limit: Max results (default 20, max 100)
    - offset: Pagination offset
    - severity: Filter by severity (Critical, High, Medium, Low)
    - vuln_type: Filter by type (SQLi, XSS, SSRF, RCE, etc.)

    Rate limit: 60/minute (unauthenticated), 120/minute (authenticated)
    """
    storage = get_storage()

    # Clamp limit
    limit = min(max(1, limit), 100)

    # Get feed from storage (request one extra to check has_more)
    feed = await storage.get_vulnerability_feed(
        limit=limit + 1,
        offset=offset,
        severity=severity,
        vuln_type=vuln_type,
    )

    # Check if there are more items
    has_more = len(feed) > limit
    feed = feed[:limit]

    def time_ago(timestamp_str: str) -> str:
        """Convert timestamp to human-readable time ago."""
        try:
            from datetime import datetime
            ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            now = datetime.now()
            delta = now - ts
            if delta.days > 0:
                return f"{delta.days}d ago"
            hours = delta.seconds // 3600
            if hours > 0:
                return f"{hours}h ago"
            minutes = delta.seconds // 60
            return f"{minutes}m ago" if minutes > 0 else "just now"
        except Exception:
            return "unknown"

    items = [
        VulnerabilityFeedItem(
            id=v.get("id", ""),
            vuln_type=v.get("vuln_type", ""),
            severity=v.get("severity", ""),
            language=v.get("language"),
            framework=v.get("framework"),
            description=v.get("description", ""),
            pattern_snippet=v.get("pattern_snippet", ""),
            fix_snippet=v.get("fix_snippet"),
            disclosure_status=v.get("disclosure_status", "open"),
            reported_by_agent=v.get("reported_by_agent", "unknown"),
            verified_count=v.get("verified_count", 0),
            timestamp=v.get("timestamp", ""),
            time_ago=time_ago(v.get("timestamp", "")),
        )
        for v in feed
    ]

    return VulnerabilityFeedResponse(
        total=len(items),
        items=items,
        has_more=has_more,
    )


@vulns_router.post("/search", response_model=VulnerabilitySearchResponse)
async def search_vulnerabilities(
    request: VulnerabilitySearchRequest,
    api_key: str = Depends(optional_api_key),
) -> VulnerabilitySearchResponse:
    """
    Search for similar vulnerabilities.

    Uses semantic search to find vulnerabilities matching your query.
    Useful for checking if a vulnerability pattern has been seen before.

    Rate limit: 60/minute (unauthenticated), 120/minute (authenticated)
    """
    storage = get_storage()

    results = await storage.find_vulnerabilities(
        query=request.query,
        vuln_type=request.vuln_type,
        severity=request.severity,
        language=request.language,
        framework=request.framework,
        include_private=False,  # Public API never shows private vulns
        limit=request.limit or 10,
    )

    if not results:
        return VulnerabilitySearchResponse(
            found=False,
            message="No matching vulnerabilities found. If you've found a new vulnerability, use the /report endpoint to log it.",
            results=[],
            total=0,
        )

    search_results = [
        VulnerabilitySearchResult(
            id=r.get("id", ""),
            vuln_type=r.get("vuln_type", ""),
            severity=r.get("severity", ""),
            language=r.get("language"),
            framework=r.get("framework"),
            description=r.get("description", ""),
            pattern_snippet=r.get("pattern_snippet", ""),
            fix_snippet=r.get("fix_snippet"),
            relevance=round(r.get("similarity", 0), 2),
            verified_count=r.get("verified_count", 0),
            source="local",
        )
        for r in results
    ]

    return VulnerabilitySearchResponse(
        found=True,
        message=f"Found {len(results)} matching vulnerability pattern(s)",
        results=search_results,
        total=len(search_results),
    )


@vulns_router.post("/verify", response_model=VulnerabilityVerifyResponse)
async def verify_vulnerability(
    request: VulnerabilityVerifyRequest,
    api_key: str = Depends(require_api_key),
) -> VulnerabilityVerifyResponse:
    """
    Verify a vulnerability report.

    **Requires API key authentication.**

    Use this to confirm a vulnerability is valid or mark it as a false positive.
    If fix_confirmed=True, the vulnerability will be marked as patched.

    Rate limit: 20/minute
    """
    storage = get_storage()

    # Determine disclosure status based on fix_confirmed
    disclosure_status = "patched" if request.fix_confirmed else None

    result = await storage.verify_vulnerability(
        record_id=request.id,
        is_valid=request.is_valid,
        disclosure_status=disclosure_status,
    )

    # Get updated counts from index
    verified_count = 0
    false_positive_count = 0
    for entry in storage._index.get("vulnerabilities", []):
        if entry["id"] == request.id:
            verified_count = entry.get("verified_count", 0)
            false_positive_count = entry.get("false_positive_count", 0)
            break

    fix_msg = " Fix confirmed - marked as patched." if request.fix_confirmed else ""

    return VulnerabilityVerifyResponse(
        success=result.get("success", False),
        id=request.id,
        verified_count=verified_count,
        false_positive_count=false_positive_count,
        message=f"Vulnerability {request.id} marked as {'valid' if request.is_valid else 'false positive'}.{fix_msg}",
    )


@vulns_router.get("/stats", response_model=VulnerabilityStatsResponse)
async def get_vulnerability_stats(
    api_key: str = Depends(optional_api_key),
) -> VulnerabilityStatsResponse:
    """
    Get vulnerability statistics for the dashboard.

    Returns counts by severity, disclosure status, and top vulnerability types.

    Rate limit: 60/minute
    """
    storage = get_storage()
    stats = await storage.get_stats()

    vulns = storage._index.get("vulnerabilities", [])

    # Count by type
    type_counts = {}
    for v in vulns:
        vtype = v.get("vuln_type", "Other")
        type_counts[vtype] = type_counts.get(vtype, 0) + 1

    # Count by agent
    agent_counts = {}
    for v in vulns:
        agent = v.get("reported_by_agent", "unknown")
        agent_counts[agent] = agent_counts.get(agent, 0) + 1

    # Get patched/open counts from status
    status_counts = stats.get("vuln_by_status", {})
    total_patched = status_counts.get("patched", 0) + status_counts.get("mitigated", 0)
    total_open = status_counts.get("open", 0)

    # Top types this week (sorted by count)
    from datetime import datetime, timedelta
    week_ago = datetime.now() - timedelta(days=7)
    week_type_counts = {}
    recent_activity = []

    for v in vulns:
        try:
            ts = datetime.fromisoformat(v.get("timestamp", ""))
            if ts >= week_ago:
                vtype = v.get("vuln_type", "Other")
                week_type_counts[vtype] = week_type_counts.get(vtype, 0) + 1
                recent_activity.append({
                    "id": v.get("id"),
                    "type": vtype,
                    "severity": v.get("severity"),
                    "timestamp": v.get("timestamp"),
                })
        except (ValueError, TypeError):
            pass

    top_types_this_week = [
        {"type": t, "count": c}
        for t, c in sorted(week_type_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    ]

    # Sort recent activity by timestamp descending
    recent_activity = sorted(recent_activity, key=lambda x: x.get("timestamp", ""), reverse=True)[:10]

    return VulnerabilityStatsResponse(
        total_found=stats.get("vulnerabilities", 0),
        total_patched=total_patched,
        total_open=total_open,
        by_severity=stats.get("vuln_by_severity", {}),
        by_type=type_counts,
        by_agent=agent_counts,
        top_types_this_week=top_types_this_week,
        recent_activity=recent_activity,
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
