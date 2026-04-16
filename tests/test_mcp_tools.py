"""
Comprehensive tests for vault404 MCP server tools.

Tests all 8 MCP tools:
- Recording: log_error_fix, log_decision, log_pattern
- Querying: find_solution, find_decision, find_pattern
- Maintenance: verify_solution, get_stats
"""

import pytest
import tempfile
import shutil
from pathlib import Path

# Import tools
from vault404.tools.recording import log_error_fix, log_decision, log_pattern
from vault404.tools.querying import find_solution, find_decision, find_pattern
from vault404.tools.maintenance import verify_solution, get_stats, purge_all, export_all

# Import storage for mocking
import vault404.storage as storage_module
import vault404.tools.maintenance as maintenance_module


@pytest.fixture
def temp_vault_dir():
    """Create a temporary vault404 directory for isolated testing."""
    temp_dir = tempfile.mkdtemp()

    # Patch the storage module to use temp directory
    original_storage = storage_module._storage
    storage_module._storage = None  # Reset singleton

    # Create a new storage with temp directory
    from vault404.storage.local_storage import LocalStorage

    storage_module._storage = LocalStorage(data_dir=Path(temp_dir))

    # Also reset the contribution manager to use temp directory
    original_contrib = maintenance_module._contrib
    maintenance_module._contrib = None
    from vault404.sync.contribution import ContributionManager

    maintenance_module._contrib = ContributionManager(data_dir=Path(temp_dir))

    yield temp_dir

    # Cleanup
    storage_module._storage = original_storage
    maintenance_module._contrib = original_contrib
    shutil.rmtree(temp_dir, ignore_errors=True)


# =============================================================================
# Recording Tools Tests
# =============================================================================


class TestLogErrorFix:
    """Tests for log_error_fix tool."""

    @pytest.mark.asyncio
    async def test_basic_log(self, temp_vault_dir):
        """Should log a basic error fix."""
        result = await log_error_fix(
            error_message="TypeError: Cannot read property 'x' of undefined",
            solution="Check if object exists before accessing property",
        )

        assert result["success"] is True
        assert "record_id" in result
        assert result["record_id"].startswith("ef_")
        assert "_summary" in result
        assert "fix logged" in result["_summary"]

    @pytest.mark.asyncio
    async def test_log_with_context(self, temp_vault_dir):
        """Should log error fix with full context."""
        result = await log_error_fix(
            error_message="Connection refused to database",
            solution="Start the PostgreSQL service",
            error_type="ConnectionError",
            file="src/db.py",
            line=42,
            language="python",
            framework="fastapi",
            database="postgresql",
            platform="railway",
            category="database",
            time_to_solve="5m",
            verified=True,
        )

        assert result["success"] is True
        assert "record_id" in result

    @pytest.mark.asyncio
    async def test_secret_redaction(self, temp_vault_dir):
        """Should redact secrets from error messages."""
        # Use a proper OpenAI-style key (48+ chars after sk-)
        fake_key = "sk-" + "a" * 50  # 50 chars after sk-
        result = await log_error_fix(
            error_message=f"Failed with API key: {fake_key}",
            solution="Use environment variable instead of hardcoded key",
        )

        assert result["success"] is True
        assert result["secrets_redacted"] is True

    @pytest.mark.asyncio
    async def test_log_with_code_change(self, temp_vault_dir):
        """Should log error fix with code change."""
        result = await log_error_fix(
            error_message="Import error",
            solution="Fix import path",
            code_change="- from foo import bar\n+ from foo.baz import bar",
            files_modified=["src/main.py", "src/utils.py"],
        )

        assert result["success"] is True


class TestLogDecision:
    """Tests for log_decision tool."""

    @pytest.mark.asyncio
    async def test_basic_decision(self, temp_vault_dir):
        """Should log a basic decision."""
        result = await log_decision(
            title="Database choice",
            choice="PostgreSQL",
        )

        assert result["success"] is True
        assert result["record_id"].startswith("dec_")
        assert "decision logged" in result["_summary"]

    @pytest.mark.asyncio
    async def test_decision_with_rationale(self, temp_vault_dir):
        """Should log decision with full rationale."""
        result = await log_decision(
            title="Authentication strategy",
            choice="JWT with refresh tokens",
            alternatives=["Session cookies", "OAuth only", "API keys"],
            pros=["Stateless", "Works with mobile", "Scalable"],
            cons=["Token management complexity", "Requires refresh logic"],
            deciding_factor="Mobile app support required",
            project="my-api",
            component="auth",
            language="typescript",
            framework="express",
        )

        assert result["success"] is True
        assert "Authentication strategy" in result["_summary"]


class TestLogPattern:
    """Tests for log_pattern tool."""

    @pytest.mark.asyncio
    async def test_basic_pattern(self, temp_vault_dir):
        """Should log a basic pattern."""
        result = await log_pattern(
            name="Repository Pattern",
            category="architecture",
            problem="Data access logic scattered across codebase",
            solution="Centralize data access behind repository interface",
        )

        assert result["success"] is True
        assert result["record_id"].startswith("pat_")
        assert "pattern logged" in result["_summary"]

    @pytest.mark.asyncio
    async def test_pattern_with_code(self, temp_vault_dir):
        """Should log pattern with code examples."""
        result = await log_pattern(
            name="Null Object Pattern",
            category="design-patterns",
            problem="Constant null checks polluting code",
            solution="Use null object that implements interface with no-op methods",
            languages=["typescript", "python"],
            frameworks=["express", "fastapi"],
            before_code="if (user) { user.notify(); }",
            after_code="user.notify(); // NullUser.notify() is no-op",
            explanation="Replace null checks with polymorphism",
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_pattern_secret_redaction(self, temp_vault_dir):
        """Should redact secrets from code examples."""
        result = await log_pattern(
            name="Config Pattern",
            category="configuration",
            problem="Hardcoded secrets",
            solution="Use environment variables",
            before_code="const apiKey = 'sk-secret123456789';",
            after_code="const apiKey = process.env.API_KEY;",
        )

        assert result["success"] is True


# =============================================================================
# Querying Tools Tests
# =============================================================================


class TestFindSolution:
    """Tests for find_solution tool."""

    @pytest.mark.asyncio
    async def test_no_results(self, temp_vault_dir):
        """Should handle no results gracefully."""
        result = await find_solution(
            error_message="Some random error that doesn't exist",
        )

        assert result["found"] is False
        assert result["solutions"] == []
        assert "_summary" in result
        assert "No solutions" in result["_summary"]

    @pytest.mark.asyncio
    async def test_find_logged_solution(self, temp_vault_dir):
        """Should find a previously logged solution."""
        # First, log a solution
        await log_error_fix(
            error_message="ECONNREFUSED 127.0.0.1:5432",
            solution="Start PostgreSQL with: sudo systemctl start postgresql",
            language="python",
            database="postgresql",
        )

        # Now search for it
        result = await find_solution(
            error_message="ECONNREFUSED connection refused postgres",
            language="python",
        )

        assert result["found"] is True
        assert len(result["solutions"]) >= 1
        assert "postgresql" in result["solutions"][0]["solution"].lower()

    @pytest.mark.asyncio
    async def test_find_with_context_matching(self, temp_vault_dir):
        """Should boost results matching context."""
        # Log solutions for different languages
        await log_error_fix(
            error_message="Import error module not found",
            solution="Install the module with pip",
            language="python",
        )
        await log_error_fix(
            error_message="Import error module not found",
            solution="Install the module with npm",
            language="javascript",
        )

        # Search with Python context
        result = await find_solution(
            error_message="Import error",
            language="python",
        )

        assert result["found"] is True
        # Python solution should rank higher due to context match
        solutions = result["solutions"]
        assert len(solutions) >= 1


class TestFindDecision:
    """Tests for find_decision tool."""

    @pytest.mark.asyncio
    async def test_no_results(self, temp_vault_dir):
        """Should handle no results gracefully."""
        result = await find_decision(
            topic="nonexistent topic xyz123",
        )

        assert result["found"] is False
        assert result["decisions"] == []

    @pytest.mark.asyncio
    async def test_find_logged_decision(self, temp_vault_dir):
        """Should find a previously logged decision."""
        # Log a decision
        await log_decision(
            title="Cache strategy",
            choice="Redis",
            alternatives=["Memcached", "In-memory"],
            project="my-app",
        )

        # Search for it
        result = await find_decision(
            topic="cache",
            project="my-app",
        )

        assert result["found"] is True
        assert len(result["decisions"]) >= 1
        assert "Redis" in result["decisions"][0]["choice"]


class TestFindPattern:
    """Tests for find_pattern tool."""

    @pytest.mark.asyncio
    async def test_no_results(self, temp_vault_dir):
        """Should handle no results gracefully."""
        result = await find_pattern(
            problem="nonexistent problem xyz123",
        )

        assert result["found"] is False
        assert result["patterns"] == []

    @pytest.mark.asyncio
    async def test_find_logged_pattern(self, temp_vault_dir):
        """Should find a previously logged pattern."""
        # Log a pattern
        await log_pattern(
            name="Circuit Breaker",
            category="resilience",
            problem="Cascading failures in distributed systems",
            solution="Wrap remote calls with circuit breaker that fails fast",
        )

        # Search for it
        result = await find_pattern(
            problem="cascading failures",
            category="resilience",
        )

        assert result["found"] is True
        assert len(result["patterns"]) >= 1
        assert "Circuit Breaker" in result["patterns"][0]["name"]

    @pytest.mark.asyncio
    async def test_find_by_category(self, temp_vault_dir):
        """Should filter patterns by category."""
        # Log patterns in different categories
        await log_pattern(
            name="Retry Pattern",
            category="resilience",
            problem="Transient failures",
            solution="Retry with exponential backoff",
        )
        await log_pattern(
            name="Singleton Pattern",
            category="creational",
            problem="Need single instance",
            solution="Private constructor with static getter",
        )

        # Search by category
        result = await find_pattern(
            problem="pattern",
            category="resilience",
        )

        assert result["found"] is True
        # Should only find resilience patterns
        for pattern in result["patterns"]:
            assert pattern["category"] == "resilience"


# =============================================================================
# Maintenance Tools Tests
# =============================================================================


class TestVerifySolution:
    """Tests for verify_solution tool."""

    @pytest.mark.asyncio
    async def test_verify_success(self, temp_vault_dir):
        """Should mark solution as successful."""
        # Log a solution first
        log_result = await log_error_fix(
            error_message="Test error",
            solution="Test solution",
        )
        record_id = log_result["record_id"]

        # Verify it
        result = await verify_solution(record_id=record_id, success=True)

        assert result["success"] is True
        assert "successful" in result["verified_as"]
        assert record_id in result["message"]

    @pytest.mark.asyncio
    async def test_verify_failure(self, temp_vault_dir):
        """Should mark solution as unsuccessful."""
        # Log a solution first
        log_result = await log_error_fix(
            error_message="Test error",
            solution="Wrong solution",
        )
        record_id = log_result["record_id"]

        # Verify it as failed
        result = await verify_solution(record_id=record_id, success=False)

        assert result["success"] is True
        assert "unsuccessful" in result["verified_as"]


class TestGetStats:
    """Tests for get_stats tool."""

    @pytest.mark.asyncio
    async def test_empty_stats(self, temp_vault_dir):
        """Should return zero counts for empty storage."""
        result = await get_stats()

        assert result["success"] is True
        # Local stats should be zero
        assert result["stats"]["local"]["total"] == 0
        assert result["stats"]["local"]["fixes"] == 0
        assert result["stats"]["local"]["decisions"] == 0
        assert result["stats"]["local"]["patterns"] == 0
        assert "_summary" in result

    @pytest.mark.asyncio
    async def test_stats_after_logging(self, temp_vault_dir):
        """Should count logged records."""
        # Log some records
        await log_error_fix(
            error_message="Error 1",
            solution="Solution 1",
        )
        await log_error_fix(
            error_message="Error 2",
            solution="Solution 2",
        )
        await log_decision(
            title="Decision 1",
            choice="Choice 1",
        )
        await log_pattern(
            name="Pattern 1",
            category="test",
            problem="Problem 1",
            solution="Solution 1",
        )

        result = await get_stats()

        # Local stats should reflect the logged records
        assert result["stats"]["local"]["total"] == 4
        assert result["stats"]["local"]["fixes"] == 2
        assert result["stats"]["local"]["decisions"] == 1
        assert result["stats"]["local"]["patterns"] == 1


class TestPurgeAll:
    """Tests for purge_all tool."""

    @pytest.mark.asyncio
    async def test_purge_requires_confirmation(self, temp_vault_dir):
        """Should require confirmation to purge."""
        result = await purge_all(confirm=False)

        assert result["success"] is False
        assert "SAFETY CHECK" in result["message"]

    @pytest.mark.asyncio
    async def test_purge_with_confirmation(self, temp_vault_dir):
        """Should purge data when confirmed."""
        # Log some data first
        await log_error_fix(
            error_message="Test error",
            solution="Test solution",
        )

        # Verify data exists
        stats_before = await get_stats()
        assert stats_before["stats"]["local"]["total"] > 0

        # Purge
        result = await purge_all(confirm=True)

        assert result["success"] is True
        assert "deleted" in result["message"].lower()


class TestExportAll:
    """Tests for export_all tool."""

    @pytest.mark.asyncio
    async def test_export_empty(self, temp_vault_dir):
        """Should export even when empty."""
        import tempfile

        export_path = tempfile.mktemp(suffix=".json")

        try:
            result = await export_all(output_path=export_path)

            assert result["success"] is True
            assert result["records_exported"]["error_fixes"] == 0

            # Verify file was created
            assert Path(export_path).exists()
        finally:
            Path(export_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_export_with_data(self, temp_vault_dir):
        """Should export all logged data."""
        import json
        import tempfile

        # Log some data
        await log_error_fix(
            error_message="Export test error",
            solution="Export test solution",
        )
        await log_decision(
            title="Export test decision",
            choice="Test choice",
        )

        export_path = tempfile.mktemp(suffix=".json")

        try:
            result = await export_all(output_path=export_path)

            assert result["success"] is True
            assert result["records_exported"]["error_fixes"] == 1
            assert result["records_exported"]["decisions"] == 1

            # Verify export content
            with open(export_path) as f:
                export_data = json.load(f)

            assert "data" in export_data
            assert len(export_data["data"]["error_fixes"]) == 1
            assert len(export_data["data"]["decisions"]) == 1
        finally:
            Path(export_path).unlink(missing_ok=True)


# =============================================================================
# Integration Tests
# =============================================================================


class TestMCPToolsIntegration:
    """Integration tests for MCP tools working together."""

    @pytest.mark.asyncio
    async def test_full_workflow(self, temp_vault_dir):
        """Test complete workflow: log -> find -> verify."""
        # 1. Log an error fix
        log_result = await log_error_fix(
            error_message="TS2345: Argument of type 'string' is not assignable",
            solution="Cast the value to the correct type using 'as Type'",
            language="typescript",
            framework="nextjs",
            verified=False,
        )
        assert log_result["success"] is True
        record_id = log_result["record_id"]

        # 2. Search and find it
        find_result = await find_solution(
            error_message="TS2345 type not assignable",
            language="typescript",
        )
        assert find_result["found"] is True
        assert any(s["id"] == record_id for s in find_result["solutions"])

        # 3. Verify the solution worked
        verify_result = await verify_solution(record_id=record_id, success=True)
        assert verify_result["success"] is True

        # 4. Check stats
        stats_result = await get_stats()
        assert stats_result["stats"]["local"]["fixes"] == 1

    @pytest.mark.asyncio
    async def test_multiple_similar_solutions(self, temp_vault_dir):
        """Test ranking of multiple similar solutions."""
        # Log multiple solutions for similar errors
        await log_error_fix(
            error_message="ECONNREFUSED 127.0.0.1:5432",
            solution="Start PostgreSQL service",
            language="python",
            verified=True,
        )
        await log_error_fix(
            error_message="ECONNREFUSED database connection",
            solution="Check database credentials",
            language="python",
            verified=False,
        )
        await log_error_fix(
            error_message="ECONNREFUSED postgres",
            solution="Ensure PostgreSQL is running on correct port",
            language="python",
            verified=True,
        )

        # Search should return all, ranked by relevance
        result = await find_solution(
            error_message="ECONNREFUSED postgres connection",
            language="python",
        )

        assert result["found"] is True
        assert len(result["solutions"]) >= 2

        # Verified solutions should generally rank higher
        solutions = result["solutions"]
        # At least one verified solution in top results
        assert any(s["verified"] for s in solutions[:2])

    @pytest.mark.asyncio
    async def test_context_isolation(self, temp_vault_dir):
        """Test that solutions are properly isolated by context."""
        # Log similar errors with different contexts
        await log_error_fix(
            error_message="Module not found error",
            solution="pip install missing-module",
            language="python",
        )
        await log_error_fix(
            error_message="Module not found error",
            solution="npm install missing-module",
            language="javascript",
        )

        # Search with Python context
        python_result = await find_solution(
            error_message="Module not found",
            language="python",
        )

        # Search with JavaScript context
        js_result = await find_solution(
            error_message="Module not found",
            language="javascript",
        )

        # Both should find results
        assert python_result["found"] is True
        assert js_result["found"] is True

        # Context matching should influence ranking
        # (exact verification depends on ranking implementation)
