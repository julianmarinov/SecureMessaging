"""
File encryption/decryption for SecureMessaging.
Handles encrypted file uploads and downloads.
"""

import os
import base64
from typing import Dict, Tuple
from pathlib import Path
import hashlib

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from shared.constants import KEY_SIZE, NONCE_SIZE


class FileEncryptor:
    """Handles file encryption and decryption."""

    @staticmethod
    def generate_file_key() -> bytes:
        """
        Generate a random symmetric key for file encryption.

        Returns:
            32-byte random key
        """
        return os.urandom(KEY_SIZE)

    @staticmethod
    def encrypt_file(file_path: str, file_key: bytes) -> Tuple[bytes, str]:
        """
        Encrypt a file using ChaCha20-Poly1305.

        Args:
            file_path: Path to file to encrypt
            file_key: 32-byte encryption key

        Returns:
            Tuple of (encrypted_data, file_hash)
        """
        # Read file
        with open(file_path, 'rb') as f:
            plaintext = f.read()

        # Generate nonce
        nonce = os.urandom(NONCE_SIZE)

        # Encrypt file
        cipher = ChaCha20Poly1305(file_key)
        ciphertext = cipher.encrypt(nonce, plaintext, None)

        # Prepend nonce to ciphertext
        encrypted_data = nonce + ciphertext

        # Calculate hash of original file for integrity
        file_hash = hashlib.sha256(plaintext).hexdigest()

        return encrypted_data, file_hash

    @staticmethod
    def decrypt_file(encrypted_data: bytes, file_key: bytes) -> bytes:
        """
        Decrypt a file using ChaCha20-Poly1305.

        Args:
            encrypted_data: Encrypted file data (nonce + ciphertext)
            file_key: 32-byte decryption key

        Returns:
            Decrypted file data

        Raises:
            cryptography.exceptions.InvalidTag: If authentication fails
        """
        # Extract nonce and ciphertext
        nonce = encrypted_data[:NONCE_SIZE]
        ciphertext = encrypted_data[NONCE_SIZE:]

        # Decrypt file
        cipher = ChaCha20Poly1305(file_key)
        plaintext = cipher.decrypt(nonce, ciphertext, None)

        return plaintext

    @staticmethod
    def encrypt_file_key_for_recipient(
        file_key: bytes,
        ephemeral_private: bytes,
        ephemeral_public: bytes,
        recipient_public_key: bytes
    ) -> Dict[str, str]:
        """
        Encrypt file key for a recipient using ECDH.

        Args:
            file_key: The symmetric file key to encrypt
            ephemeral_private: Ephemeral private key for ECDH
            ephemeral_public: Ephemeral public key for ECDH
            recipient_public_key: Recipient's X25519 public key

        Returns:
            Dict with encrypted file key info
        """
        from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
        from cryptography.hazmat.primitives import serialization

        # Reconstruct key objects
        eph_priv = X25519PrivateKey.from_private_bytes(ephemeral_private)
        recipient_pub = X25519PublicKey.from_public_bytes(recipient_public_key)

        # Perform ECDH
        shared_secret = eph_priv.exchange(recipient_pub)

        # Derive encryption key
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=KEY_SIZE,
            salt=None,
            info=b'file_key',
        )
        encryption_key = hkdf.derive(shared_secret)

        # Encrypt file key
        file_key_b64 = base64.b64encode(file_key).decode('utf-8')
        nonce = os.urandom(NONCE_SIZE)
        cipher = ChaCha20Poly1305(encryption_key)
        ciphertext = cipher.encrypt(nonce, file_key_b64.encode('utf-8'), None)

        return {
            'ephemeral_public_key': base64.b64encode(ephemeral_public).decode('utf-8'),
            'ciphertext': base64.b64encode(ciphertext).decode('utf-8'),
            'nonce': base64.b64encode(nonce).decode('utf-8')
        }

    @staticmethod
    def decrypt_file_key(
        encrypted_file_key: Dict[str, str],
        private_key
    ) -> bytes:
        """
        Decrypt a file key using private key.

        Args:
            encrypted_file_key: Dict with ephemeral_public_key, ciphertext, nonce
            private_key: User's X25519 private key

        Returns:
            Decrypted file key (32 bytes)
        """
        from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey

        # Decode ephemeral public key
        ephemeral_public_bytes = base64.b64decode(encrypted_file_key['ephemeral_public_key'])
        ephemeral_public = X25519PublicKey.from_public_bytes(ephemeral_public_bytes)

        # Perform ECDH
        shared_secret = private_key.exchange(ephemeral_public)

        # Derive decryption key
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=KEY_SIZE,
            salt=None,
            info=b'file_key',
        )
        decryption_key = hkdf.derive(shared_secret)

        # Decrypt file key
        ciphertext = base64.b64decode(encrypted_file_key['ciphertext'])
        nonce = base64.b64decode(encrypted_file_key['nonce'])
        cipher = ChaCha20Poly1305(decryption_key)
        file_key_b64 = cipher.decrypt(nonce, ciphertext, None)

        # Decode from base64
        return base64.b64decode(file_key_b64.decode('utf-8'))

    @staticmethod
    def get_file_info(file_path: str) -> Dict[str, any]:
        """
        Get file metadata.

        Args:
            file_path: Path to file

        Returns:
            Dict with filename, size, extension
        """
        path = Path(file_path)
        stat = path.stat()

        return {
            'filename': path.name,
            'size_bytes': stat.st_size,
            'extension': path.suffix,
            'mime_type': FileEncryptor._guess_mime_type(path.suffix)
        }

    @staticmethod
    def _guess_mime_type(extension: str) -> str:
        """Guess MIME type from file extension."""
        mime_types = {
            '.txt': 'text/plain',
            '.pdf': 'application/pdf',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.zip': 'application/zip',
            '.mp4': 'video/mp4',
            '.mp3': 'audio/mpeg',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        }
        return mime_types.get(extension.lower(), 'application/octet-stream')

    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """Format file size in human-readable format."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
