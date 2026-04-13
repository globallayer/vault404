"""Sync layer for vault404 - enables opt-in contribution to community knowledge"""

from .anonymizer import anonymize_record
from .contribution import ContributionManager
from .community import CommunityBrain, get_community_brain, federated_search

__all__ = [
    "anonymize_record",
    "ContributionManager",
    "CommunityBrain",
    "get_community_brain",
    "federated_search",
]
