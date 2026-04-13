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
            r'\1=[REDACTED:api_key]'
        ),

        # Passwords
        "password": (
            r'(?i)(password|passwd|pwd|secret)["\s:=]+["\']?([^\s"\']{4,})["\']?',
            r'\1=[REDACTED:password]'
        ),

        # Generic tokens
        "token": (
            r'(?i)(token|auth[_-]?token|access[_-]?token|bearer)["\s:=]+["\']?([\w-]{20,})["\']?',
            r'\1=[REDACTED:token]'
        ),

        # OpenAI
        "openai_key": (
            r'sk-[a-zA-Z0-9]{48,}',
            '[REDACTED:openai_key]'
        ),

        # Anthropic
        "anthropic_key": (
            r'sk-ant-[a-zA-Z0-9-]{80,}',
            '[REDACTED:anthropic_key]'
        ),

        # Stripe
        "stripe_key": (
            r'(sk|pk|rk)_(live|test)_[a-zA-Z0-9]{24,}',
            '[REDACTED:stripe_key]'
        ),

        # GitHub
        "github_token": (
            r'(ghp|gho|ghu|ghs|ghr)_[a-zA-Z0-9]{36,}',
            '[REDACTED:github_token]'
        ),

        # AWS
        "aws_key": (
            r'AKIA[0-9A-Z]{16}',
            '[REDACTED:aws_access_key]'
        ),
        "aws_secret": (
            r'(?i)(aws[_-]?secret[_-]?access[_-]?key)["\s:=]+["\']?([a-zA-Z0-9/+=]{40})["\']?',
            r'\1=[REDACTED:aws_secret]'
        ),

        # Database URLs (redact credentials portion)
        "postgres_url": (
            r'postgresql://([^:]+):([^@]+)@',
            r'postgresql://[REDACTED]:[REDACTED]@'
        ),
        "mysql_url": (
            r'mysql://([^:]+):([^@]+)@',
            r'mysql://[REDACTED]:[REDACTED]@'
        ),
        "mongodb_url": (
            r'mongodb(\+srv)?://([^:]+):([^@]+)@',
            r'mongodb\1://[REDACTED]:[REDACTED]@'
        ),

        # Supabase
        "supabase_key": (
            r'eyJ[a-zA-Z0-9_-]{100,}\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+',
            '[REDACTED:jwt_token]'
        ),

        # Private keys
        "private_key": (
            r'-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----[\s\S]*?-----END (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----',
            '[REDACTED:private_key]'
        ),

        # Generic secrets in env format
        "env_secret": (
            r'(?i)^([A-Z_]*(?:SECRET|KEY|TOKEN|PASSWORD|CREDENTIAL|AUTH)[A-Z_]*)\s*=\s*["\']?([^\s"\']{8,})["\']?',
            r'\1=[REDACTED:env_secret]'
        ),

        # Bearer tokens in headers
        "bearer_token": (
            r'(?i)bearer\s+([a-zA-Z0-9._-]{20,})',
            'Bearer [REDACTED:bearer_token]'
        ),

        # Basic auth in URLs
        "basic_auth": (
            r'https?://([^:]+):([^@]+)@',
            r'https://[REDACTED]:[REDACTED]@'
        ),
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
            name: re.compile(pattern, re.MULTILINE)
            for name, (pattern, _) in self.patterns.items()
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
