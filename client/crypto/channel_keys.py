"""
Channel key management for SecureMessaging.
Handles symmetric key generation, encryption, and storage for group channels.
"""

import os
import base64
import sqlite3
from typing import Optional, Dict
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives import serialization

from client.crypto.encryption import MessageEncryptor
from client.crypto.key_exchange import ECDHKeyExchange
from shared.constants import KEY_SIZE, NONCE_SIZE


class ChannelKeyManager:
    """Manages channel encryption keys."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize channel keys database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS channel_keys (
                channel_name TEXT PRIMARY KEY,
                channel_key BLOB NOT NULL
            )
        """)

        conn.commit()
        conn.close()

    def generate_channel_key(self) -> bytes:
        """
        Generate a random symmetric key for a channel.

        Returns:
            32-byte random key
        """
        return os.urandom(KEY_SIZE)

    def encrypt_channel_key_for_user(
        self,
        channel_key: bytes,
        recipient_public_key: bytes
    ) -> Dict[str, str]:
        """
        Encrypt a channel key for a specific user using their public key.

        Args:
            channel_key: The symmetric channel key to encrypt
            recipient_public_key: Recipient's X25519 public key

        Returns:
            Dict with encrypted payload (ephemeral_public_key, ciphertext, nonce)
        """
        # Convert channel key to base64 string for encryption
        channel_key_b64 = base64.b64encode(channel_key).decode('utf-8')

        # Generate ephemeral keypair
        ephemeral_private = X25519PrivateKey.generate()
        ephemeral_public = ephemeral_private.public_key()

        # Perform ECDH
        recipient_public_key_obj = X25519PublicKey.from_public_bytes(recipient_public_key)
        shared_secret = ephemeral_private.exchange(recipient_public_key_obj)

        # Derive encryption key
        encryption_key = MessageEncryptor.derive_message_key(shared_secret, b'channel_key')

        # Encrypt channel key
        encrypted = MessageEncryptor.encrypt_message(channel_key_b64, encryption_key)

        # Add ephemeral public key
        ephemeral_public_bytes = ephemeral_public.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )

        return {
            'ephemeral_public_key': base64.b64encode(ephemeral_public_bytes).decode('utf-8'),
            'ciphertext': encrypted['ciphertext'],
            'nonce': encrypted['nonce']
        }

    def decrypt_channel_key(
        self,
        encrypted_payload: Dict[str, str],
        private_key: X25519PrivateKey
    ) -> bytes:
        """
        Decrypt a channel key using private key.

        Args:
            encrypted_payload: Dict with ephemeral_public_key, ciphertext, nonce
            private_key: User's X25519 private key

        Returns:
            Decrypted channel key (32 bytes)
        """
        # Decode ephemeral public key
        ephemeral_public_bytes = base64.b64decode(encrypted_payload['ephemeral_public_key'])
        ephemeral_public = X25519PublicKey.from_public_bytes(ephemeral_public_bytes)

        # Perform ECDH
        shared_secret = private_key.exchange(ephemeral_public)

        # Derive decryption key
        decryption_key = MessageEncryptor.derive_message_key(shared_secret, b'channel_key')

        # Decrypt channel key
        channel_key_b64 = MessageEncryptor.decrypt_message(
            encrypted_payload['ciphertext'],
            encrypted_payload['nonce'],
            decryption_key
        )

        # Decode from base64
        return base64.b64decode(channel_key_b64)

    def store_channel_key(self, channel_name: str, channel_key: bytes):
        """Store a channel key locally."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute(
                "INSERT OR REPLACE INTO channel_keys (channel_name, channel_key) VALUES (?, ?)",
                (channel_name, channel_key)
            )
            conn.commit()
        finally:
            conn.close()

    def get_channel_key(self, channel_name: str) -> Optional[bytes]:
        """Retrieve a stored channel key."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute(
                "SELECT channel_key FROM channel_keys WHERE channel_name = ?",
                (channel_name,)
            )
            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def delete_channel_key(self, channel_name: str):
        """Delete a channel key (when leaving channel)."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute(
                "DELETE FROM channel_keys WHERE channel_name = ?",
                (channel_name,)
            )
            conn.commit()
        finally:
            conn.close()

    def encrypt_channel_message(self, message: str, channel_key: bytes) -> Dict[str, str]:
        """
        Encrypt a message for a channel using the symmetric channel key.

        Args:
            message: Plaintext message
            channel_key: Channel's symmetric key

        Returns:
            Dict with ciphertext and nonce
        """
        return MessageEncryptor.encrypt_symmetric(message, channel_key)

    def decrypt_channel_message(
        self,
        ciphertext_b64: str,
        nonce_b64: str,
        channel_key: bytes
    ) -> str:
        """
        Decrypt a channel message using the symmetric channel key.

        Args:
            ciphertext_b64: Base64-encoded ciphertext
            nonce_b64: Base64-encoded nonce
            channel_key: Channel's symmetric key

        Returns:
            Decrypted plaintext message
        """
        return MessageEncryptor.decrypt_symmetric(ciphertext_b64, nonce_b64, channel_key)
