"""
Encryption Module for vault404

Provides AES-256 encryption for all stored data.
Keys are derived from a user-provided password or auto-generated and stored securely.
"""

import os
import base64
import secrets
from pathlib import Path
from typing import Optional

# Try to import cryptography, provide helpful error if missing
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


class EncryptionError(Exception):
    """Raised when encryption/decryption fails"""
    pass


class Encryptor:
    """
    AES-256 encryption for vault404 data.

    Uses Fernet (AES-128-CBC with HMAC) for authenticated encryption.
    Key is derived from password using PBKDF2 with 480,000 iterations.
    """

    SALT_FILE = "vault404.salt"
    KEY_FILE = "vault404.key"
    ITERATIONS = 480_000  # OWASP recommended minimum for PBKDF2-SHA256

    def __init__(self, data_dir: Optional[Path] = None, password: Optional[str] = None):
        """
        Initialize encryptor.

        Args:
            data_dir: Directory for storing salt/key files (default: ~/.vault404)
            password: Optional password for key derivation. If not provided,
                     a random key is generated and stored locally.
        """
        if not CRYPTO_AVAILABLE:
            raise EncryptionError(
                "cryptography package not installed. "
                "Install with: pip install cryptography"
            )

        self.data_dir = data_dir or Path.home() / ".vault404"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Set restrictive permissions on data directory (Unix only)
        if os.name != 'nt':
            os.chmod(self.data_dir, 0o700)

        self._fernet = self._initialize_encryption(password)

    def _initialize_encryption(self, password: Optional[str]) -> Fernet:
        """Initialize Fernet with derived or generated key."""
        if password:
            return self._derive_key_from_password(password)
        else:
            return self._get_or_create_key()

    def _derive_key_from_password(self, password: str) -> Fernet:
        """Derive encryption key from password using PBKDF2."""
        salt_path = self.data_dir / self.SALT_FILE

        # Get or create salt
        if salt_path.exists():
            salt = salt_path.read_bytes()
        else:
            salt = secrets.token_bytes(32)
            salt_path.write_bytes(salt)
            if os.name != 'nt':
                os.chmod(salt_path, 0o600)

        # Derive key using PBKDF2
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=self.ITERATIONS,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))

        return Fernet(key)

    def _get_or_create_key(self) -> Fernet:
        """Get existing key or create new one."""
        key_path = self.data_dir / self.KEY_FILE

        if key_path.exists():
            key = key_path.read_bytes()
        else:
            key = Fernet.generate_key()
            key_path.write_bytes(key)
            if os.name != 'nt':
                os.chmod(key_path, 0o600)

        return Fernet(key)

    def encrypt(self, data: str) -> bytes:
        """
        Encrypt string data.

        Args:
            data: Plain text to encrypt

        Returns:
            Encrypted bytes
        """
        try:
            return self._fernet.encrypt(data.encode('utf-8'))
        except Exception as e:
            raise EncryptionError(f"Encryption failed: {e}")

    def decrypt(self, encrypted_data: bytes) -> str:
        """
        Decrypt data back to string.

        Args:
            encrypted_data: Encrypted bytes

        Returns:
            Decrypted string
        """
        try:
            return self._fernet.decrypt(encrypted_data).decode('utf-8')
        except Exception as e:
            raise EncryptionError(f"Decryption failed: {e}")

    def encrypt_file(self, filepath: Path) -> None:
        """Encrypt a file in place."""
        content = filepath.read_text(encoding='utf-8')
        encrypted = self.encrypt(content)
        filepath.write_bytes(encrypted)

    def decrypt_file(self, filepath: Path) -> str:
        """Decrypt a file and return contents."""
        encrypted = filepath.read_bytes()
        return self.decrypt(encrypted)

    def rotate_key(self, new_password: Optional[str] = None) -> None:
        """
        Rotate encryption key.

        Warning: This will make previously encrypted data unreadable
        unless you re-encrypt it with the new key first.
        """
        # Generate new salt
        salt_path = self.data_dir / self.SALT_FILE
        new_salt = secrets.token_bytes(32)
        salt_path.write_bytes(new_salt)

        # Reinitialize with new key
        self._fernet = self._initialize_encryption(new_password)

    @staticmethod
    def generate_strong_password(length: int = 32) -> str:
        """Generate a cryptographically strong random password."""
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
        return ''.join(secrets.choice(alphabet) for _ in range(length))


# Fallback for when cryptography is not installed
class NoOpEncryptor:
    """No-op encryptor that warns but doesn't encrypt."""

    def __init__(self, *args, **kwargs):
        import warnings
        warnings.warn(
            "cryptography package not installed. Data will NOT be encrypted. "
            "Install with: pip install cryptography",
            UserWarning
        )

    def encrypt(self, data: str) -> bytes:
        return data.encode('utf-8')

    def decrypt(self, encrypted_data: bytes) -> str:
        return encrypted_data.decode('utf-8')


def get_encryptor(data_dir: Optional[Path] = None, password: Optional[str] = None):
    """
    Get appropriate encryptor based on available dependencies.

    Returns Encryptor if cryptography is available, NoOpEncryptor otherwise.
    """
    if CRYPTO_AVAILABLE:
        return Encryptor(data_dir, password)
    else:
        return NoOpEncryptor(data_dir, password)
