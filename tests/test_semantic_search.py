"""
Tests for vault404 semantic search functionality.

Tests cover:
- Embedding generation (when sentence-transformers available)
- Graceful degradation (when not available)
- Hybrid search combining semantic + text matching
- Cosine similarity calculations
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch

from vault404.search import embeddings
from vault404.storage.local_storage import LocalStorage
from vault404.storage.schemas import Context

import vault404.storage as storage_module


@pytest.fixture
def temp_vault_dir():
    """Create a temporary vault404 directory for isolated testing."""
    temp_dir = tempfile.mkdtemp()

    # Patch the storage module to use temp directory
    original_storage = storage_module._storage
    storage_module._storage = None

    storage_module._storage = LocalStorage(data_dir=Path(temp_dir))

    yield temp_dir

    storage_module._storage = original_storage
    shutil.rmtree(temp_dir, ignore_errors=True)


class TestEmbeddingUtils:
    """Tests for embedding utility functions."""

    def test_cosine_similarity_identical(self):
        """Identical vectors should have similarity 1.0."""
        vec = [1.0, 0.0, 0.0, 1.0]
        sim = embeddings.cosine_similarity(vec, vec)
        assert sim == pytest.approx(1.0)

    def test_cosine_similarity_orthogonal(self):
        """Orthogonal vectors should have similarity 0.0."""
        vec1 = [1.0, 0.0]
        vec2 = [0.0, 1.0]
        sim = embeddings.cosine_similarity(vec1, vec2)
        assert sim == pytest.approx(0.0)

    def test_cosine_similarity_opposite(self):
        """Opposite vectors should have similarity -1.0."""
        vec1 = [1.0, 0.0]
        vec2 = [-1.0, 0.0]
        sim = embeddings.cosine_similarity(vec1, vec2)
        assert sim == pytest.approx(-1.0)

    def test_cosine_similarity_none_inputs(self):
        """None inputs should return 0.0."""
        assert embeddings.cosine_similarity(None, [1.0, 0.0]) == 0.0
        assert embeddings.cosine_similarity([1.0, 0.0], None) == 0.0
        assert embeddings.cosine_similarity(None, None) == 0.0

    def test_cosine_similarity_zero_vector(self):
        """Zero vectors should return 0.0."""
        vec1 = [0.0, 0.0]
        vec2 = [1.0, 1.0]
        sim = embeddings.cosine_similarity(vec1, vec2)
        assert sim == 0.0

    def test_combine_text_for_embedding_basic(self):
        """Should combine error message only."""
        text = embeddings.combine_text_for_embedding("TypeError: x is undefined")
        assert "TypeError" in text
        assert "undefined" in text

    def test_combine_text_for_embedding_with_context(self):
        """Should include context in combined text."""
        context = {
            "language": "typescript",
            "framework": "nextjs",
            "database": "postgresql",
        }
        text = embeddings.combine_text_for_embedding("Connection refused", context)
        assert "Connection refused" in text
        assert "typescript" in text
        assert "nextjs" in text
        assert "postgresql" in text


class TestEmbeddingAvailability:
    """Tests for graceful degradation when embeddings unavailable."""

    def test_is_available_returns_bool(self):
        """is_available should return a boolean."""
        result = embeddings.is_available()
        assert isinstance(result, bool)

    def test_get_embedding_returns_none_or_list(self):
        """get_embedding should return None or list of floats."""
        result = embeddings.get_embedding("test text")
        assert result is None or isinstance(result, list)
        if result is not None:
            assert all(isinstance(x, float) for x in result)

    def test_semantic_similarity_fallback(self):
        """semantic_similarity should return 0.0 when embeddings unavailable."""
        with patch.object(embeddings, 'get_embedding', return_value=None):
            sim = embeddings.semantic_similarity("text1", "text2")
            assert sim == 0.0


class TestHybridSearch:
    """Tests for hybrid semantic + text search."""

    @pytest.mark.asyncio
    async def test_search_without_embeddings(self, temp_vault_dir):
        """Search should work with text-only when embeddings unavailable."""
        storage = storage_module._storage

        # Store a fix (won't have embedding if sentence-transformers not installed)
        from vault404.storage.schemas import ErrorFix, ErrorInfo, SolutionInfo
        fix = ErrorFix(
            error=ErrorInfo(message="Cannot read property 'map' of undefined"),
            solution=SolutionInfo(description="Check if array exists before mapping"),
        )
        await storage.store_error_fix(fix)

        # Search should still work
        results = await storage.find_solutions("Cannot read property 'map' of undefined")
        assert len(results) > 0
        assert results[0]["error"] == "Cannot read property 'map' of undefined"[:200]

    @pytest.mark.asyncio
    async def test_search_returns_score(self, temp_vault_dir):
        """Search results should include score."""
        storage = storage_module._storage

        from vault404.storage.schemas import ErrorFix, ErrorInfo, SolutionInfo
        fix = ErrorFix(
            error=ErrorInfo(message="Connection refused"),
            solution=SolutionInfo(description="Start the database service"),
        )
        await storage.store_error_fix(fix)

        results = await storage.find_solutions("Connection refused")
        assert len(results) > 0
        assert "score" in results[0]
        assert 0.0 <= results[0]["score"] <= 1.0

    @pytest.mark.asyncio
    async def test_search_with_context_matching(self, temp_vault_dir):
        """Search should boost results with matching context."""
        storage = storage_module._storage

        from vault404.storage.schemas import ErrorFix, ErrorInfo, SolutionInfo

        # Store fix with Python context
        fix_python = ErrorFix(
            error=ErrorInfo(message="ImportError: No module named 'foo'"),
            solution=SolutionInfo(description="Install the foo package"),
            context=Context(language="python"),
        )
        await storage.store_error_fix(fix_python)

        # Search with matching context should find it
        results = await storage.find_solutions(
            "ImportError: No module named 'foo'",
            context=Context(language="python"),
        )
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_similar_errors_found(self, temp_vault_dir):
        """Similar but not identical errors should be found."""
        storage = storage_module._storage

        from vault404.storage.schemas import ErrorFix, ErrorInfo, SolutionInfo

        # Store fix for one error
        fix = ErrorFix(
            error=ErrorInfo(message="TypeError: Cannot read property 'x' of undefined"),
            solution=SolutionInfo(description="Add null check before accessing property"),
        )
        await storage.store_error_fix(fix)

        # Search with similar error
        results = await storage.find_solutions(
            "TypeError: Cannot read property 'name' of undefined"
        )
        # Should find the similar error
        assert len(results) > 0


class TestEmbeddingStorage:
    """Tests for embedding storage in records."""

    @pytest.mark.asyncio
    async def test_store_includes_has_embedding_flag(self, temp_vault_dir):
        """store_error_fix should return has_embedding flag."""
        storage = storage_module._storage

        from vault404.storage.schemas import ErrorFix, ErrorInfo, SolutionInfo
        fix = ErrorFix(
            error=ErrorInfo(message="Test error"),
            solution=SolutionInfo(description="Test solution"),
        )
        result = await storage.store_error_fix(fix)

        assert "has_embedding" in result
        assert isinstance(result["has_embedding"], bool)

    @pytest.mark.asyncio
    async def test_decision_includes_has_embedding_flag(self, temp_vault_dir):
        """store_decision should return has_embedding flag."""
        storage = storage_module._storage

        from vault404.storage.schemas import Decision
        decision = Decision(
            title="Test decision",
            choice="Option A",
            alternatives=["Option B"],
        )
        result = await storage.store_decision(decision)

        assert "has_embedding" in result
        assert isinstance(result["has_embedding"], bool)

    @pytest.mark.asyncio
    async def test_pattern_includes_has_embedding_flag(self, temp_vault_dir):
        """store_pattern should return has_embedding flag."""
        storage = storage_module._storage

        from vault404.storage.schemas import Pattern
        pattern = Pattern(
            name="Test pattern",
            category="testing",
            problem="Test problem",
            solution="Test solution",
        )
        result = await storage.store_pattern(pattern)

        assert "has_embedding" in result
        assert isinstance(result["has_embedding"], bool)


class TestFindMostSimilar:
    """Tests for find_most_similar utility."""

    def test_find_most_similar_empty_candidates(self):
        """Should return empty list for empty candidates."""
        query = [1.0, 0.0, 0.0]
        results = embeddings.find_most_similar(query, [], top_k=5)
        assert results == []

    def test_find_most_similar_none_query(self):
        """Should return empty list for None query."""
        candidates = [("id1", [1.0, 0.0])]
        results = embeddings.find_most_similar(None, candidates, top_k=5)
        assert results == []

    def test_find_most_similar_threshold(self):
        """Should filter results below threshold."""
        query = [1.0, 0.0]
        candidates = [
            ("id1", [1.0, 0.0]),  # sim = 1.0
            ("id2", [0.0, 1.0]),  # sim = 0.0
        ]
        results = embeddings.find_most_similar(query, candidates, threshold=0.5)
        assert len(results) == 1
        assert results[0][0] == "id1"

    def test_find_most_similar_top_k(self):
        """Should return at most top_k results."""
        query = [1.0, 0.0]
        candidates = [
            ("id1", [0.9, 0.1]),
            ("id2", [0.8, 0.2]),
            ("id3", [0.7, 0.3]),
        ]
        results = embeddings.find_most_similar(query, candidates, top_k=2, threshold=0.0)
        assert len(results) == 2

    def test_find_most_similar_sorted_by_similarity(self):
        """Results should be sorted by similarity descending."""
        query = [1.0, 0.0]
        candidates = [
            ("id_low", [0.1, 0.9]),
            ("id_high", [0.99, 0.01]),
            ("id_mid", [0.7, 0.3]),
        ]
        results = embeddings.find_most_similar(query, candidates, threshold=0.0)
        sims = [r[1] for r in results]
        assert sims == sorted(sims, reverse=True)
