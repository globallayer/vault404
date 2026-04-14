"""
Multi-strategy text matching for vault404 search.

Combines keyword matching, fuzzy matching, and error code extraction
for better search recall without heavy dependencies.
"""

import re
from difflib import SequenceMatcher


# Strategy weights for combining results
STRATEGY_WEIGHTS = {
    "error_code": 0.40,   # Exact error code match is strongest signal
    "keyword": 0.35,      # Keyword overlap is next
    "fuzzy": 0.25,        # Fuzzy matching catches the rest
}


class KeywordStrategy:
    """Extract and match important keywords from error messages."""

    # Common error keywords that indicate the problem type
    ERROR_KEYWORDS = {
        # Connection/Network
        "connection", "timeout", "refused", "reset", "socket", "network",
        "econnrefused", "enotfound", "etimedout", "econnreset",

        # Auth/Permissions
        "denied", "permission", "unauthorized", "forbidden", "auth",
        "authentication", "authorization", "token", "jwt", "session",

        # Data/Type errors
        "null", "undefined", "none", "nan", "type", "typeerror",
        "cannot", "read", "property", "attribute",

        # Import/Module
        "import", "module", "export", "require", "package", "dependency",
        "modulenotfound", "importerror",

        # Syntax/Parse
        "syntax", "parse", "unexpected", "invalid", "malformed",

        # Database
        "database", "query", "sql", "constraint", "duplicate", "foreign",
        "key", "unique", "index", "migration",

        # File/Path
        "file", "path", "directory", "enoent", "exist", "permission",

        # Memory/Resource
        "memory", "heap", "stack", "overflow", "limit", "quota",

        # HTTP/API
        "http", "request", "response", "status", "api", "endpoint",
        "cors", "method", "header",

        # General
        "error", "exception", "failed", "failure", "crash", "panic",
    }

    def extract_keywords(self, text: str) -> set[str]:
        """
        Extract meaningful keywords from error message.

        Args:
            text: Error message or search query

        Returns:
            Set of relevant keywords (lowercase)
        """
        # Extract words (including underscores for snake_case)
        words = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', text.lower())

        # Keep words that are:
        # - In our error keywords set, OR
        # - Longer than 4 chars (likely meaningful)
        keywords = set()
        for word in words:
            if word in self.ERROR_KEYWORDS or len(word) > 4:
                keywords.add(word)

        return keywords

    def score(self, query: str, candidate: str) -> float:
        """
        Score based on keyword overlap.

        Args:
            query: Search query (error message to find)
            candidate: Stored error message

        Returns:
            float: 0.0 to 1.0 overlap score
        """
        q_keywords = self.extract_keywords(query)
        c_keywords = self.extract_keywords(candidate)

        if not q_keywords or not c_keywords:
            return 0.0

        overlap = len(q_keywords & c_keywords)
        union = len(q_keywords | c_keywords)

        if union == 0:
            return 0.0

        # Jaccard similarity
        return overlap / union


class FuzzyStrategy:
    """SequenceMatcher-based fuzzy matching."""

    def score(self, query: str, candidate: str) -> float:
        """
        Calculate fuzzy similarity score.

        Args:
            query: Search query
            candidate: Stored text

        Returns:
            float: 0.0 to 1.0 similarity score
        """
        query_lower = query.lower()
        candidate_lower = candidate.lower()

        # Exact match
        if query_lower == candidate_lower:
            return 1.0

        # Quick substring check (high confidence)
        if query_lower in candidate_lower or candidate_lower in query_lower:
            return 0.9

        # SequenceMatcher ratio
        return SequenceMatcher(None, query_lower, candidate_lower).ratio()


class ErrorCodeStrategy:
    """Match specific error codes and error types."""

    # Patterns for common error codes across languages/frameworks
    ERROR_CODE_PATTERNS = [
        # TypeScript/JavaScript
        r'TS\d{4}',           # TS2345
        r'ERR_[A-Z_]+',       # ERR_MODULE_NOT_FOUND

        # Python
        r'[A-Z][a-z]+Error',  # TypeError, ValueError
        r'[A-Z][a-z]+Exception',  # RuntimeException

        # Node.js
        r'E[A-Z]+',           # ENOENT, ECONNREFUSED

        # HTTP status codes
        r'\b[45]\d{2}\b',     # 404, 500

        # Generic numbered errors
        r'E\d{4,}',           # E0001

        # Rust
        r'E\d{4}',            # E0308

        # Go
        r'[a-z]+: [a-z]+',    # panic: runtime error
    ]

    def __init__(self):
        self._compiled = re.compile(
            '|'.join(f'({p})' for p in self.ERROR_CODE_PATTERNS),
            re.IGNORECASE
        )

    def extract_codes(self, text: str) -> set[str]:
        """
        Extract error codes from text.

        Args:
            text: Error message

        Returns:
            Set of extracted error codes (uppercase)
        """
        matches = self._compiled.findall(text)
        # Flatten tuple results and filter empty
        codes = set()
        for match in matches:
            if isinstance(match, tuple):
                for m in match:
                    if m:
                        codes.add(m.upper())
            elif match:
                codes.add(match.upper())
        return codes

    def score(self, query: str, candidate: str) -> float:
        """
        Score based on error code matches.

        Args:
            query: Search query
            candidate: Stored error message

        Returns:
            float: 1.0 if codes match, 0.0 otherwise
        """
        q_codes = self.extract_codes(query)
        c_codes = self.extract_codes(candidate)

        if not q_codes or not c_codes:
            return 0.0

        # Any overlap in error codes is a strong signal
        if q_codes & c_codes:
            return 1.0

        return 0.0


def multi_strategy_text_score(query: str, candidate: str) -> float:
    """
    Combine multiple search strategies for better matching.

    This is the main entry point for text similarity scoring.
    Combines keyword, fuzzy, and error code strategies.

    Args:
        query: The error message to search for
        candidate: A stored error message to compare against

    Returns:
        float: Combined similarity score (0.0 to 1.0)
    """
    keyword = KeywordStrategy()
    fuzzy = FuzzyStrategy()
    error_code = ErrorCodeStrategy()

    scores = {
        "error_code": error_code.score(query, candidate),
        "keyword": keyword.score(query, candidate),
        "fuzzy": fuzzy.score(query, candidate),
    }

    # Weighted combination
    total = sum(scores[k] * STRATEGY_WEIGHTS[k] for k in scores)

    # Bonus boost if error code matched exactly (very high signal)
    if scores["error_code"] > 0.9:
        total = min(1.0, total + 0.2)

    return total
