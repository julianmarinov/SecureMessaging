"""
File manager for SecureMessaging client.
Handles file upload/download with encryption.
"""

import os
import uuid
import asyncio
from pathlib import Path
from typing import Optional, Callable, Dict
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from client.crypto.file_encryption import FileEncryptor
from client.crypto import KeyManager


class FileManager:
    """Manages encrypted file uploads and downloads."""

    def __init__(self, downloads_dir: str):
        self.downloads_dir = Path(downloads_dir)
        self.downloads_dir.mkdir(parents=True, exist_ok=True)

        # Callbacks for UI updates
        self.on_upload_progress: Optional[Callable] = None
        self.on_download_progress: Optional[Callable] = None
        self.on_file_uploaded: Optional[Callable] = None
        self.on_file_available: Optional[Callable] = None

        # Track active uploads/downloads
        self.pending_uploads: Dict[str, Dict] = {}
        self.available_files: Dict[str, Dict] = {}

    def set_callbacks(
        self,
        on_upload_progress: Optional[Callable] = None,
        on_download_progress: Optional[Callable] = None,
        on_file_uploaded: Optional[Callable] = None,
        on_file_available: Optional[Callable] = None
    ):
        """Set file operation callbacks."""
        if on_upload_progress:
            self.on_upload_progress = on_upload_progress
        if on_download_progress:
            self.on_download_progress = on_download_progress
        if on_file_uploaded:
            self.on_file_uploaded = on_file_uploaded
        if on_file_available:
            self.on_file_available = on_file_available

    async def prepare_file_upload(
        self,
        file_path: str,
        recipient_public_key: Optional[bytes] = None,
        channel_key: Optional[bytes] = None,
        key_manager: Optional[KeyManager] = None
    ) -> Dict:
        """
        Prepare a file for encrypted upload.

        Args:
            file_path: Path to file to upload
            recipient_public_key: For DM files
            channel_key: For channel files
            key_manager: KeyManager instance for generating ephemeral keys

        Returns:
            Dict with file info and encrypted data
        """
        # Generate unique file ID
        file_id = str(uuid.uuid4())

        # Get file info
        file_info = FileEncryptor.get_file_info(file_path)

        # Generate file encryption key
        file_key = FileEncryptor.generate_file_key()

        # Encrypt file
        encrypted_data, file_hash = FileEncryptor.encrypt_file(file_path, file_key)

        # Encrypt file key for recipient(s)
        encrypted_file_key = None

        if recipient_public_key and key_manager:
            # DM file - encrypt file key with recipient's public key
            ephemeral_private, ephemeral_public = key_manager.generate_ephemeral_keypair()

            from cryptography.hazmat.primitives import serialization
            ephemeral_private_bytes = ephemeral_private.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption()
            )
            ephemeral_public_bytes = ephemeral_public.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw
            )

            encrypted_file_key = FileEncryptor.encrypt_file_key_for_recipient(
                file_key,
                ephemeral_private_bytes,
                ephemeral_public_bytes,
                recipient_public_key
            )

        elif channel_key:
            # Channel file - encrypt file key with channel key
            # For simplicity, we'll send the file key encrypted with channel key
            from client.crypto.encryption import MessageEncryptor
            import base64

            file_key_b64 = base64.b64encode(file_key).decode('utf-8')
            encrypted = MessageEncryptor.encrypt_symmetric(file_key_b64, channel_key)

            encrypted_file_key = {
                'ciphertext': encrypted['ciphertext'],
                'nonce': encrypted['nonce']
            }

        # Store upload info
        self.pending_uploads[file_id] = {
            'file_id': file_id,
            'filename': file_info['filename'],
            'size_bytes': file_info['size_bytes'],
            'mime_type': file_info['mime_type'],
            'encrypted_data': encrypted_data,
            'encrypted_file_key': encrypted_file_key,
            'file_hash': file_hash
        }

        return self.pending_uploads[file_id]

    def get_pending_upload(self, file_id: str) -> Optional[Dict]:
        """Get pending upload by file ID."""
        return self.pending_uploads.get(file_id)

    def clear_pending_upload(self, file_id: str):
        """Clear pending upload after successful upload."""
        self.pending_uploads.pop(file_id, None)

    async def handle_file_available(
        self,
        file_id: str,
        sender: str,
        filename: str,
        size_bytes: int,
        mime_type: str,
        encrypted_file_key: Dict,
        file_hash: str,
        recipient: Optional[str] = None,
        channel: Optional[str] = None
    ):
        """Handle file available notification."""
        self.available_files[file_id] = {
            'file_id': file_id,
            'sender': sender,
            'filename': filename,
            'size_bytes': size_bytes,
            'mime_type': mime_type,
            'encrypted_file_key': encrypted_file_key,
            'file_hash': file_hash,
            'recipient': recipient,
            'channel': channel
        }

        # Notify UI
        if self.on_file_available:
            await self.on_file_available(
                file_id=file_id,
                sender=sender,
                filename=filename,
                size_bytes=size_bytes,
                conversation=channel if channel else sender
            )

    async def download_and_decrypt_file(
        self,
        file_id: str,
        encrypted_data: bytes,
        private_key=None,
        channel_key: Optional[bytes] = None
    ) -> Optional[str]:
        """
        Download and decrypt a file.

        Args:
            file_id: File ID
            encrypted_data: Encrypted file data from server
            private_key: User's private key (for DM files)
            channel_key: Channel key (for channel files)

        Returns:
            Path to decrypted file
        """
        if file_id not in self.available_files:
            return None

        file_info = self.available_files[file_id]
        encrypted_file_key = file_info['encrypted_file_key']

        # Decrypt file key
        file_key = None

        if private_key and 'ephemeral_public_key' in encrypted_file_key:
            # DM file - decrypt with private key
            file_key = FileEncryptor.decrypt_file_key(encrypted_file_key, private_key)

        elif channel_key:
            # Channel file - decrypt with channel key
            from client.crypto.encryption import MessageEncryptor
            import base64

            file_key_b64 = MessageEncryptor.decrypt_symmetric(
                encrypted_file_key['ciphertext'],
                encrypted_file_key['nonce'],
                channel_key
            )
            file_key = base64.b64decode(file_key_b64)

        if not file_key:
            raise ValueError("Could not decrypt file key")

        # Verify hash of encrypted data before decryption
        import hashlib
        actual_hash = hashlib.sha256(encrypted_data).hexdigest()
        if actual_hash != file_info['file_hash']:
            raise ValueError("File integrity check failed - data may have been tampered with")

        # Decrypt file
        plaintext = FileEncryptor.decrypt_file(encrypted_data, file_key)

        # Sanitize filename to prevent path traversal
        # Extract only the base filename, stripping any path components
        raw_filename = file_info['filename']
        safe_filename = Path(raw_filename).name  # Strips directory components
        # Remove any remaining dangerous characters
        safe_filename = safe_filename.replace('\x00', '').replace('/', '').replace('\\', '')
        if not safe_filename or safe_filename in ('.', '..'):
            safe_filename = f"download_{file_id}"

        # Save file
        output_path = self.downloads_dir / safe_filename

        # Handle duplicate filenames
        counter = 1
        while output_path.exists():
            stem = Path(safe_filename).stem
            suffix = Path(safe_filename).suffix
            output_path = self.downloads_dir / f"{stem}_{counter}{suffix}"
            counter += 1

        with open(output_path, 'wb') as f:
            f.write(plaintext)

        # Remove from available files (thread-safe)
        self.available_files.pop(file_id, None)

        return str(output_path)

    def get_available_file(self, file_id: str) -> Optional[Dict]:
        """Get info about an available file."""
        return self.available_files.get(file_id)

    def list_available_files(self, conversation: Optional[str] = None) -> list:
        """
        List available files, optionally filtered by conversation.

        Args:
            conversation: Username (DM) or channel name to filter by

        Returns:
            List of file info dicts
        """
        files = []
        for file_info in self.available_files.values():
            if conversation:
                # Filter by conversation
                conv = file_info.get('channel') or file_info.get('sender')
                if conv == conversation:
                    files.append(file_info)
            else:
                files.append(file_info)

        return files
