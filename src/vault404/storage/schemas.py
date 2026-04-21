"""Data schemas for Agent Brain records"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class Context(BaseModel):
    """Context information for matching solutions"""

    project: Optional[str] = None
    language: Optional[str] = None  # typescript, python, go, rust, etc.
    framework: Optional[str] = None  # express, fastapi, nextjs, etc.
    database: Optional[str] = None  # postgresql, mongodb, supabase, etc.
    platform: Optional[str] = None  # railway, vercel, aws, local, etc.
    category: Optional[str] = None  # database, auth, api, deployment, etc.
    versions: dict[str, str] = Field(default_factory=dict)  # {"node": "20.x", "typescript": "5.x"}

    def to_aaak(self) -> str:
        """Convert to AAAK compressed format"""
        parts = []
        if self.project:
            parts.append(f"PROJ:{self.project}")
        if self.language:
            parts.append(f"LANG:{self.language}")
        if self.framework:
            parts.append(f"FW:{self.framework}")
        if self.database:
            parts.append(f"DB:{self.database}")
        if self.platform:
            parts.append(f"PLAT:{self.platform}")
        if self.category:
            parts.append(f"CAT:{self.category}")
        return "|".join(parts)

    def match_score(self, other: "Context") -> float:
        """Calculate how well this context matches another (0.0 to 1.0)"""
        weights = {
            "language": 0.25,
            "framework": 0.20,
            "database": 0.20,
            "platform": 0.15,
            "category": 0.10,
            "project": 0.10,
        }

        score = 0.0
        for field, weight in weights.items():
            self_val = getattr(self, field, None)
            other_val = getattr(other, field, None)
            if self_val and other_val and self_val.lower() == other_val.lower():
                score += weight

        return score


class ErrorInfo(BaseModel):
    """Information about an error encountered"""

    message: str
    error_type: Optional[str] = None
    stack_trace: Optional[str] = None
    file: Optional[str] = None
    line: Optional[int] = None


class SolutionInfo(BaseModel):
    """Information about a solution applied"""

    description: str
    code_change: Optional[str] = None
    files_modified: list[str] = Field(default_factory=list)
    verification: Optional[str] = None


class ErrorFix(BaseModel):
    """A record of an error and its fix"""

    id: str = Field(default_factory=lambda: f"ef_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    type: str = "error_fix"
    timestamp: datetime = Field(default_factory=datetime.now)

    error: ErrorInfo
    context: Context = Field(default_factory=Context)
    solution: SolutionInfo

    # Metadata
    time_to_solve: Optional[str] = None
    confidence: float = 1.0
    verified: bool = False
    success_count: int = 0
    failure_count: int = 0

    # Usage tracking (for enhanced ranking)
    usage_count: int = 0
    last_accessed: Optional[datetime] = None

    # Semantic search embedding (optional - computed on store)
    embedding: Optional[list[float]] = None

    def to_aaak(self) -> str:
        """Convert to AAAK compressed format for storage"""
        ctx = self.context.to_aaak()
        return (
            f"ERROR_FIX|{self.timestamp.strftime('%Y-%m-%d')}|"
            f"ERR:{self.error.message[:100]}|"
            f"SOL:{self.solution.description[:100]}|"
            f"{ctx}|"
            f"CONF:{self.confidence}|"
            f"{'VERIFIED' if self.verified else 'UNVERIFIED'}"
        )

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.5  # Unknown
        return self.success_count / total


class Decision(BaseModel):
    """A record of an architectural decision"""

    id: str = Field(default_factory=lambda: f"dec_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    type: str = "decision"
    timestamp: datetime = Field(default_factory=datetime.now)

    title: str
    choice: str
    alternatives: list[str] = Field(default_factory=list)
    context: Context = Field(default_factory=Context)

    # Rationale
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    deciding_factor: Optional[str] = None

    # Outcome tracking
    status: str = "pending"  # pending, successful, failed, revised
    lessons: Optional[str] = None
    would_repeat: Optional[bool] = None

    # Semantic search embedding (optional)
    embedding: Optional[list[float]] = None

    def to_aaak(self) -> str:
        """Convert to AAAK compressed format"""
        ctx = self.context.to_aaak()
        return (
            f"DECISION|{self.timestamp.strftime('%Y-%m-%d')}|"
            f"TITLE:{self.title}|"
            f"CHOSE:{self.choice}|"
            f"OVER:{','.join(self.alternatives)}|"
            f"{ctx}|"
            f"STATUS:{self.status}"
        )


class Pattern(BaseModel):
    """A reusable pattern extracted from experience"""

    id: str = Field(default_factory=lambda: f"pat_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    type: str = "pattern"
    timestamp: datetime = Field(default_factory=datetime.now)

    name: str
    category: str  # database, auth, api, deployment, testing, etc.
    problem: str
    solution: str

    # Applicability
    languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    databases: list[str] = Field(default_factory=list)
    scenarios: list[str] = Field(default_factory=list)

    # Implementation
    before_code: Optional[str] = None
    after_code: Optional[str] = None
    explanation: Optional[str] = None

    # References to source records
    source_records: list[str] = Field(default_factory=list)

    # Semantic search embedding (optional)
    embedding: Optional[list[float]] = None

    def to_aaak(self) -> str:
        """Convert to AAAK compressed format"""
        return (
            f"PATTERN|{self.name}|"
            f"CAT:{self.category}|"
            f"PROB:{self.problem[:80]}|"
            f"SOL:{self.solution[:80]}|"
            f"LANGS:{','.join(self.languages)}|"
            f"FW:{','.join(self.frameworks)}"
        )


class VulnerabilityReport(BaseModel):
    """A record of an AI-discovered security vulnerability"""

    id: str = Field(default_factory=lambda: f"vuln_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    type: str = "vulnerability"
    timestamp: datetime = Field(default_factory=datetime.now)

    # Vulnerability classification
    vuln_type: str  # SQLi, XSS, SSRF, RCE, IDOR, PathTraversal, AuthBypass, etc.
    severity: str  # Critical, High, Medium, Low
    cwe_id: Optional[str] = None  # CWE-79, CWE-89, etc.

    # Context
    language: Optional[str] = None  # python, typescript, go, rust, etc.
    framework: Optional[str] = None  # express, fastapi, django, nextjs, etc.
    database: Optional[str] = None  # postgresql, mongodb, etc.
    platform: Optional[str] = None  # railway, vercel, aws, etc.

    # Vulnerability details (REDACTED - no real code/paths)
    pattern_snippet: str  # Anonymized vulnerable code pattern
    fix_snippet: Optional[str] = None  # Anonymized fix pattern
    description: str  # What the vulnerability is
    impact: Optional[str] = None  # Potential impact if exploited
    remediation: Optional[str] = None  # How to fix it

    # Disclosure & status
    disclosure_status: str = "open"  # open, patched, mitigated, wontfix
    disclosure_delay_hours: int = 72  # Responsible disclosure delay
    is_public: bool = False  # Only true after disclosure delay or patched

    # Attribution & verification
    reported_by_agent: str = "unknown"  # Claude, GPT, Cursor, Aider, etc.
    verified_count: int = 0
    false_positive_count: int = 0

    # Usage tracking
    view_count: int = 0
    last_accessed: Optional[datetime] = None

    # Semantic search embedding (optional)
    embedding: Optional[list[float]] = None

    def to_aaak(self) -> str:
        """Convert to AAAK compressed format"""
        return (
            f"VULN|{self.timestamp.strftime('%Y-%m-%d')}|"
            f"TYPE:{self.vuln_type}|"
            f"SEV:{self.severity}|"
            f"LANG:{self.language or 'any'}|"
            f"FW:{self.framework or 'any'}|"
            f"STATUS:{self.disclosure_status}|"
            f"AGENT:{self.reported_by_agent}|"
            f"VERIFIED:{self.verified_count}"
        )

    @property
    def is_ready_for_disclosure(self) -> bool:
        """Check if vulnerability can be publicly disclosed"""
        if self.disclosure_status in ("patched", "mitigated", "wontfix"):
            return True
        if self.is_public:
            return True
        # Check if disclosure delay has passed
        from datetime import timedelta
        deadline = self.timestamp + timedelta(hours=self.disclosure_delay_hours)
        return datetime.now() >= deadline

    @property
    def confidence_score(self) -> float:
        """Calculate confidence based on verifications vs false positives"""
        total = self.verified_count + self.false_positive_count
        if total == 0:
            return 0.5  # Unknown
        return self.verified_count / total
