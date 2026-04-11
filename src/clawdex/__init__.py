"""
Claw-dex: Collective AI Coding Agent Brain

Every verified fix makes ALL AI agents smarter.
Automatic sharing, fully anonymized.

"Fix it once, fix it for everyone."

DATA FLOW:
1. log_error_fix() → local storage (encrypted, secrets redacted)
2. verify_solution(success=True) → AUTO-CONTRIBUTES to community brain
3. find_solution() → searches local + community, ranked by trust

SECURITY LAYERS:
- Secret redaction (20+ patterns) BEFORE local storage
- Anonymization (paths, IPs, identifiers) BEFORE sharing
- AES-256 encryption for local data
- Verification gate: only working solutions get shared

USAGE:
    # MCP Server (for Claude Code)
    $ clawdex serve

    # CLI commands
    $ clawdex stats           # Show knowledge base statistics
    $ clawdex search "error"  # Search for solutions
    $ clawdex export          # Export all data
    $ clawdex encrypt         # Enable encryption

    # Environment variables
    CLAWDEX_ENCRYPTED=true    # Enable encryption
    CLAWDEX_PASSWORD=xxx      # Encryption password
    CLAWDEX_COMMUNITY=true    # Enable community brain

License: FSL-1.1-Apache-2.0
"""

__version__ = "0.1.2"
__license__ = "FSL-1.1-Apache-2.0"

# Core security
from .security import redact_secrets, SecretRedactor, Encryptor, CRYPTO_AVAILABLE

# Storage
from .storage import get_storage, configure_storage, LocalStorage

# Sync (contribution + community)
from .sync import anonymize_record, ContributionManager, CommunityBrain, get_community_brain

# Tools (for direct use outside MCP)
from .tools.recording import log_error_fix, log_decision, log_pattern
from .tools.querying import find_solution, find_decision, find_pattern
from .tools.maintenance import verify_solution, get_stats, export_all, purge_all

__all__ = [
    # Version
    "__version__",
    "__license__",
    # Security
    "redact_secrets",
    "SecretRedactor",
    "Encryptor",
    "CRYPTO_AVAILABLE",
    # Storage
    "get_storage",
    "configure_storage",
    "LocalStorage",
    # Sync
    "anonymize_record",
    "ContributionManager",
    "CommunityBrain",
    "get_community_brain",
    # Recording tools
    "log_error_fix",
    "log_decision",
    "log_pattern",
    # Query tools
    "find_solution",
    "find_decision",
    "find_pattern",
    # Maintenance tools
    "verify_solution",
    "get_stats",
    "export_all",
    "purge_all",
]
