"""
Pydantic models for the Vault404 REST API.

Request and response models for all API endpoints with input validation.
"""

import re
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator


# =============================================================================
# Validation Constants
# =============================================================================

MAX_ERROR_MESSAGE_LENGTH = 5000
MAX_SOLUTION_LENGTH = 10000
MAX_STACK_TRACE_LENGTH = 20000
MAX_CODE_LENGTH = 50000
MAX_SHORT_TEXT_LENGTH = 500
MAX_LIST_ITEMS = 20
MIN_TEXT_LENGTH = 3

# Pattern for safe identifiers (project names, categories, etc.)
SAFE_IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\.\/\s]+$")


# =============================================================================
# Validation Helpers
# =============================================================================


def validate_safe_text(value: Optional[str], max_length: int, field_name: str) -> Optional[str]:
    """Validate text input for length and strip whitespace."""
    if value is None:
        return None
    value = value.strip()
    if len(value) > max_length:
        raise ValueError(f"{field_name} must be at most {max_length} characters")
    return value


def validate_identifier(value: Optional[str], field_name: str) -> Optional[str]:
    """Validate identifier-like text (project names, categories)."""
    if value is None:
        return None
    value = value.strip()
    if len(value) > MAX_SHORT_TEXT_LENGTH:
        raise ValueError(f"{field_name} must be at most {MAX_SHORT_TEXT_LENGTH} characters")
    if value and not SAFE_IDENTIFIER_PATTERN.match(value):
        raise ValueError(f"{field_name} contains invalid characters")
    return value


# =============================================================================
# Solution Models
# =============================================================================


class SolutionSearchRequest(BaseModel):
    """Request body for searching solutions."""

    error_message: str = Field(
        ...,
        min_length=MIN_TEXT_LENGTH,
        max_length=MAX_ERROR_MESSAGE_LENGTH,
        description="The error message to search for",
    )
    language: Optional[str] = Field(None, max_length=50, description="Programming language filter")
    framework: Optional[str] = Field(None, max_length=50, description="Framework filter")
    database: Optional[str] = Field(None, max_length=50, description="Database filter")
    platform: Optional[str] = Field(None, max_length=50, description="Platform filter")
    category: Optional[str] = Field(None, max_length=50, description="Category filter")
    limit: int = Field(5, ge=1, le=50, description="Maximum number of results")

    @field_validator("language", "framework", "database", "platform", "category")
    @classmethod
    def validate_filters(cls, v):
        return validate_identifier(v, "filter")


class SolutionResult(BaseModel):
    """A single solution result."""

    id: str
    solution: str
    original_error: str
    context: Dict[str, Any] = Field(default_factory=dict)
    confidence: float
    verified: bool
    source: str = "local"


class SolutionSearchResponse(BaseModel):
    """Response for solution search."""

    found: bool
    message: str
    solutions: List[SolutionResult] = Field(default_factory=list)
    source: str = "local"
    suggestion: Optional[str] = None


class SolutionLogRequest(BaseModel):
    """Request body for logging a solution."""

    error_message: str = Field(
        ...,
        min_length=MIN_TEXT_LENGTH,
        max_length=MAX_ERROR_MESSAGE_LENGTH,
        description="The error message that was encountered",
    )
    solution: str = Field(
        ...,
        min_length=MIN_TEXT_LENGTH,
        max_length=MAX_SOLUTION_LENGTH,
        description="Description of how the error was fixed",
    )
    error_type: Optional[str] = Field(None, max_length=100, description="Type of error")
    stack_trace: Optional[str] = Field(
        None, max_length=MAX_STACK_TRACE_LENGTH, description="Full stack trace"
    )
    file: Optional[str] = Field(None, max_length=500, description="File where error occurred")
    line: Optional[int] = Field(None, ge=1, le=1000000, description="Line number")
    code_change: Optional[str] = Field(
        None, max_length=MAX_CODE_LENGTH, description="Code change made"
    )
    files_modified: Optional[List[str]] = Field(
        None, max_length=MAX_LIST_ITEMS, description="Files modified"
    )
    project: Optional[str] = Field(None, max_length=100, description="Project name")
    language: Optional[str] = Field(None, max_length=50, description="Programming language")
    framework: Optional[str] = Field(None, max_length=50, description="Framework")
    database: Optional[str] = Field(None, max_length=50, description="Database")
    platform: Optional[str] = Field(None, max_length=50, description="Platform")
    category: Optional[str] = Field(None, max_length=50, description="Category")
    time_to_solve: Optional[str] = Field(None, max_length=20, description="Time to solve")
    verified: bool = Field(False, description="Whether solution is verified")

    @field_validator("error_message", "solution")
    @classmethod
    def strip_and_validate(cls, v, info):
        if v:
            v = v.strip()
            if len(v) < MIN_TEXT_LENGTH:
                raise ValueError(f"{info.field_name} must be at least {MIN_TEXT_LENGTH} characters")
        return v

    @field_validator("files_modified")
    @classmethod
    def validate_files_list(cls, v):
        if v is not None and len(v) > MAX_LIST_ITEMS:
            raise ValueError(f"files_modified cannot have more than {MAX_LIST_ITEMS} items")
        return v


class SolutionLogResponse(BaseModel):
    """Response for logging a solution."""

    id: str
    success: bool
    message: str
    secrets_redacted: bool = False


class SolutionVerifyRequest(BaseModel):
    """Request body for verifying a solution."""

    id: str = Field(..., min_length=1, max_length=100, description="Solution record ID")
    success: bool = Field(..., description="Whether the solution worked")

    @field_validator("id")
    @classmethod
    def validate_id(cls, v):
        # Record IDs should match pattern like ef_20260413_195401
        if not re.match(r"^[a-zA-Z0-9_\-]+$", v):
            raise ValueError("Invalid record ID format")
        return v


class SolutionVerifyResponse(BaseModel):
    """Response for verifying a solution."""

    success: bool
    record_id: str
    verified: bool
    contributed_to_community: bool = False
    message: str


# =============================================================================
# Decision Models
# =============================================================================


class DecisionSearchRequest(BaseModel):
    """Request body for searching decisions."""

    topic: str = Field(
        ...,
        min_length=MIN_TEXT_LENGTH,
        max_length=MAX_SHORT_TEXT_LENGTH,
        description="Topic to search for",
    )
    project: Optional[str] = Field(None, max_length=100, description="Project filter")
    component: Optional[str] = Field(None, max_length=100, description="Component filter")
    limit: int = Field(5, ge=1, le=50, description="Maximum number of results")


class DecisionResult(BaseModel):
    """A single decision result."""

    id: str
    title: str
    choice: str
    relevance: float


class DecisionSearchResponse(BaseModel):
    """Response for decision search."""

    found: bool
    message: str
    decisions: List[DecisionResult] = Field(default_factory=list)
    suggestion: Optional[str] = None


class DecisionLogRequest(BaseModel):
    """Request body for logging a decision."""

    title: str = Field(
        ..., min_length=MIN_TEXT_LENGTH, max_length=200, description="Short title for the decision"
    )
    choice: str = Field(
        ...,
        min_length=MIN_TEXT_LENGTH,
        max_length=MAX_SHORT_TEXT_LENGTH,
        description="What was chosen",
    )
    alternatives: Optional[List[str]] = Field(None, description="Other options considered")
    pros: Optional[List[str]] = Field(None, description="Advantages")
    cons: Optional[List[str]] = Field(None, description="Disadvantages")
    deciding_factor: Optional[str] = Field(
        None, max_length=MAX_SHORT_TEXT_LENGTH, description="Main reason for choice"
    )
    project: Optional[str] = Field(None, max_length=100, description="Project name")
    component: Optional[str] = Field(None, max_length=100, description="Component affected")
    language: Optional[str] = Field(None, max_length=50, description="Programming language")
    framework: Optional[str] = Field(None, max_length=50, description="Framework")

    @field_validator("alternatives", "pros", "cons")
    @classmethod
    def validate_lists(cls, v):
        if v is not None:
            if len(v) > MAX_LIST_ITEMS:
                raise ValueError(f"Cannot have more than {MAX_LIST_ITEMS} items")
            # Validate each item
            for item in v:
                if len(item) > MAX_SHORT_TEXT_LENGTH:
                    raise ValueError(
                        f"Each item must be at most {MAX_SHORT_TEXT_LENGTH} characters"
                    )
        return v


class DecisionLogResponse(BaseModel):
    """Response for logging a decision."""

    id: str
    success: bool
    message: str


# =============================================================================
# Pattern Models
# =============================================================================


class PatternSearchRequest(BaseModel):
    """Request body for searching patterns."""

    problem: str = Field(
        ...,
        min_length=MIN_TEXT_LENGTH,
        max_length=MAX_SHORT_TEXT_LENGTH,
        description="Problem to search for",
    )
    category: Optional[str] = Field(None, max_length=50, description="Category filter")
    language: Optional[str] = Field(None, max_length=50, description="Language filter")
    framework: Optional[str] = Field(None, max_length=50, description="Framework filter")
    limit: int = Field(5, ge=1, le=50, description="Maximum number of results")


class PatternResult(BaseModel):
    """A single pattern result."""

    id: str
    name: str
    category: str
    problem: str
    solution: str
    relevance: float


class PatternSearchResponse(BaseModel):
    """Response for pattern search."""

    found: bool
    message: str
    patterns: List[PatternResult] = Field(default_factory=list)
    suggestion: Optional[str] = None


class PatternLogRequest(BaseModel):
    """Request body for logging a pattern."""

    name: str = Field(
        ..., min_length=MIN_TEXT_LENGTH, max_length=200, description="Name for this pattern"
    )
    category: str = Field(..., min_length=1, max_length=50, description="Category")
    problem: str = Field(
        ...,
        min_length=MIN_TEXT_LENGTH,
        max_length=MAX_SOLUTION_LENGTH,
        description="Problem this pattern solves",
    )
    solution: str = Field(
        ...,
        min_length=MIN_TEXT_LENGTH,
        max_length=MAX_SOLUTION_LENGTH,
        description="How the pattern solves it",
    )
    languages: Optional[List[str]] = Field(None, description="Applicable languages")
    frameworks: Optional[List[str]] = Field(None, description="Applicable frameworks")
    databases: Optional[List[str]] = Field(None, description="Applicable databases")
    scenarios: Optional[List[str]] = Field(None, description="Usage scenarios")
    before_code: Optional[str] = Field(
        None, max_length=MAX_CODE_LENGTH, description="Code before pattern"
    )
    after_code: Optional[str] = Field(
        None, max_length=MAX_CODE_LENGTH, description="Code after pattern"
    )
    explanation: Optional[str] = Field(
        None, max_length=MAX_SOLUTION_LENGTH, description="Detailed explanation"
    )

    @field_validator("languages", "frameworks", "databases", "scenarios")
    @classmethod
    def validate_lists(cls, v):
        if v is not None:
            if len(v) > MAX_LIST_ITEMS:
                raise ValueError(f"Cannot have more than {MAX_LIST_ITEMS} items")
        return v


class PatternLogResponse(BaseModel):
    """Response for logging a pattern."""

    id: str
    success: bool
    message: str


# =============================================================================
# Stats & Health Models
# =============================================================================


class StatsResponse(BaseModel):
    """Response for stats endpoint."""

    total_records: int
    error_fixes: int
    decisions: int
    patterns: int
    data_directory: str


class HealthResponse(BaseModel):
    """Response for health check."""

    status: str
    version: str
    storage_available: bool = True


# =============================================================================
# Error Models
# =============================================================================


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str
    error_code: Optional[str] = None


class RateLimitResponse(BaseModel):
    """Rate limit exceeded response."""

    detail: str = "Rate limit exceeded"
    retry_after: Optional[int] = None


# =============================================================================
# Vulnerability Models
# =============================================================================

# Valid vulnerability types
VULN_TYPES = [
    "SQLi",           # SQL Injection
    "XSS",            # Cross-Site Scripting
    "SSRF",           # Server-Side Request Forgery
    "RCE",            # Remote Code Execution
    "IDOR",           # Insecure Direct Object Reference
    "PathTraversal",  # Path/Directory Traversal
    "AuthBypass",     # Authentication Bypass
    "BrokenAuth",     # Broken Authentication
    "CSRF",           # Cross-Site Request Forgery
    "XXE",            # XML External Entity
    "Deserialization", # Insecure Deserialization
    "SSTI",           # Server-Side Template Injection
    "OpenRedirect",   # Open Redirect
    "InfoLeak",       # Information Disclosure
    "MissingAuth",    # Missing Authorization
    "Hardcoded",      # Hardcoded Secrets/Credentials
    "WeakCrypto",     # Weak Cryptography
    "RaceCondition",  # Race Condition
    "DoS",            # Denial of Service
    "Other",          # Other vulnerability type
]

SEVERITY_LEVELS = ["Critical", "High", "Medium", "Low"]
DISCLOSURE_STATUSES = ["open", "patched", "mitigated", "wontfix"]
AGENT_TYPES = ["Claude", "GPT", "Cursor", "Aider", "Copilot", "Continue", "Other"]


class VulnerabilityReportRequest(BaseModel):
    """Request body for reporting a vulnerability."""

    vuln_type: str = Field(
        ...,
        description="Type of vulnerability (SQLi, XSS, SSRF, RCE, etc.)",
    )
    severity: str = Field(
        ...,
        description="Severity level (Critical, High, Medium, Low)",
    )
    pattern_snippet: str = Field(
        ...,
        min_length=MIN_TEXT_LENGTH,
        max_length=MAX_CODE_LENGTH,
        description="Anonymized vulnerable code pattern (NO real code/paths)",
    )
    description: str = Field(
        ...,
        min_length=MIN_TEXT_LENGTH,
        max_length=MAX_SOLUTION_LENGTH,
        description="Description of the vulnerability",
    )

    # Optional fields
    cwe_id: Optional[str] = Field(None, max_length=20, description="CWE ID (e.g., CWE-79)")
    language: Optional[str] = Field(None, max_length=50, description="Programming language")
    framework: Optional[str] = Field(None, max_length=50, description="Framework")
    database: Optional[str] = Field(None, max_length=50, description="Database")
    platform: Optional[str] = Field(None, max_length=50, description="Platform")
    fix_snippet: Optional[str] = Field(
        None, max_length=MAX_CODE_LENGTH, description="Anonymized fix pattern"
    )
    impact: Optional[str] = Field(
        None, max_length=MAX_SHORT_TEXT_LENGTH, description="Potential impact"
    )
    remediation: Optional[str] = Field(
        None, max_length=MAX_SOLUTION_LENGTH, description="How to fix"
    )
    reported_by_agent: str = Field(
        "Claude", max_length=50, description="AI agent that found it"
    )

    @field_validator("vuln_type")
    @classmethod
    def validate_vuln_type(cls, v):
        if v not in VULN_TYPES:
            raise ValueError(f"vuln_type must be one of: {', '.join(VULN_TYPES)}")
        return v

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v):
        if v not in SEVERITY_LEVELS:
            raise ValueError(f"severity must be one of: {', '.join(SEVERITY_LEVELS)}")
        return v

    @field_validator("cwe_id")
    @classmethod
    def validate_cwe_id(cls, v):
        if v is not None:
            if not re.match(r"^CWE-\d+$", v):
                raise ValueError("cwe_id must be in format CWE-XXX (e.g., CWE-79)")
        return v


class VulnerabilityReportResponse(BaseModel):
    """Response for reporting a vulnerability."""

    id: str
    success: bool
    message: str
    disclosure_delay_hours: int = 72
    is_public: bool = False


class VulnerabilityFeedItem(BaseModel):
    """A single vulnerability in the feed."""

    id: str
    vuln_type: str
    severity: str
    language: Optional[str] = None
    framework: Optional[str] = None
    description: str
    pattern_snippet: str
    fix_snippet: Optional[str] = None
    disclosure_status: str
    reported_by_agent: str
    verified_count: int
    timestamp: str
    time_ago: str  # "2h ago", "1d ago", etc.


class VulnerabilityFeedResponse(BaseModel):
    """Response for vulnerability feed."""

    total: int
    items: List[VulnerabilityFeedItem] = Field(default_factory=list)
    has_more: bool = False


class VulnerabilitySearchRequest(BaseModel):
    """Request body for searching vulnerabilities."""

    query: str = Field(
        ...,
        min_length=MIN_TEXT_LENGTH,
        max_length=MAX_ERROR_MESSAGE_LENGTH,
        description="Search query (vulnerability pattern or description)",
    )
    vuln_type: Optional[str] = Field(None, description="Filter by vulnerability type")
    severity: Optional[str] = Field(None, description="Filter by severity")
    language: Optional[str] = Field(None, max_length=50, description="Filter by language")
    framework: Optional[str] = Field(None, max_length=50, description="Filter by framework")
    disclosure_status: Optional[str] = Field(None, description="Filter by status")
    limit: int = Field(10, ge=1, le=100, description="Maximum results")

    @field_validator("vuln_type")
    @classmethod
    def validate_vuln_type(cls, v):
        if v is not None and v not in VULN_TYPES:
            raise ValueError(f"vuln_type must be one of: {', '.join(VULN_TYPES)}")
        return v

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v):
        if v is not None and v not in SEVERITY_LEVELS:
            raise ValueError(f"severity must be one of: {', '.join(SEVERITY_LEVELS)}")
        return v

    @field_validator("disclosure_status")
    @classmethod
    def validate_status(cls, v):
        if v is not None and v not in DISCLOSURE_STATUSES:
            raise ValueError(f"disclosure_status must be one of: {', '.join(DISCLOSURE_STATUSES)}")
        return v


class VulnerabilitySearchResult(BaseModel):
    """A single vulnerability search result."""

    id: str
    vuln_type: str
    severity: str
    description: str
    pattern_snippet: str
    fix_snippet: Optional[str] = None
    language: Optional[str] = None
    framework: Optional[str] = None
    verified_count: int
    relevance: float
    source: str = "local"


class VulnerabilitySearchResponse(BaseModel):
    """Response for vulnerability search."""

    found: bool
    message: str
    results: List[VulnerabilitySearchResult] = Field(default_factory=list)
    total: int = 0


class VulnerabilityVerifyRequest(BaseModel):
    """Request body for verifying a vulnerability."""

    id: str = Field(..., min_length=1, max_length=100, description="Vulnerability ID")
    is_valid: bool = Field(..., description="True if vuln is real, False if false positive")
    fix_confirmed: bool = Field(False, description="True if the fix works")
    notes: Optional[str] = Field(None, max_length=MAX_SHORT_TEXT_LENGTH, description="Notes")

    @field_validator("id")
    @classmethod
    def validate_id(cls, v):
        if not re.match(r"^vuln_[a-zA-Z0-9_\-]+$", v):
            raise ValueError("Invalid vulnerability ID format")
        return v


class VulnerabilityVerifyResponse(BaseModel):
    """Response for verifying a vulnerability."""

    success: bool
    id: str
    verified_count: int
    false_positive_count: int
    message: str


class VulnerabilityStatsResponse(BaseModel):
    """Response for vulnerability statistics."""

    total_found: int
    total_patched: int
    total_open: int
    by_severity: Dict[str, int] = Field(default_factory=dict)
    by_type: Dict[str, int] = Field(default_factory=dict)
    by_agent: Dict[str, int] = Field(default_factory=dict)
    top_types_this_week: List[Dict[str, Any]] = Field(default_factory=list)
    recent_activity: List[Dict[str, Any]] = Field(default_factory=list)
