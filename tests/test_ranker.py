"""Tests for vault404 search ranking system."""

from datetime import datetime, timedelta
from vault404.search.ranker import (
    temporal_decay,
    success_rate_factor,
    usage_popularity_factor,
    calculate_score,
)
from vault404.search.strategies import (
    KeywordStrategy,
    FuzzyStrategy,
    ErrorCodeStrategy,
    multi_strategy_text_score,
)


class TestTemporalDecay:
    """Tests for temporal decay function."""

    def test_recent_items_high_score(self):
        """Recent items should have scores close to 1.0."""
        now = datetime.now()
        score = temporal_decay(now, half_life_days=30, now=now)
        assert score > 0.99

    def test_half_life_decay(self):
        """Items at half-life should have ~0.5 score."""
        now = datetime.now()
        old = now - timedelta(days=30)
        score = temporal_decay(old, half_life_days=30, now=now)
        assert 0.45 < score < 0.55

    def test_double_half_life_decay(self):
        """Items at 2x half-life should have ~0.25 score."""
        now = datetime.now()
        old = now - timedelta(days=60)
        score = temporal_decay(old, half_life_days=30, now=now)
        assert 0.20 < score < 0.30

    def test_very_old_items_low_score(self):
        """Very old items should have scores approaching 0."""
        now = datetime.now()
        very_old = now - timedelta(days=365)
        score = temporal_decay(very_old, half_life_days=30, now=now)
        assert score < 0.01

    def test_future_timestamps_capped(self):
        """Future timestamps should return 1.0."""
        now = datetime.now()
        future = now + timedelta(days=10)
        score = temporal_decay(future, now=now)
        assert score == 1.0


class TestSuccessRateFactor:
    """Tests for success rate Bayesian smoothing."""

    def test_no_data_neutral(self):
        """No data should give neutral ~0.5 score."""
        score = success_rate_factor(0, 0)
        assert 0.45 < score < 0.55

    def test_one_success_positive(self):
        """One success, no failures should be > 0.5."""
        score = success_rate_factor(1, 0)
        assert score > 0.6

    def test_one_failure_negative(self):
        """No successes, one failure should be < 0.5."""
        score = success_rate_factor(0, 1)
        assert score < 0.4

    def test_many_successes_high(self):
        """Many successes should approach 1.0."""
        score = success_rate_factor(100, 0)
        assert score > 0.95

    def test_equal_success_failure_neutral(self):
        """Equal successes and failures should be ~0.5."""
        score = success_rate_factor(10, 10)
        assert 0.45 < score < 0.55


class TestUsagePopularityFactor:
    """Tests for usage popularity factor."""

    def test_unused_neutral(self):
        """Unused items should have 0.5 score."""
        score = usage_popularity_factor(0)
        assert score == 0.5

    def test_some_usage_boost(self):
        """Some usage should boost above 0.5."""
        score = usage_popularity_factor(10)
        assert score > 0.5

    def test_high_usage_capped(self):
        """High usage should approach but not exceed 1.0."""
        score = usage_popularity_factor(1000)
        assert score <= 1.0
        assert score > 0.9


class TestKeywordStrategy:
    """Tests for keyword extraction and matching."""

    def test_extract_error_keywords(self):
        """Should extract common error keywords."""
        strategy = KeywordStrategy()
        keywords = strategy.extract_keywords("TypeError: connection refused")
        assert "typeerror" in keywords or "type" in keywords
        assert "connection" in keywords
        assert "refused" in keywords

    def test_keyword_overlap_score(self):
        """Should score based on keyword overlap."""
        strategy = KeywordStrategy()
        score = strategy.score(
            "connection refused ECONNREFUSED",
            "connection timeout ETIMEDOUT"
        )
        assert score > 0  # "connection" overlaps


class TestFuzzyStrategy:
    """Tests for fuzzy string matching."""

    def test_exact_match_high(self):
        """Exact matches should score high."""
        strategy = FuzzyStrategy()
        score = strategy.score("TypeError: x is undefined", "TypeError: x is undefined")
        assert score > 0.95

    def test_substring_match_high(self):
        """Substring matches should score high."""
        strategy = FuzzyStrategy()
        score = strategy.score("TypeError", "TypeError: cannot read property")
        assert score >= 0.9

    def test_similar_strings_moderate(self):
        """Similar but not identical strings should score moderately."""
        strategy = FuzzyStrategy()
        score = strategy.score("TypeError: x is undefined", "TypeError: y is undefined")
        assert 0.5 < score < 1.0


class TestErrorCodeStrategy:
    """Tests for error code extraction and matching."""

    def test_extract_typescript_error(self):
        """Should extract TypeScript error codes."""
        strategy = ErrorCodeStrategy()
        codes = strategy.extract_codes("error TS2345: Argument of type")
        assert "TS2345" in codes

    def test_extract_node_error(self):
        """Should extract Node.js error codes."""
        strategy = ErrorCodeStrategy()
        codes = strategy.extract_codes("ECONNREFUSED 127.0.0.1:5432")
        assert "ECONNREFUSED" in codes

    def test_extract_python_error(self):
        """Should extract Python error types."""
        strategy = ErrorCodeStrategy()
        codes = strategy.extract_codes("ValueError: invalid literal")
        assert "VALUEERROR" in codes

    def test_exact_code_match_high(self):
        """Exact error code match should score 1.0."""
        strategy = ErrorCodeStrategy()
        score = strategy.score(
            "error TS2345: Argument type mismatch",
            "TS2345: Type 'string' not assignable"
        )
        assert score == 1.0

    def test_no_code_match_zero(self):
        """No error codes should score 0."""
        strategy = ErrorCodeStrategy()
        score = strategy.score("something went wrong", "another error")
        assert score == 0.0


class TestMultiStrategyScore:
    """Tests for combined multi-strategy scoring."""

    def test_exact_error_code_high(self):
        """Exact error code match should score high."""
        score = multi_strategy_text_score(
            "TS2345: Argument of type 'string'",
            "error TS2345: Argument type mismatch"
        )
        assert score > 0.6  # Error code bonus

    def test_similar_messages_moderate(self):
        """Similar messages without exact codes should score moderately."""
        score = multi_strategy_text_score(
            "Cannot read property 'x' of undefined",
            "Cannot read property 'y' of undefined"
        )
        assert score > 0.4

    def test_unrelated_messages_low(self):
        """Unrelated messages should score low."""
        score = multi_strategy_text_score(
            "Database connection timeout",
            "Invalid JSON syntax"
        )
        assert score < 0.3


class TestCalculateScore:
    """Tests for final score calculation."""

    def test_all_positive_signals_high(self):
        """All positive signals should give high score."""
        score = calculate_score(
            text_similarity=0.9,
            context_match=0.8,
            temporal_factor=0.95,
            verified=True,
            success_count=10,
            failure_count=0,
            usage_count=50,
        )
        assert score > 0.8

    def test_low_text_similarity_low(self):
        """Low text similarity should give low score even with other positives."""
        score = calculate_score(
            text_similarity=0.1,
            context_match=0.8,
            temporal_factor=0.95,
            verified=True,
        )
        assert score < 0.6

    def test_old_items_penalized(self):
        """Old items should score lower than recent ones."""
        recent_score = calculate_score(
            text_similarity=0.7,
            temporal_factor=0.95,
        )
        old_score = calculate_score(
            text_similarity=0.7,
            temporal_factor=0.25,
        )
        assert recent_score > old_score

    def test_verified_boost(self):
        """Verified solutions should score higher."""
        verified_score = calculate_score(
            text_similarity=0.7,
            verified=True,
        )
        unverified_score = calculate_score(
            text_similarity=0.7,
            verified=False,
        )
        assert verified_score > unverified_score
