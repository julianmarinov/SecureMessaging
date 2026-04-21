"""
ECDH key exchange for SecureMessaging.
Implements X25519 key exchange with Perfect Forward Secrecy.
"""

import base64
from typing import Dict, Tuple
from cryptography.hazmat.primitives.asymmetric import x25519

from .encryption import MessageEncryptor

class ECDHKeyExchange:
    """Handles Elliptic Curve Diffie-Hellman key exchange."""

    @staticmethod
    def perform_sender_exchange(
        recipient_public_key: bytes,
        ephemeral_private_key: x25519.X25519PrivateKey
    ) -> Tuple[bytes, bytes]:
        """
        Perform ECDH as sender (encrypt).

        Args:
            recipient_public_key: Recipient's identity public key (raw bytes)
            ephemeral_private_key: Sender's ephemeral private key

        Returns:
            (shared_secret, ephemeral_public_key_bytes)
        """
        # Load recipient's public key
        recipient_key = x25519.X25519PublicKey.from_public_bytes(recipient_public_key)

        # Perform ECDH: shared_secret = ephemeral_private * recipient_public
        shared_secret = ephemeral_private_key.exchange(recipient_key)

        # Get ephemeral public key to send
        ephemeral_public_key = ephemeral_private_key.public_key()
        ephemeral_public_bytes = ephemeral_public_key.public_bytes_raw()

        return shared_secret, ephemeral_public_bytes

    @staticmethod
    def perform_recipient_exchange(
        ephemeral_public_key: bytes,
        identity_private_key: x25519.X25519PrivateKey
    ) -> bytes:
        """
        Perform ECDH as recipient (decrypt).

        Args:
            ephemeral_public_key: Sender's ephemeral public key (raw bytes)
            identity_private_key: Recipient's identity private key

        Returns:
            shared_secret
        """
        # Load sender's ephemeral public key
        ephemeral_key = x25519.X25519PublicKey.from_public_bytes(ephemeral_public_key)

        # Perform ECDH: shared_secret = identity_private * ephemeral_public
        shared_secret = identity_private_key.exchange(ephemeral_key)

        return shared_secret

    @staticmethod
    def encrypt_for_recipient(
        message: str,
        recipient_public_key: bytes,
        ephemeral_private_key: x25519.X25519PrivateKey
    ) -> Dict[str, str]:
        """
        Encrypt a message for a recipient using ECDH + ChaCha20-Poly1305.

        Args:
            message: Plaintext message
            recipient_public_key: Recipient's public key (raw bytes)
            ephemeral_private_key: Ephemeral private key for this message

        Returns:
            Dict with 'ephemeral_public_key', 'ciphertext', 'nonce' (all base64)
        """
        # Perform ECDH
        shared_secret, ephemeral_public_bytes = ECDHKeyExchange.perform_sender_exchange(
            recipient_public_key,
            ephemeral_private_key
        )

        # Derive encryption key from shared secret
        encryption_key = MessageEncryptor.derive_message_key(shared_secret)

        # Encrypt message
        encrypted = MessageEncryptor.encrypt_message(message, encryption_key)

        # Add ephemeral public key
        encrypted['ephemeral_public_key'] = base64.b64encode(ephemeral_public_bytes).decode('utf-8')

        return encrypted

    @staticmethod
    def decrypt_from_sender(
        encrypted_payload: Dict[str, str],
        identity_private_key: x25519.X25519PrivateKey
    ) -> str:
        """
        Decrypt a message from a sender using ECDH + ChaCha20-Poly1305.

        Args:
            encrypted_payload: Dict with 'ephemeral_public_key', 'ciphertext', 'nonce'
            identity_private_key: Recipient's identity private key

        Returns:
            Decrypted plaintext message

        Raises:
            cryptography.exceptions.InvalidTag: If authentication fails
        """
        # Extract ephemeral public key
        ephemeral_public_bytes = base64.b64decode(encrypted_payload['ephemeral_public_key'])

        # Perform ECDH
        shared_secret = ECDHKeyExchange.perform_recipient_exchange(
            ephemeral_public_bytes,
            identity_private_key
        )

        # Derive decryption key
        decryption_key = MessageEncryptor.derive_message_key(shared_secret)

        # Decrypt message
        plaintext = MessageEncryptor.decrypt_message(
            encrypted_payload['ciphertext'],
            encrypted_payload['nonce'],
            decryption_key
        )

        return plaintext

    @staticmethod
    def encrypt_channel_key_for_member(
        channel_key: bytes,
        member_public_key: bytes,
        ephemeral_private_key: x25519.X25519PrivateKey
    ) -> Dict[str, str]:
        """
        Encrypt a channel's symmetric key for a member.

        Args:
            channel_key: Channel's symmetric encryption key
            member_public_key: Member's public key
            ephemeral_private_key: Ephemeral key for this encryption

        Returns:
            Encrypted channel key payload
        """
        # Encode channel key as base64 string for encryption
        channel_key_str = base64.b64encode(channel_key).decode('utf-8')

        return ECDHKeyExchange.encrypt_for_recipient(
            channel_key_str,
            member_public_key,
            ephemeral_private_key
        )

    @staticmethod
    def decrypt_channel_key(
        encrypted_payload: Dict[str, str],
        identity_private_key: x25519.X25519PrivateKey
    ) -> bytes:
        """
        Decrypt a channel's symmetric key.

        Args:
            encrypted_payload: Encrypted channel key
            identity_private_key: Member's private key

        Returns:
            Channel symmetric key (32 bytes)
        """
        # Decrypt to get base64 string
        channel_key_str = ECDHKeyExchange.decrypt_from_sender(
            encrypted_payload,
            identity_private_key
        )

        # Decode from base64
        return base64.b64decode(channel_key_str)
