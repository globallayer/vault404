"""Tests for vault404 API models input validation."""

import pytest
from pydantic import ValidationError

from vault404.api.models import (
    SolutionSearchRequest,
    SolutionLogRequest,
    SolutionVerifyRequest,
    DecisionLogRequest,
    PatternLogRequest,
    MAX_ERROR_MESSAGE_LENGTH,
    MAX_LIST_ITEMS,
)


class TestSolutionSearchRequest:
    """Tests for SolutionSearchRequest validation."""

    def test_valid_request(self):
        """Valid request should pass validation."""
        req = SolutionSearchRequest(error_message="TypeError: cannot read property")
        assert req.error_message == "TypeError: cannot read property"

    def test_error_message_too_short(self):
        """Error message below minimum length should fail."""
        with pytest.raises(ValidationError) as exc_info:
            SolutionSearchRequest(error_message="ab")
        assert "at least" in str(exc_info.value).lower()

    def test_error_message_too_long(self):
        """Error message above maximum length should fail."""
        with pytest.raises(ValidationError):
            SolutionSearchRequest(error_message="x" * (MAX_ERROR_MESSAGE_LENGTH + 1))

    def test_limit_bounds(self):
        """Limit should be within bounds."""
        # Valid limits
        req = SolutionSearchRequest(error_message="test error", limit=1)
        assert req.limit == 1

        req = SolutionSearchRequest(error_message="test error", limit=50)
        assert req.limit == 50

        # Invalid limits
        with pytest.raises(ValidationError):
            SolutionSearchRequest(error_message="test error", limit=0)

        with pytest.raises(ValidationError):
            SolutionSearchRequest(error_message="test error", limit=51)

    def test_optional_filters(self):
        """Optional filters should accept valid values."""
        req = SolutionSearchRequest(
            error_message="test error",
            language="python",
            framework="fastapi",
            database="postgresql",
        )
        assert req.language == "python"
        assert req.framework == "fastapi"
        assert req.database == "postgresql"


class TestSolutionLogRequest:
    """Tests for SolutionLogRequest validation."""

    def test_valid_request(self):
        """Valid request should pass validation."""
        req = SolutionLogRequest(
            error_message="Connection refused",
            solution="Check database is running",
        )
        assert "Connection" in req.error_message

    def test_solution_too_short(self):
        """Solution below minimum length should fail."""
        with pytest.raises(ValidationError):
            SolutionLogRequest(
                error_message="Test error message",
                solution="ab",
            )

    def test_files_modified_limit(self):
        """Files modified list should have max items."""
        # Valid
        req = SolutionLogRequest(
            error_message="Test error",
            solution="Test solution",
            files_modified=["file1.py", "file2.py"],
        )
        assert len(req.files_modified) == 2

        # Too many
        with pytest.raises(ValidationError):
            SolutionLogRequest(
                error_message="Test error",
                solution="Test solution",
                files_modified=[f"file{i}.py" for i in range(MAX_LIST_ITEMS + 1)],
            )

    def test_line_number_bounds(self):
        """Line number should be positive."""
        req = SolutionLogRequest(
            error_message="Test error",
            solution="Test solution",
            line=1,
        )
        assert req.line == 1

        with pytest.raises(ValidationError):
            SolutionLogRequest(
                error_message="Test error",
                solution="Test solution",
                line=0,
            )

    def test_whitespace_stripping(self):
        """Leading/trailing whitespace should be stripped."""
        req = SolutionLogRequest(
            error_message="  Test error  ",
            solution="  Test solution  ",
        )
        assert req.error_message == "Test error"
        assert req.solution == "Test solution"


class TestSolutionVerifyRequest:
    """Tests for SolutionVerifyRequest validation."""

    def test_valid_request(self):
        """Valid request should pass validation."""
        req = SolutionVerifyRequest(id="ef_20260413_195401", success=True)
        assert req.id == "ef_20260413_195401"
        assert req.success is True

    def test_invalid_id_format(self):
        """Invalid ID format should fail."""
        with pytest.raises(ValidationError):
            SolutionVerifyRequest(id="invalid id with spaces!", success=True)

    def test_valid_id_formats(self):
        """Various valid ID formats should pass."""
        valid_ids = [
            "ef_20260413_195401",
            "dec_20260101_000000",
            "pat_12345678_123456",
            "simple-id-123",
            "underscore_id",
        ]
        for id_val in valid_ids:
            req = SolutionVerifyRequest(id=id_val, success=True)
            assert req.id == id_val


class TestDecisionLogRequest:
    """Tests for DecisionLogRequest validation."""

    def test_valid_request(self):
        """Valid request should pass validation."""
        req = DecisionLogRequest(
            title="Database choice",
            choice="PostgreSQL",
            alternatives=["MySQL", "MongoDB"],
            pros=["ACID compliance", "JSON support"],
            cons=["More complex setup"],
        )
        assert req.title == "Database choice"
        assert len(req.alternatives) == 2

    def test_lists_too_long(self):
        """Lists exceeding max items should fail."""
        with pytest.raises(ValidationError):
            DecisionLogRequest(
                title="Test decision",
                choice="Test choice",
                alternatives=[f"alt{i}" for i in range(MAX_LIST_ITEMS + 1)],
            )

    def test_list_item_too_long(self):
        """List items exceeding max length should fail."""
        with pytest.raises(ValidationError):
            DecisionLogRequest(
                title="Test decision",
                choice="Test choice",
                pros=["x" * 1000],  # Too long
            )


class TestPatternLogRequest:
    """Tests for PatternLogRequest validation."""

    def test_valid_request(self):
        """Valid request should pass validation."""
        req = PatternLogRequest(
            name="Repository Pattern",
            category="architecture",
            problem="Data access scattered across codebase",
            solution="Centralize data access behind repository interface",
        )
        assert req.name == "Repository Pattern"

    def test_required_fields(self):
        """Required fields should be enforced."""
        with pytest.raises(ValidationError):
            PatternLogRequest(
                name="Test",
                # Missing category, problem, solution
            )

    def test_code_fields_accept_long_content(self):
        """Code fields should accept longer content."""
        long_code = "x" * 10000  # 10KB of code
        req = PatternLogRequest(
            name="Test pattern",
            category="test",
            problem="Test problem",
            solution="Test solution",
            before_code=long_code,
            after_code=long_code,
        )
        assert len(req.before_code) == 10000
