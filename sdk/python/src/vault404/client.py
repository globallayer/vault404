"""
Vault404 Python SDK - Client

Main client class for interacting with the Vault404 API.
Provides methods for logging and querying error fixes, decisions, and patterns.

Example:
    >>> from vault404 import Vault404
    >>>
    >>> client = Vault404()
    >>>
    >>> # Find solutions for an error
    >>> result = client.find_solution(
    ...     error_message="Cannot find module react",
    ...     language="typescript"
    ... )
    >>>
    >>> # Log an error fix
    >>> client.log_error_fix(
    ...     error_message="Module not found",
    ...     solution="Run npm install"
    ... )
"""

import json
from typing import Any, Optional
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from .errors import (
    Vault404Error,
    NetworkError,
    ApiError,
    TimeoutError,
    ValidationError,
    AuthenticationError,
    RateLimitError,
    NotFoundError,
)
from .types import (
    Context,
    Solution,
    Decision,
    Pattern,
    LogResult,
    FindSolutionResult,
    FindDecisionResult,
    FindPatternResult,
    VerifySolutionResult,
    StatsResult,
    Vault404Stats,
)


DEFAULT_API_URL = "https://web-production-7e0e3.up.railway.app"
DEFAULT_TIMEOUT = 30.0
API_VERSION = "v1"
SDK_VERSION = "0.1.0"


class Vault404:
    """
    Vault404Client - Main client for interacting with the Vault404 API.

    The Vault404 client provides methods to:
    - Find solutions to errors from the collective knowledge base
    - Log error fixes to help other AI agents
    - Record architectural decisions for future reference
    - Store and retrieve reusable patterns
    - Verify solutions and contribute to the community brain

    Example:
        >>> from vault404 import Vault404
        >>>
        >>> client = Vault404(api_url="http://localhost:8000")
        >>>
        >>> # Find solutions for an error
        >>> result = client.find_solution(
        ...     error_message="Cannot find module react",
        ...     language="typescript",
        ...     framework="nextjs"
        ... )
        >>>
        >>> if result.found:
        ...     for solution in result.solutions:
        ...         print(f"[{solution.confidence}] {solution.solution}")
    """

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
        headers: Optional[dict[str, str]] = None,
        debug: bool = False,
    ):
        """
        Create a new Vault404 client instance.

        Args:
            api_url: Base URL of the Vault404 API server.
                     Defaults to "https://api.vault404.dev".
            api_key: API key for authenticated requests (optional).
            timeout: Request timeout in seconds. Defaults to 30.
            headers: Custom headers to include in all requests.
            debug: Enable debug logging. Defaults to False.

        Example:
            >>> # With default settings (production API)
            >>> client = Vault404()
            >>>
            >>> # With custom API URL (local development)
            >>> client = Vault404(api_url="http://localhost:8000")
            >>>
            >>> # With API key and custom timeout
            >>> client = Vault404(api_key="your-api-key", timeout=60)
        """
        self._api_url = self._normalize_url(api_url or DEFAULT_API_URL)
        self._api_key = api_key
        self._timeout = timeout
        self._debug = debug

        self._headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": f"vault404-python-sdk/{SDK_VERSION}",
            **(headers or {}),
        }

        if self._api_key:
            self._headers["Authorization"] = f"Bearer {self._api_key}"

    def _normalize_url(self, url: str) -> str:
        """Remove trailing slash from URL."""
        return url.rstrip("/")

    def _log(self, message: str, data: Any = None) -> None:
        """Log debug messages if debug mode is enabled."""
        if self._debug:
            print(f"[Vault404] {message}", data if data else "")

    def _request(
        self,
        method: str,
        endpoint: str,
        body: Optional[dict[str, Any]] = None,
    ) -> Any:
        """Make an HTTP request to the Vault404 API."""
        url = f"{self._api_url}/api/{API_VERSION}{endpoint}"

        self._log(f"{method} {url}", body)

        data = None
        if body:
            # Remove None values from body
            body = {k: v for k, v in body.items() if v is not None}
            data = json.dumps(body).encode("utf-8")

        request = Request(url, data=data, method=method)
        for key, value in self._headers.items():
            request.add_header(key, value)

        try:
            with urlopen(request, timeout=self._timeout) as response:
                response_body = json.loads(response.read().decode("utf-8"))
                self._log(f"Response {response.status}", response_body)
                return response_body

        except HTTPError as e:
            try:
                error_body = json.loads(e.read().decode("utf-8"))
            except (json.JSONDecodeError, AttributeError):
                error_body = {}

            message = error_body.get("message", f"HTTP {e.code} error")
            self._handle_error_response(e.code, message, error_body, url, method)

        except URLError as e:
            if "timed out" in str(e.reason).lower():
                raise TimeoutError(
                    f"Request timed out after {self._timeout}s",
                    int(self._timeout * 1000),
                    {"url": url},
                )
            raise NetworkError(f"Network request failed: {e.reason}", url, e)

        except Exception as e:
            raise Vault404Error(f"An unexpected error occurred: {e}", {"error": str(e)})

    def _handle_error_response(
        self,
        status: int,
        message: str,
        body: dict[str, Any],
        url: str,
        method: str,
    ) -> None:
        """Handle error responses from the API."""
        if status == 400:
            raise ValidationError(message)
        elif status == 401:
            raise AuthenticationError(message)
        elif status == 404:
            raise NotFoundError(message)
        elif status == 429:
            retry_after = body.get("retry_after")
            raise RateLimitError(message, retry_after)
        else:
            raise ApiError(message, status, {"body": body, "url": url, "method": method})

    def _validate_required(self, value: Any, field_name: str) -> None:
        """Validate that a required field is present and not empty."""
        if value is None:
            raise ValidationError(f"{field_name} is required", field=field_name, rule="required")
        if isinstance(value, str) and value.strip() == "":
            raise ValidationError(f"{field_name} cannot be empty", field=field_name, rule="not_empty")

    # =========================================================================
    # Error Fix Methods
    # =========================================================================

    def find_solution(
        self,
        error_message: str,
        *,
        project: Optional[str] = None,
        language: Optional[str] = None,
        framework: Optional[str] = None,
        database: Optional[str] = None,
        platform: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 5,
    ) -> FindSolutionResult:
        """
        Find solutions for an error from the Vault404 knowledge base.

        This should be the first thing you check when encountering an error.
        Solutions are ranked by relevance based on error similarity and context match.

        Args:
            error_message: The error message to find solutions for (required).
            project: Project name for context matching.
            language: Programming language (e.g., 'typescript', 'python').
            framework: Framework (e.g., 'nextjs', 'fastapi').
            database: Database (e.g., 'postgresql', 'mongodb').
            platform: Platform (e.g., 'railway', 'vercel').
            category: Issue category (e.g., 'database', 'auth').
            limit: Maximum number of solutions to return. Defaults to 5.

        Returns:
            FindSolutionResult with matching solutions.

        Example:
            >>> result = client.find_solution(
            ...     error_message="Connection refused",
            ...     language="typescript",
            ...     framework="nextjs",
            ...     database="postgresql"
            ... )
            >>>
            >>> if result.found:
            ...     for solution in result.solutions:
            ...         print(f"[{solution.confidence}] {solution.solution}")
        """
        self._validate_required(error_message, "error_message")

        response = self._request(
            "POST",
            "/solutions/search",
            {
                "error_message": error_message,
                "project": project,
                "language": language,
                "framework": framework,
                "database": database,
                "platform": platform,
                "category": category,
                "limit": limit,
            },
        )

        solutions = [
            Solution(
                id=s.get("id", ""),
                solution=s.get("solution", ""),
                original_error=s.get("original_error", ""),
                context=Context(
                    project=s.get("context", {}).get("project"),
                    language=s.get("context", {}).get("language"),
                    framework=s.get("context", {}).get("framework"),
                    database=s.get("context", {}).get("database"),
                    platform=s.get("context", {}).get("platform"),
                    category=s.get("context", {}).get("category"),
                ),
                confidence=s.get("confidence", 0.0),
                verified=s.get("verified", False),
                source=s.get("source", "local"),
            )
            for s in response.get("solutions", [])
        ]

        return FindSolutionResult(
            found=response.get("found", False),
            message=response.get("message", ""),
            solutions=solutions,
            suggestion=response.get("suggestion"),
        )

    def log_error_fix(
        self,
        error_message: str,
        solution: str,
        *,
        error_type: Optional[str] = None,
        stack_trace: Optional[str] = None,
        file: Optional[str] = None,
        line: Optional[int] = None,
        code_change: Optional[str] = None,
        files_modified: Optional[list[str]] = None,
        project: Optional[str] = None,
        language: Optional[str] = None,
        framework: Optional[str] = None,
        database: Optional[str] = None,
        platform: Optional[str] = None,
        category: Optional[str] = None,
        time_to_solve: Optional[str] = None,
        verified: bool = False,
    ) -> LogResult:
        """
        Log an error and its solution to the Vault404 knowledge base.

        Use this after fixing any error to help other AI agents. All inputs are
        automatically scanned for secrets (API keys, passwords, tokens) and
        redacted before storage.

        Args:
            error_message: The error message that was encountered (required).
            solution: Description of how the error was fixed (required).
            error_type: Type of error (e.g., "ConnectionError", "TypeError").
            stack_trace: Full stack trace if available.
            file: File where the error occurred.
            line: Line number where the error occurred.
            code_change: The actual code change made to fix the error.
            files_modified: List of files that were modified.
            project: Project name.
            language: Programming language.
            framework: Framework being used.
            database: Database being used.
            platform: Deployment platform.
            category: Issue category.
            time_to_solve: How long it took to fix (e.g., "5m", "2h").
            verified: Whether the solution has been verified to work.

        Returns:
            LogResult with the record ID.

        Example:
            >>> result = client.log_error_fix(
            ...     error_message="ECONNREFUSED 127.0.0.1:5432",
            ...     solution="Start PostgreSQL: sudo systemctl start postgresql",
            ...     language="typescript",
            ...     framework="nextjs",
            ...     database="postgresql",
            ...     category="database",
            ...     verified=True
            ... )
            >>> print(f"Logged with ID: {result.record_id}")
        """
        self._validate_required(error_message, "error_message")
        self._validate_required(solution, "solution")

        response = self._request(
            "POST",
            "/solutions/log",
            {
                "error_message": error_message,
                "solution": solution,
                "error_type": error_type,
                "stack_trace": stack_trace,
                "file": file,
                "line": line,
                "code_change": code_change,
                "files_modified": files_modified,
                "project": project,
                "language": language,
                "framework": framework,
                "database": database,
                "platform": platform,
                "category": category,
                "time_to_solve": time_to_solve,
                "verified": verified,
            },
        )

        return LogResult(
            success=response.get("success", False),
            message=response.get("message", ""),
            record_id=response.get("id"),
            secrets_redacted=response.get("secrets_redacted"),
        )

    def verify_solution(self, id: str, success: bool) -> VerifySolutionResult:
        """
        Verify whether a solution worked or not.

        Call this after trying a suggested solution. If success=True, the
        anonymized solution is automatically contributed to the community
        brain, helping all AI agents get smarter.

        Args:
            id: The record ID of the solution to verify (required).
            success: Whether the solution worked (required).

        Returns:
            VerifySolutionResult with contribution status.

        Example:
            >>> result = client.verify_solution(
            ...     id="ef_20240115_143052",
            ...     success=True
            ... )
            >>> if result.contributed:
            ...     print("Solution contributed to community brain!")
        """
        self._validate_required(id, "id")

        response = self._request(
            "POST",
            "/solutions/verify",
            {"id": id, "success": success},
        )

        return VerifySolutionResult(
            success=response.get("success", False),
            message=response.get("message", ""),
            record_id=response.get("record_id", id),
            verified_as="successful" if success else "unsuccessful",
            contributed=response.get("contributed_to_community", False),
            contribution_note=response.get("message"),
        )

    # =========================================================================
    # Decision Methods
    # =========================================================================

    def log_decision(
        self,
        title: str,
        choice: str,
        *,
        alternatives: Optional[list[str]] = None,
        pros: Optional[list[str]] = None,
        cons: Optional[list[str]] = None,
        deciding_factor: Optional[str] = None,
        project: Optional[str] = None,
        component: Optional[str] = None,
        language: Optional[str] = None,
        framework: Optional[str] = None,
    ) -> LogResult:
        """
        Log an architectural decision to the Vault404 knowledge base.

        Use this when making significant technical choices. Recording decisions
        helps remember why choices were made and their outcomes.

        Args:
            title: Short title for the decision (required).
            choice: What was chosen (required).
            alternatives: Other options that were considered.
            pros: Advantages of the chosen option.
            cons: Disadvantages of the chosen option.
            deciding_factor: The main reason for this choice.
            project: Project name.
            component: Component this decision affects.
            language: Programming language context.
            framework: Framework context.

        Returns:
            LogResult with the record ID.

        Example:
            >>> result = client.log_decision(
            ...     title="State management library",
            ...     choice="Zustand",
            ...     alternatives=["Redux", "Context API", "Jotai"],
            ...     pros=["Simple API", "Small bundle size"],
            ...     cons=["Smaller ecosystem"],
            ...     deciding_factor="Project needs simplicity"
            ... )
        """
        self._validate_required(title, "title")
        self._validate_required(choice, "choice")

        response = self._request(
            "POST",
            "/decisions/log",
            {
                "title": title,
                "choice": choice,
                "alternatives": alternatives,
                "pros": pros,
                "cons": cons,
                "deciding_factor": deciding_factor,
                "project": project,
                "component": component,
                "language": language,
                "framework": framework,
            },
        )

        return LogResult(
            success=response.get("success", False),
            message=response.get("message", ""),
            record_id=response.get("id"),
        )

    def find_decision(
        self,
        topic: str,
        *,
        project: Optional[str] = None,
        component: Optional[str] = None,
        limit: int = 3,
    ) -> FindDecisionResult:
        """
        Find past decisions on a topic from the Vault404 knowledge base.

        Check this before making architectural choices to learn from history.

        Args:
            topic: Topic to search for (required).
            project: Filter by project.
            component: Filter by component.
            limit: Maximum number of decisions to return. Defaults to 3.

        Returns:
            FindDecisionResult with matching decisions.

        Example:
            >>> result = client.find_decision(
            ...     topic="database choice",
            ...     project="my-app"
            ... )
            >>> if result.found:
            ...     for decision in result.decisions:
            ...         print(f"{decision.title}: chose {decision.choice}")
        """
        self._validate_required(topic, "topic")

        response = self._request(
            "POST",
            "/decisions/search",
            {
                "topic": topic,
                "project": project,
                "component": component,
                "limit": limit,
            },
        )

        decisions = [
            Decision(
                id=d.get("id", ""),
                title=d.get("title", ""),
                choice=d.get("choice", ""),
                alternatives=d.get("alternatives", []),
                relevance=d.get("relevance", 0.0),
            )
            for d in response.get("decisions", [])
        ]

        return FindDecisionResult(
            found=response.get("found", False),
            message=response.get("message", ""),
            decisions=decisions,
            suggestion=response.get("suggestion"),
        )

    # =========================================================================
    # Pattern Methods
    # =========================================================================

    def log_pattern(
        self,
        name: str,
        category: str,
        problem: str,
        solution: str,
        *,
        languages: Optional[list[str]] = None,
        frameworks: Optional[list[str]] = None,
        databases: Optional[list[str]] = None,
        scenarios: Optional[list[str]] = None,
        before_code: Optional[str] = None,
        after_code: Optional[str] = None,
        explanation: Optional[str] = None,
    ) -> LogResult:
        """
        Log a reusable pattern to the Vault404 knowledge base.

        Use this to capture patterns that solve recurring problems. Code snippets
        are automatically scanned for secrets and redacted.

        Args:
            name: Name for this pattern (required).
            category: Category (e.g., "database", "auth", "api") (required).
            problem: The problem this pattern solves (required).
            solution: How the pattern solves the problem (required).
            languages: Languages this pattern applies to.
            frameworks: Frameworks this pattern applies to.
            databases: Databases this pattern applies to.
            scenarios: Scenarios where this pattern is useful.
            before_code: Code before applying the pattern.
            after_code: Code after applying the pattern.
            explanation: Detailed explanation of the pattern.

        Returns:
            LogResult with the record ID.

        Example:
            >>> result = client.log_pattern(
            ...     name="Optimistic UI updates",
            ...     category="frontend",
            ...     problem="Slow UI feedback when waiting for API",
            ...     solution="Update UI immediately, sync with server response",
            ...     languages=["typescript"],
            ...     frameworks=["react", "nextjs"]
            ... )
        """
        self._validate_required(name, "name")
        self._validate_required(category, "category")
        self._validate_required(problem, "problem")
        self._validate_required(solution, "solution")

        response = self._request(
            "POST",
            "/patterns/log",
            {
                "name": name,
                "category": category,
                "problem": problem,
                "solution": solution,
                "languages": languages,
                "frameworks": frameworks,
                "databases": databases,
                "scenarios": scenarios,
                "before_code": before_code,
                "after_code": after_code,
                "explanation": explanation,
            },
        )

        return LogResult(
            success=response.get("success", False),
            message=response.get("message", ""),
            record_id=response.get("id"),
        )

    def find_pattern(
        self,
        problem: str,
        *,
        category: Optional[str] = None,
        language: Optional[str] = None,
        framework: Optional[str] = None,
        limit: int = 3,
    ) -> FindPatternResult:
        """
        Find reusable patterns for a problem from the Vault404 knowledge base.

        Search for established patterns before implementing solutions.

        Args:
            problem: The problem to find patterns for (required).
            category: Category filter.
            language: Language filter.
            framework: Framework filter.
            limit: Maximum number of patterns to return. Defaults to 3.

        Returns:
            FindPatternResult with matching patterns.

        Example:
            >>> result = client.find_pattern(
            ...     problem="database connection pooling",
            ...     category="database",
            ...     language="typescript"
            ... )
            >>> if result.found:
            ...     for pattern in result.patterns:
            ...         print(f"{pattern.name}: {pattern.solution}")
        """
        self._validate_required(problem, "problem")

        response = self._request(
            "POST",
            "/patterns/search",
            {
                "problem": problem,
                "category": category,
                "language": language,
                "framework": framework,
                "limit": limit,
            },
        )

        patterns = [
            Pattern(
                id=p.get("id", ""),
                name=p.get("name", ""),
                category=p.get("category", ""),
                problem=p.get("problem", ""),
                solution=p.get("solution", ""),
                relevance=p.get("relevance", 0.0),
            )
            for p in response.get("patterns", [])
        ]

        return FindPatternResult(
            found=response.get("found", False),
            message=response.get("message", ""),
            patterns=patterns,
            suggestion=response.get("suggestion"),
        )

    # =========================================================================
    # Stats Methods
    # =========================================================================

    def get_stats(self) -> StatsResult:
        """
        Get statistics about the Vault404 knowledge base.

        Returns:
            StatsResult with knowledge base statistics.

        Example:
            >>> result = client.get_stats()
            >>> print(f"Total records: {result.stats.total_records}")
            >>> print(f"Error fixes: {result.stats.error_fixes}")
        """
        response = self._request("GET", "/stats")

        return StatsResult(
            success=True,
            message="Stats retrieved successfully",
            stats=Vault404Stats(
                total_records=response.get("total_records", 0),
                error_fixes=response.get("error_fixes", 0),
                decisions=response.get("decisions", 0),
                patterns=response.get("patterns", 0),
                data_directory=response.get("data_directory"),
            ),
        )

    def health_check(self) -> bool:
        """
        Check if the API server is reachable.

        Returns:
            True if the server is reachable, False otherwise.

        Example:
            >>> if not client.health_check():
            ...     print("Vault404 API is not reachable")
        """
        try:
            self._request("GET", "/health")
            return True
        except Exception:
            return False

    @property
    def api_url(self) -> str:
        """Get the configured API URL."""
        return self._api_url


# Alias for convenience
Vault404Client = Vault404
