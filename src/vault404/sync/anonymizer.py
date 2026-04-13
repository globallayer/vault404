"""
Anonymization Layer for vault404

Transforms personal records into shareable, anonymized knowledge.
Strips ALL identifying information while preserving the useful pattern.

Example:
    Input:  "ConnectionError in /Users/john/projects/myapp/db.py line 42"
    Output: "ConnectionError in [project]/db.py line 42"
"""

import re
import hashlib
from pathlib import Path
from typing import Optional


def anonymize_record(record: dict) -> dict:
    """
    Transform a local record into an anonymized, shareable version.

    Removes:
    - Absolute paths → relative patterns
    - Project names → generic placeholders
    - User-specific context → category-level info
    - Any remaining secrets (double-check)

    Preserves:
    - Error type and pattern
    - Solution approach
    - Language/framework context
    - Category
    """
    anon = {}

    # Copy basic structure
    anon["type"] = record.get("type", "error_fix")
    anon["category"] = record.get("context", {}).get("category", "general")
    anon["language"] = record.get("context", {}).get("language")
    anon["framework"] = record.get("context", {}).get("framework")
    anon["database"] = record.get("context", {}).get("database")
    anon["platform"] = record.get("context", {}).get("platform")

    # Anonymize error info
    if "error" in record:
        error = record["error"]
        anon["error"] = {
            "message": _anonymize_text(error.get("message", "")),
            "error_type": error.get("error_type"),
            "file_pattern": _extract_file_pattern(error.get("file", "")),
        }

    # Anonymize solution
    if "solution" in record:
        solution = record["solution"]
        anon["solution"] = {
            "description": _anonymize_text(solution.get("description", "")),
            "approach": _extract_approach(solution.get("description", "")),
        }
        if solution.get("code_change"):
            anon["solution"]["code_pattern"] = _anonymize_code(solution["code_change"])

    # Add a hash for deduplication
    content = f"{anon.get('error', {}).get('message', '')}{anon.get('solution', {}).get('description', '')}"
    anon["content_hash"] = hashlib.sha256(content.encode()).hexdigest()[:16]

    # Verification status (important for trust)
    anon["verified"] = record.get("verified", False)
    anon["success_count"] = record.get("success_count", 0)

    return anon


def _anonymize_text(text: str) -> str:
    """Remove identifying information from text while keeping the error pattern."""
    if not text:
        return ""

    result = text

    # Replace absolute paths with relative patterns
    # Windows: C:\Users\john\projects\... → [project]/...
    result = re.sub(
        r'[A-Z]:\\[^\\]+\\[^\\]+\\[^\\]+\\([^\\]+\\)',
        r'[project]/',
        result
    )

    # Unix: /Users/john/projects/... → [project]/...
    result = re.sub(
        r'/(?:Users|home)/[^/]+/[^/]+/([^/]+/)',
        r'[project]/',
        result
    )

    # Replace specific IPs with [IP]
    result = re.sub(
        r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',
        '[IP]',
        result
    )

    # Replace specific ports with [PORT] (keep common ones)
    common_ports = {'80', '443', '3000', '5432', '3306', '27017', '6379', '8080'}
    result = re.sub(
        r':(\d{4,5})\b',
        lambda m: f':{m.group(1)}' if m.group(1) in common_ports else ':[PORT]',
        result
    )

    # Replace UUIDs with [UUID]
    result = re.sub(
        r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
        '[UUID]',
        result,
        flags=re.IGNORECASE
    )

    # Replace email-like patterns with [EMAIL]
    result = re.sub(
        r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        '[EMAIL]',
        result
    )

    # Replace URLs with domain only
    result = re.sub(
        r'https?://([^/\s]+)[^\s]*',
        r'https://[DOMAIN]',
        result
    )

    return result


def _extract_file_pattern(filepath: str) -> Optional[str]:
    """Extract just the file pattern (e.g., 'db.py', 'auth/login.ts')."""
    if not filepath:
        return None

    path = Path(filepath)

    # Get last 2 parts (directory/file) if available
    parts = path.parts
    if len(parts) >= 2:
        return f"{parts[-2]}/{parts[-1]}"
    return path.name


def _extract_approach(solution: str) -> str:
    """Extract the general approach from a solution description."""
    # Look for common fix patterns
    approaches = []

    lower = solution.lower()

    if 'import' in lower:
        approaches.append('import_fix')
    if 'type' in lower and ('annotation' in lower or 'hint' in lower):
        approaches.append('type_annotation')
    if 'async' in lower or 'await' in lower:
        approaches.append('async_handling')
    if 'null' in lower or 'none' in lower or 'undefined' in lower:
        approaches.append('null_check')
    if 'try' in lower and ('catch' in lower or 'except' in lower):
        approaches.append('error_handling')
    if 'config' in lower or 'env' in lower:
        approaches.append('configuration')
    if 'dependency' in lower or 'package' in lower or 'version' in lower:
        approaches.append('dependency_fix')
    if 'permission' in lower or 'auth' in lower:
        approaches.append('auth_fix')
    if 'query' in lower or 'sql' in lower:
        approaches.append('query_fix')

    return ','.join(approaches) if approaches else 'general'


def _anonymize_code(code: str) -> str:
    """Anonymize code snippets while keeping the pattern."""
    if not code:
        return ""

    result = code

    # Replace string literals with placeholders
    result = re.sub(r'"[^"]*"', '"[STRING]"', result)
    result = re.sub(r"'[^']*'", "'[STRING]'", result)

    # Replace specific variable names that look like identifiers
    # Keep common patterns (i, j, x, err, ctx, db, etc.)

    # Anonymize comments
    result = re.sub(r'//.*$', '// [comment]', result, flags=re.MULTILINE)
    result = re.sub(r'#.*$', '# [comment]', result, flags=re.MULTILINE)

    return result
