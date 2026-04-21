"""
Secret Redaction Module for vault404

Automatically detects and redacts sensitive information before storage.
This ensures API keys, passwords, tokens, and other secrets are NEVER stored.
"""

import re
from typing import Optional
from dataclasses import dataclass


@dataclass
class RedactionResult:
    """Result of redaction operation"""

    original_length: int
    redacted_length: int
    redactions_made: int
    redacted_text: str
    redaction_types: list[str]


class SecretRedactor:
    """
    Detects and redacts secrets from text before storage.

    Patterns are intentionally aggressive - better to over-redact than leak secrets.
    """

    # Pattern name -> (regex pattern, replacement template)
    PATTERNS = {
        # API Keys - Generic
        "api_key": (
            r'(?i)(api[_-]?key|apikey)["\s:=]+["\']?([\w-]{20,})["\']?',
            r"\1=[REDACTED:api_key]",
        ),
        # Passwords
        "password": (
            r'(?i)(password|passwd|pwd|secret)["\s:=]+["\']?([^\s"\']{4,})["\']?',
            r"\1=[REDACTED:password]",
        ),
        # Generic tokens
        "token": (
            r'(?i)(token|auth[_-]?token|access[_-]?token|bearer)["\s:=]+["\']?([\w-]{20,})["\']?',
            r"\1=[REDACTED:token]",
        ),
        # OpenAI
        "openai_key": (r"sk-[a-zA-Z0-9]{48,}", "[REDACTED:openai_key]"),
        # Anthropic
        "anthropic_key": (r"sk-ant-[a-zA-Z0-9-]{80,}", "[REDACTED:anthropic_key]"),
        # Stripe
        "stripe_key": (r"(sk|pk|rk)_(live|test)_[a-zA-Z0-9]{24,}", "[REDACTED:stripe_key]"),
        # GitHub
        "github_token": (r"(ghp|gho|ghu|ghs|ghr)_[a-zA-Z0-9]{36,}", "[REDACTED:github_token]"),
        # AWS
        "aws_key": (r"AKIA[0-9A-Z]{16}", "[REDACTED:aws_access_key]"),
        "aws_secret": (
            r'(?i)(aws[_-]?secret[_-]?access[_-]?key)["\s:=]+["\']?([a-zA-Z0-9/+=]{40})["\']?',
            r"\1=[REDACTED:aws_secret]",
        ),
        # Database URLs (redact credentials portion)
        "postgres_url": (r"postgresql://([^:]+):([^@]+)@", r"postgresql://[REDACTED]:[REDACTED]@"),
        "mysql_url": (r"mysql://([^:]+):([^@]+)@", r"mysql://[REDACTED]:[REDACTED]@"),
        "mongodb_url": (
            r"mongodb(\+srv)?://([^:]+):([^@]+)@",
            r"mongodb\1://[REDACTED]:[REDACTED]@",
        ),
        # Supabase
        "supabase_key": (
            r"eyJ[a-zA-Z0-9_-]{100,}\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+",
            "[REDACTED:jwt_token]",
        ),
        # Private keys
        "private_key": (
            r"-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----[\s\S]*?-----END (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----",
            "[REDACTED:private_key]",
        ),
        # Generic secrets in env format
        "env_secret": (
            r'(?i)^([A-Z_]*(?:SECRET|KEY|TOKEN|PASSWORD|CREDENTIAL|AUTH)[A-Z_]*)\s*=\s*["\']?([^\s"\']{8,})["\']?',
            r"\1=[REDACTED:env_secret]",
        ),
        # Bearer tokens in headers
        "bearer_token": (r"(?i)bearer\s+([a-zA-Z0-9._-]{20,})", "Bearer [REDACTED:bearer_token]"),
        # Basic auth in URLs
        "basic_auth": (r"https?://([^:]+):([^@]+)@", r"https://[REDACTED]:[REDACTED]@"),
    }

    def __init__(self, extra_patterns: Optional[dict] = None):
        """
        Initialize redactor with optional extra patterns.

        Args:
            extra_patterns: Additional patterns to redact
        """
        self.patterns = dict(self.PATTERNS)
        if extra_patterns:
            self.patterns.update(extra_patterns)

        # Compile patterns for efficiency
        self._compiled = {
            name: re.compile(pattern, re.MULTILINE) for name, (pattern, _) in self.patterns.items()
        }

    def redact(self, text: str) -> RedactionResult:
        """
        Redact all secrets from text.

        Args:
            text: Text that may contain secrets

        Returns:
            RedactionResult with redacted text and metadata
        """
        original_length = len(text)
        redacted = text
        redaction_types = []
        redactions_made = 0

        for name, compiled_pattern in self._compiled.items():
            _, replacement = self.patterns[name]

            # Count matches
            matches = compiled_pattern.findall(redacted)
            if matches:
                redactions_made += len(matches) if isinstance(matches[0], str) else len(matches)
                redaction_types.append(name)

            # Apply redaction
            redacted = compiled_pattern.sub(replacement, redacted)

        return RedactionResult(
            original_length=original_length,
            redacted_length=len(redacted),
            redactions_made=redactions_made,
            redacted_text=redacted,
            redaction_types=redaction_types,
        )

    def contains_secrets(self, text: str) -> bool:
        """Quick check if text contains any secrets."""
        for compiled_pattern in self._compiled.values():
            if compiled_pattern.search(text):
                return True
        return False


# Global instance for convenience
_default_redactor = SecretRedactor()


def redact_secrets(text: str) -> str:
    """
    Convenience function to redact secrets from text.

    Args:
        text: Text that may contain secrets

    Returns:
        Text with secrets redacted
    """
    result = _default_redactor.redact(text)
    return result.redacted_text


# =============================================================================
# Vulnerability Pattern Anonymizer
# =============================================================================

class VulnerabilityAnonymizer:
    """
    Anonymizes code patterns for vulnerability reporting.

    Removes identifying information while preserving the vulnerability shape:
    - File paths and directory structures
    - Repository names and URLs
    - IP addresses and domain names
    - Email addresses
    - Specific variable/function/class names (optional)

    The goal is to share the vulnerability PATTERN without revealing
    the specific codebase where it was found.
    """

    # Patterns to anonymize
    PATTERNS = {
        # File paths (Unix and Windows)
        "unix_path": (
            r'(/(?:home|users|var|opt|etc|usr|tmp|app|src|lib|pkg|node_modules)/[^\s"\'<>|:*?]+)',
            "[PATH]",
        ),
        "windows_path": (
            r'([A-Za-z]:\\(?:[^\\/:*?"<>|\r\n]+\\)*[^\\/:*?"<>|\r\n]*)',
            "[PATH]",
        ),
        "relative_path": (
            r'(?:^|[\s"\'])(\.\./(?:[^\s"\']+/)*[^\s"\']+|\.\/(?:[^\s"\']+/)*[^\s"\']+)',
            "[PATH]",
        ),
        # Repository URLs
        "github_url": (
            r'https?://github\.com/[a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+(?:/[^\s"\'<>]*)?',
            "[REPO_URL]",
        ),
        "gitlab_url": (
            r'https?://gitlab\.com/[a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+(?:/[^\s"\'<>]*)?',
            "[REPO_URL]",
        ),
        "bitbucket_url": (
            r'https?://bitbucket\.org/[a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+(?:/[^\s"\'<>]*)?',
            "[REPO_URL]",
        ),
        # IP addresses (v4)
        "ipv4": (
            r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b',
            "[IP_ADDR]",
        ),
        # IP addresses (v6)
        "ipv6": (
            r'\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b',
            "[IP_ADDR]",
        ),
        # Domain names (but not common ones)
        "domain": (
            r'\b(?!(?:localhost|example\.com|google\.com|github\.com|npm\.(js\.)?org))[a-zA-Z0-9][-a-zA-Z0-9]*\.[a-zA-Z]{2,}(?:\.[a-zA-Z]{2,})?\b',
            "[DOMAIN]",
        ),
        # Email addresses
        "email": (
            r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b',
            "[EMAIL]",
        ),
        # Git commit hashes
        "commit_hash": (
            r'\b[a-f0-9]{40}\b',
            "[COMMIT]",
        ),
        "short_commit": (
            r'\b[a-f0-9]{7,8}\b(?=\s|$|[^\w])',
            "[COMMIT]",
        ),
        # UUID
        "uuid": (
            r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b',
            "[UUID]",
        ),
        # Package version specifiers (npm, pip)
        "package_version": (
            r'@[0-9]+\.[0-9]+\.[0-9]+(?:-[a-zA-Z0-9.]+)?',
            "@[VERSION]",
        ),
    }

    # Variable name patterns (more aggressive anonymization)
    VARIABLE_PATTERNS = {
        # Specific-looking variable names in common patterns
        "sql_table": (
            r'(?i)(?:FROM|INTO|UPDATE|JOIN)\s+[`"\']?([a-zA-Z_][a-zA-Z0-9_]*)[`"\']?',
            r"TABLE_NAME",
        ),
        "sql_column": (
            r'(?i)(?:SELECT|WHERE|SET|AND|OR)\s+[`"\']?([a-zA-Z_][a-zA-Z0-9_]*)[`"\']?\s*[=<>]',
            r"COLUMN",
        ),
    }

    def __init__(self, anonymize_variables: bool = False):
        """
        Initialize anonymizer.

        Args:
            anonymize_variables: If True, also anonymize variable/table names
        """
        self.patterns = dict(self.PATTERNS)
        if anonymize_variables:
            self.patterns.update(self.VARIABLE_PATTERNS)

        # Compile patterns
        self._compiled = {
            name: re.compile(pattern, re.MULTILINE | re.IGNORECASE)
            for name, (pattern, _) in self.patterns.items()
        }

    def anonymize(self, text: str) -> str:
        """
        Anonymize a code pattern for vulnerability reporting.

        Args:
            text: Code pattern that may contain identifying info

        Returns:
            Anonymized pattern
        """
        result = text

        for name, compiled_pattern in self._compiled.items():
            _, replacement = self.patterns[name]
            result = compiled_pattern.sub(replacement, result)

        return result

    def anonymize_with_stats(self, text: str) -> RedactionResult:
        """
        Anonymize with detailed statistics.

        Args:
            text: Code pattern to anonymize

        Returns:
            RedactionResult with anonymized text and metadata
        """
        original_length = len(text)
        anonymized = text
        redaction_types = []
        redactions_made = 0

        for name, compiled_pattern in self._compiled.items():
            _, replacement = self.patterns[name]

            # Count matches
            matches = compiled_pattern.findall(anonymized)
            if matches:
                count = len(matches) if isinstance(matches[0], str) else len(matches)
                redactions_made += count
                redaction_types.append(f"{name}:{count}")

            # Apply anonymization
            anonymized = compiled_pattern.sub(replacement, anonymized)

        return RedactionResult(
            original_length=original_length,
            redacted_length=len(anonymized),
            redactions_made=redactions_made,
            redacted_text=anonymized,
            redaction_types=redaction_types,
        )


# Global anonymizer instance
_vulnerability_anonymizer = VulnerabilityAnonymizer()
_aggressive_anonymizer = VulnerabilityAnonymizer(anonymize_variables=True)


def anonymize_vuln_pattern(text: str, aggressive: bool = False) -> str:
    """
    Anonymize a vulnerability code pattern for sharing.

    Removes file paths, repo URLs, IP addresses, domains, emails,
    and optionally variable names.

    Args:
        text: Code pattern that may contain identifying info
        aggressive: If True, also anonymize variable/table names

    Returns:
        Anonymized pattern safe to share publicly
    """
    # First redact secrets
    text = redact_secrets(text)

    # Then anonymize identifying info
    anonymizer = _aggressive_anonymizer if aggressive else _vulnerability_anonymizer
    return anonymizer.anonymize(text)


def full_vulnerability_redaction(text: str) -> str:
    """
    Full redaction for vulnerability patterns: secrets + anonymization.

    This is the recommended function for all vulnerability reporting.
    It combines secret redaction with pattern anonymization.

    Args:
        text: Vulnerability pattern or code snippet

    Returns:
        Fully redacted and anonymized text
    """
    return anonymize_vuln_pattern(text, aggressive=False)
