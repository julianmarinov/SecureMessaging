"""
Key management for SecureMessaging client.
Handles identity key generation, storage, and retrieval.
"""

import os
import sqlite3
from pathlib import Path
from typing import Optional, Tuple
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.constants import KEY_SIZE

class KeyManager:
    """Manages cryptographic keys for a user."""

    def __init__(self, db_path: str):
        """
        Initialize key manager.

        Args:
            db_path: Path to client database
        """
        self.db_path = db_path
        self._ensure_db_exists()

    def _ensure_db_exists(self):
        """Ensure database and tables exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create user_keys table if needed
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_keys (
                key_type TEXT PRIMARY KEY,
                encrypted_key BLOB NOT NULL,
                salt BLOB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create public_keys cache table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS public_keys (
                username TEXT PRIMARY KEY,
                public_key BLOB NOT NULL,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()

    def generate_identity_keypair(self, password: str) -> Tuple[bytes, bytes]:
        """
        Generate X25519 identity keypair and store encrypted private key.

        Args:
            password: Password to encrypt private key

        Returns:
            (public_key_bytes, private_key_bytes)
        """
        # Generate keypair
        private_key = x25519.X25519PrivateKey.generate()
        public_key = private_key.public_key()

        # Get raw bytes
        private_key_bytes = private_key.private_bytes_raw()
        public_key_bytes = public_key.public_bytes_raw()

        # Encrypt and store private key
        self._store_private_key(private_key_bytes, password)

        return public_key_bytes, private_key_bytes

    def _derive_key_from_password(self, password: str, salt: bytes) -> bytes:
        """
        Derive encryption key from password using PBKDF2.

        Args:
            password: User password
            salt: Random salt

        Returns:
            32-byte key
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=KEY_SIZE,
            salt=salt,
            iterations=100000,  # OWASP recommendation
        )
        return kdf.derive(password.encode('utf-8'))

    def _store_private_key(self, private_key: bytes, password: str):
        """
        Store private key encrypted with password.

        Args:
            private_key: Raw private key bytes
            password: Password to encrypt with
        """
        # Generate random salt
        salt = os.urandom(16)

        # Derive encryption key from password
        encryption_key = self._derive_key_from_password(password, salt)

        # Encrypt private key with ChaCha20-Poly1305
        cipher = ChaCha20Poly1305(encryption_key)
        nonce = os.urandom(12)
        encrypted_key = nonce + cipher.encrypt(nonce, private_key, None)

        # Store in database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """INSERT OR REPLACE INTO user_keys (key_type, encrypted_key, salt)
               VALUES (?, ?, ?)""",
            ('identity_private', encrypted_key, salt)
        )

        conn.commit()
        conn.close()

    def load_private_key(self, password: str) -> Optional[x25519.X25519PrivateKey]:
        """
        Load and decrypt private key.

        Args:
            password: Password to decrypt with

        Returns:
            Private key object or None if not found/wrong password
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT encrypted_key, salt FROM user_keys WHERE key_type = ?",
            ('identity_private',)
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        encrypted_key, salt = row

        # Derive decryption key
        decryption_key = self._derive_key_from_password(password, salt)

        try:
            # Decrypt private key
            cipher = ChaCha20Poly1305(decryption_key)
            nonce = encrypted_key[:12]
            ciphertext = encrypted_key[12:]
            private_key_bytes = cipher.decrypt(nonce, ciphertext, None)

            # Reconstruct key object
            return x25519.X25519PrivateKey.from_private_bytes(private_key_bytes)

        except Exception:
            # Wrong password or corrupted data
            return None

    def has_identity_key(self) -> bool:
        """Check if identity key exists."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM user_keys WHERE key_type = ?",
            ('identity_private',)
        )
        exists = cursor.fetchone() is not None
        conn.close()
        return exists

    def cache_public_key(self, username: str, public_key: bytes):
        """
        Cache a user's public key.

        Args:
            username: Username
            public_key: Raw public key bytes
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """INSERT OR REPLACE INTO public_keys (username, public_key, fetched_at)
               VALUES (?, ?, CURRENT_TIMESTAMP)""",
            (username, public_key)
        )

        conn.commit()
        conn.close()

    def get_cached_public_key(self, username: str) -> Optional[bytes]:
        """
        Get cached public key for a user.

        Args:
            username: Username

        Returns:
            Public key bytes or None if not cached
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT public_key FROM public_keys WHERE username = ?",
            (username,)
        )
        row = cursor.fetchone()
        conn.close()

        return row[0] if row else None

    def generate_ephemeral_keypair(self) -> Tuple[x25519.X25519PrivateKey, x25519.X25519PublicKey]:
        """
        Generate ephemeral keypair for Perfect Forward Secrecy.

        Returns:
            (private_key, public_key)
        """
        private_key = x25519.X25519PrivateKey.generate()
        public_key = private_key.public_key()
        return private_key, public_key
