"""Tests for vault404 API authentication."""

import pytest
from pathlib import Path
import tempfile
import shutil

from vault404.api.auth import (
    generate_api_key,
    hash_api_key,
    register_api_key,
    revoke_api_key,
    validate_api_key,
    load_api_keys,
    API_KEYS_FILE,
)


@pytest.fixture
def temp_vault_dir():
    """Create a temporary vault404 directory for testing."""
    temp_dir = tempfile.mkdtemp()
    original_file = API_KEYS_FILE

    # Patch the API_KEYS_FILE to use temp directory
    import vault404.api.auth as auth_module
    auth_module.API_KEYS_FILE = Path(temp_dir) / "api_keys.json"

    yield temp_dir

    # Restore original
    auth_module.API_KEYS_FILE = original_file
    shutil.rmtree(temp_dir, ignore_errors=True)


class TestApiKeyGeneration:
    """Tests for API key generation."""

    def test_generate_api_key_format(self):
        """Generated keys should have correct prefix."""
        key = generate_api_key()
        assert key.startswith("v404_")

    def test_generate_api_key_length(self):
        """Generated keys should be sufficiently long."""
        key = generate_api_key()
        # v404_ prefix + 43 chars (base64url of 32 bytes)
        assert len(key) > 40

    def test_generate_api_key_unique(self):
        """Each generated key should be unique."""
        keys = [generate_api_key() for _ in range(100)]
        assert len(keys) == len(set(keys))


class TestApiKeyHashing:
    """Tests for API key hashing."""

    def test_hash_is_deterministic(self):
        """Same key should always produce same hash."""
        key = "test_key_123"
        hash1 = hash_api_key(key)
        hash2 = hash_api_key(key)
        assert hash1 == hash2

    def test_hash_is_different_for_different_keys(self):
        """Different keys should produce different hashes."""
        hash1 = hash_api_key("key1")
        hash2 = hash_api_key("key2")
        assert hash1 != hash2

    def test_hash_length(self):
        """Hash should be SHA256 (64 hex chars)."""
        h = hash_api_key("test")
        assert len(h) == 64


class TestApiKeyRegistration:
    """Tests for API key registration and validation."""

    def test_register_and_validate(self, temp_vault_dir):
        """Registered keys should validate successfully."""
        key = register_api_key("test-agent")
        assert validate_api_key(key)

    def test_unregistered_key_invalid(self, temp_vault_dir):
        """Unregistered keys should not validate."""
        assert not validate_api_key("fake_key_12345")

    def test_empty_key_invalid(self, temp_vault_dir):
        """Empty keys should not validate."""
        assert not validate_api_key("")
        assert not validate_api_key(None)

    def test_revoke_key(self, temp_vault_dir):
        """Revoked keys should no longer validate."""
        key = register_api_key("to-revoke")
        assert validate_api_key(key)

        result = revoke_api_key(key)
        assert result is True
        assert not validate_api_key(key)

    def test_revoke_nonexistent_key(self, temp_vault_dir):
        """Revoking nonexistent key should return False."""
        result = revoke_api_key("nonexistent_key")
        assert result is False

    def test_register_with_custom_key(self, temp_vault_dir):
        """Should be able to register with a custom key."""
        custom_key = "custom_test_key_123"
        returned_key = register_api_key("custom-agent", key=custom_key)
        assert returned_key == custom_key
        assert validate_api_key(custom_key)


class TestMasterKey:
    """Tests for master API key."""

    def test_master_key_validates(self, temp_vault_dir, monkeypatch):
        """Master key from environment should validate."""
        master = "master_secret_key_123"
        monkeypatch.setenv("VAULT404_MASTER_API_KEY", master)

        assert validate_api_key(master)

    def test_master_key_not_stored(self, temp_vault_dir, monkeypatch):
        """Master key should not be stored in file."""
        master = "master_secret_key_123"
        monkeypatch.setenv("VAULT404_MASTER_API_KEY", master)

        # Validate should work
        assert validate_api_key(master)

        # But key should not be in stored keys
        keys = load_api_keys()
        assert hash_api_key(master) not in keys


class TestApiKeyPersistence:
    """Tests for API key storage persistence."""

    def test_keys_persist_across_loads(self, temp_vault_dir):
        """Keys should persist when reloaded."""
        key = register_api_key("persist-test")

        # Clear in-memory and reload
        keys = load_api_keys()
        assert hash_api_key(key) in keys

    def test_multiple_keys_stored(self, temp_vault_dir):
        """Multiple keys should be stored correctly."""
        keys_registered = []
        for i in range(5):
            key = register_api_key(f"agent-{i}")
            keys_registered.append(key)

        # Verify all keys
        for key in keys_registered:
            assert validate_api_key(key)

        # Check storage
        stored = load_api_keys()
        assert len(stored) == 5
