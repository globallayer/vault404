"""Recording tools for vault404 - log errors, decisions, and patterns with secret redaction"""

from typing import Optional
from ..storage import get_storage, ErrorFix, Decision, Pattern, Context, ErrorInfo, SolutionInfo
from ..security import redact_secrets


async def log_error_fix(
    error_message: str,
    solution: str,
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
) -> dict:
    """
    Log an error and its solution to vault404.

    SECURITY: All inputs are automatically scanned for secrets
    (API keys, passwords, tokens) and redacted before storage.

    Args:
        error_message: The error message that was encountered
        solution: Description of how the error was fixed
        error_type: Type of error (e.g., ConnectionError, TypeError)
        stack_trace: Full stack trace if available
        file: File where error occurred
        line: Line number where error occurred
        code_change: The actual code change made to fix it
        files_modified: List of files that were changed
        project: Project name
        language: Programming language (typescript, python, etc.)
        framework: Framework being used (express, nextjs, fastapi, etc.)
        database: Database being used (postgresql, mongodb, etc.)
        platform: Deployment platform (railway, vercel, aws, etc.)
        category: Category of issue (database, auth, api, deployment, etc.)
        time_to_solve: How long it took to fix (e.g., "5m", "2h")
        verified: Whether the solution has been verified to work

    Returns:
        dict with success status and record ID
    """
    storage = get_storage()

    # SECURITY: Redact secrets before storage
    safe_error_message = redact_secrets(error_message)
    safe_solution = redact_secrets(solution)
    safe_stack_trace = redact_secrets(stack_trace) if stack_trace else None
    safe_code_change = redact_secrets(code_change) if code_change else None

    record = ErrorFix(
        error=ErrorInfo(
            message=safe_error_message,
            error_type=error_type,
            stack_trace=safe_stack_trace,
            file=file,
            line=line,
        ),
        solution=SolutionInfo(
            description=safe_solution,
            code_change=safe_code_change,
            files_modified=files_modified or [],
        ),
        context=Context(
            project=project,
            language=language,
            framework=framework,
            database=database,
            platform=platform,
            category=category,
        ),
        time_to_solve=time_to_solve,
        verified=verified,
    )

    result = await storage.store_error_fix(record)

    return {
        "success": result.get("success", False),
        "record_id": record.id,
        "message": f"Logged error fix: {safe_error_message[:50]}... -> {safe_solution[:50]}...",
        "secrets_redacted": safe_error_message != error_message or safe_solution != solution,
    }


async def log_decision(
    title: str,
    choice: str,
    alternatives: Optional[list[str]] = None,
    pros: Optional[list[str]] = None,
    cons: Optional[list[str]] = None,
    deciding_factor: Optional[str] = None,
    project: Optional[str] = None,
    component: Optional[str] = None,
    language: Optional[str] = None,
    framework: Optional[str] = None,
) -> dict:
    """
    Log an architectural decision to vault404.

    Args:
        title: Short title for the decision
        choice: What was chosen
        alternatives: Other options that were considered
        pros: Advantages of the chosen option
        cons: Disadvantages of the chosen option
        deciding_factor: The main reason for this choice
        project: Project name
        component: Component this decision affects
        language: Programming language context
        framework: Framework context

    Returns:
        dict with success status and record ID
    """
    storage = get_storage()

    record = Decision(
        title=title,
        choice=choice,
        alternatives=alternatives or [],
        pros=pros or [],
        cons=cons or [],
        deciding_factor=deciding_factor,
        context=Context(
            project=project,
            language=language,
            framework=framework,
            category=component,
        ),
    )

    result = await storage.store_decision(record)

    return {
        "success": result.get("success", False),
        "record_id": record.id,
        "message": f"Logged decision: {title} -> {choice}",
    }


async def log_pattern(
    name: str,
    category: str,
    problem: str,
    solution: str,
    languages: Optional[list[str]] = None,
    frameworks: Optional[list[str]] = None,
    databases: Optional[list[str]] = None,
    scenarios: Optional[list[str]] = None,
    before_code: Optional[str] = None,
    after_code: Optional[str] = None,
    explanation: Optional[str] = None,
) -> dict:
    """
    Log a reusable pattern to vault404.

    SECURITY: Code snippets are scanned for secrets and redacted.

    Args:
        name: Name for this pattern
        category: Category (database, auth, api, deployment, testing, etc.)
        problem: The problem this pattern solves
        solution: How the pattern solves it
        languages: Languages this applies to
        frameworks: Frameworks this applies to
        databases: Databases this applies to
        scenarios: Scenarios where this is useful
        before_code: Code before applying the pattern
        after_code: Code after applying the pattern
        explanation: Detailed explanation

    Returns:
        dict with success status and record ID
    """
    storage = get_storage()

    # SECURITY: Redact secrets from code snippets
    safe_before = redact_secrets(before_code) if before_code else None
    safe_after = redact_secrets(after_code) if after_code else None

    record = Pattern(
        name=name,
        category=category,
        problem=problem,
        solution=solution,
        languages=languages or [],
        frameworks=frameworks or [],
        databases=databases or [],
        scenarios=scenarios or [],
        before_code=safe_before,
        after_code=safe_after,
        explanation=explanation,
    )

    result = await storage.store_pattern(record)

    return {
        "success": result.get("success", False),
        "record_id": record.id,
        "message": f"Logged pattern: {name}",
    }
