"""
Message encryption/decryption using ChaCha20-Poly1305 AEAD.
"""

import os
import base64
from typing import Dict, Tuple
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.constants import KEY_SIZE, NONCE_SIZE

class MessageEncryptor:
    """Handles message encryption and decryption."""

    @staticmethod
    def derive_message_key(shared_secret: bytes, context: bytes = b'message') -> bytes:
        """
        Derive message encryption key from shared secret using HKDF.

        Args:
            shared_secret: Shared secret from ECDH
            context: Context info for key derivation

        Returns:
            32-byte encryption key
        """
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=KEY_SIZE,
            salt=None,  # ECDH output is already uniform
            info=context,
        )
        return hkdf.derive(shared_secret)

    @staticmethod
    def encrypt_message(message: str, encryption_key: bytes) -> Dict[str, str]:
        """
        Encrypt a message using ChaCha20-Poly1305.

        Args:
            message: Plaintext message
            encryption_key: 32-byte encryption key

        Returns:
            Dict with 'ciphertext' and 'nonce' (base64 encoded)
        """
        # Generate random nonce
        nonce = os.urandom(NONCE_SIZE)

        # Encrypt with ChaCha20-Poly1305 (AEAD - includes authentication)
        cipher = ChaCha20Poly1305(encryption_key)
        ciphertext = cipher.encrypt(nonce, message.encode('utf-8'), None)

        # Return base64-encoded values for JSON transmission
        return {
            'ciphertext': base64.b64encode(ciphertext).decode('utf-8'),
            'nonce': base64.b64encode(nonce).decode('utf-8')
        }

    @staticmethod
    def decrypt_message(ciphertext_b64: str, nonce_b64: str, decryption_key: bytes) -> str:
        """
        Decrypt a message using ChaCha20-Poly1305.

        Args:
            ciphertext_b64: Base64-encoded ciphertext
            nonce_b64: Base64-encoded nonce
            decryption_key: 32-byte decryption key

        Returns:
            Decrypted plaintext message

        Raises:
            cryptography.exceptions.InvalidTag: If authentication fails
        """
        # Decode from base64
        ciphertext = base64.b64decode(ciphertext_b64)
        nonce = base64.b64decode(nonce_b64)

        # Decrypt and verify
        cipher = ChaCha20Poly1305(decryption_key)
        plaintext_bytes = cipher.decrypt(nonce, ciphertext, None)

        return plaintext_bytes.decode('utf-8')

    @staticmethod
    def encrypt_symmetric(message: str, key: bytes) -> Dict[str, str]:
        """
        Encrypt a message with a symmetric key (for group channels).

        Args:
            message: Plaintext message
            key: 32-byte symmetric key

        Returns:
            Dict with 'ciphertext' and 'nonce' (base64 encoded)
        """
        return MessageEncryptor.encrypt_message(message, key)

    @staticmethod
    def decrypt_symmetric(ciphertext_b64: str, nonce_b64: str, key: bytes) -> str:
        """
        Decrypt a message with a symmetric key (for group channels).

        Args:
            ciphertext_b64: Base64-encoded ciphertext
            nonce_b64: Base64-encoded nonce
            key: 32-byte symmetric key

        Returns:
            Decrypted plaintext message
        """
        return MessageEncryptor.decrypt_message(ciphertext_b64, nonce_b64, key)

    @staticmethod
    def generate_channel_key() -> bytes:
        """
        Generate a random symmetric key for a channel.

        Returns:
            32-byte random key
        """
        return os.urandom(KEY_SIZE)
