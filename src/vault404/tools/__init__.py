"""vault404 MCP Tools"""

from .recording import log_error_fix, log_decision, log_pattern
from .querying import find_solution, find_decision, find_pattern
from .maintenance import verify_solution, get_stats, purge_all, export_all

__all__ = [
    # Recording (local storage)
    "log_error_fix",
    "log_decision",
    "log_pattern",
    # Querying (local + community)
    "find_solution",
    "find_decision",
    "find_pattern",
    # Maintenance (verify = auto-contribute)
    "verify_solution",
    "get_stats",
    "purge_all",
    "export_all",
]
