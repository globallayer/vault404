"""Storage backends for vault404"""

import os
from typing import Optional
from .schemas import ErrorFix, Decision, Pattern, Context, ErrorInfo, SolutionInfo
from .local_storage import LocalStorage

# Centralized singleton - ALL modules must use this
_storage: Optional[LocalStorage] = None


def get_storage() -> LocalStorage:
    """
    Get the shared storage instance.

    This is the ONLY way to access storage across all vault404 modules.
    Ensures consistent state between recording, querying, and maintenance.

    Encryption is enabled via:
    - VAULT404_ENCRYPTED=true environment variable
    - VAULT404_PASSWORD environment variable (optional, auto-generates if not set)
    - Or by calling configure_storage() before first use
    """
    global _storage
    if _storage is None:
        encrypted = os.environ.get("VAULT404_ENCRYPTED", "").lower() in ("true", "1", "yes")
        password = os.environ.get("VAULT404_PASSWORD")
        _storage = LocalStorage(encrypted=encrypted, password=password)
    return _storage


def configure_storage(encrypted: bool = False, password: Optional[str] = None) -> LocalStorage:
    """
    Configure and return the storage instance.

    Must be called BEFORE any other storage operations if you want encryption.

    Args:
        encrypted: Enable AES-256 encryption for data at rest
        password: Optional password for key derivation (auto-generated if not provided)

    Returns:
        The configured LocalStorage instance
    """
    global _storage
    _storage = LocalStorage(encrypted=encrypted, password=password)
    return _storage


def reset_storage() -> None:
    """Reset the storage instance (for testing or after purge)."""
    global _storage
    _storage = None


__all__ = [
    "ErrorFix",
    "Decision",
    "Pattern",
    "Context",
    "ErrorInfo",
    "SolutionInfo",
    "LocalStorage",
    "get_storage",
    "configure_storage",
    "reset_storage",
]
