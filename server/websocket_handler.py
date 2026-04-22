"""
WebSocket connection handler for SecureMessaging server.
Processes incoming messages and manages individual client connections.
"""

import asyncio
import logging
import base64
from typing import Optional
import websockets

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.protocol import Message, MessageType
from server.auth import AuthManager
from server.storage import ServerStorage
from server.router import MessageRouter

logger = logging.getLogger(__name__)

class WebSocketHandler:
    """Handles individual WebSocket connections."""

    def __init__(
        self,
        auth_manager: AuthManager,
        storage: ServerStorage,
        router: MessageRouter
    ):
        self.auth_manager = auth_manager
        self.storage = storage
        self.router = router

    async def handle_connection(self, websocket):
        """Handle a WebSocket connection."""
        user_id: Optional[int] = None
        username: Optional[str] = None
        authenticated = False

        try:
            logger.info(f"New connection from {websocket.remote_address}")

            async for raw_message in websocket:
                try:
                    message = Message.from_json(raw_message)
                    msg_type = message.type

                    # Authentication required for most operations
                    if not authenticated and msg_type != MessageType.AUTHENTICATE:
                        await self._send_error(websocket, "Authentication required")
                        continue

                    # Route message to appropriate handler
                    if msg_type == MessageType.AUTHENTICATE:
                        user_id, username, authenticated = await self._handle_authenticate(
                            websocket, message
                        )
                        if authenticated:
                            # Register connection with router
                            await self.router.register_connection(user_id, username, websocket)

                            # Send undelivered messages
                            await self.router.send_undelivered_messages(user_id)

                    elif msg_type == MessageType.SEND_MESSAGE:
                        await self._handle_send_message(websocket, message, user_id)

                    elif msg_type == MessageType.MESSAGE_DELIVERED:
                        await self._handle_message_delivered(message, user_id)

                    elif msg_type == MessageType.MESSAGE_READ:
                        await self._handle_message_read(message, user_id)

                    elif msg_type == MessageType.REQUEST_PUBLIC_KEY:
                        await self._handle_request_public_key(websocket, message)

                    elif msg_type == MessageType.CREATE_CHANNEL:
                        await self._handle_create_channel(websocket, message, user_id)

                    elif msg_type == MessageType.JOIN_CHANNEL:
                        await self._handle_join_channel(websocket, message, user_id)

                    elif msg_type == MessageType.LIST_CHANNELS:
                        await self._handle_list_channels(websocket)

                    elif msg_type == MessageType.LIST_USERS:
                        await self._handle_list_users(websocket)

                    elif msg_type == MessageType.TYPING:
                        await self._handle_typing(message, user_id)

                    elif msg_type == MessageType.UPLOAD_FILE:
                        await self._handle_upload_file(websocket, message, user_id)

                    elif msg_type == MessageType.DOWNLOAD_FILE:
                        await self._handle_download_file(websocket, message, user_id)

                    elif msg_type == MessageType.PING:
                        await websocket.send(Message(MessageType.PONG).to_json())

                    else:
                        await self._send_error(websocket, f"Unknown message type: {msg_type}")

                except Exception as e:
                    logger.error(f"Error processing message: {e}", exc_info=True)
                    await self._send_error(websocket, "Error processing message")

        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Connection closed for user {username}")

        finally:
            # Unregister connection
            if user_id:
                await self.router.unregister_connection(user_id)

    async def _handle_authenticate(self, websocket, message) -> tuple:
        """Handle authentication request."""
        username = message.get('username')
        password = message.get('password')

        if not username or not password:
            await self._send_error(websocket, "Username and password required", MessageType.AUTH_ERROR)
            return None, None, False

        # Verify credentials
        success, user_id, error = self.auth_manager.verify_password(username, password)

        if not success:
            await self._send_error(websocket, error or "Authentication failed", MessageType.AUTH_ERROR)
            return None, None, False

        # Create session
        token = self.auth_manager.create_session(user_id)

        # Send success response
        response = Message(
            MessageType.AUTHENTICATED,
            token=token,
            user_id=user_id,
            username=username
        )
        await websocket.send(response.to_json())

        logger.info(f"User {username} authenticated successfully")
        return user_id, username, True

    async def _handle_send_message(self, websocket, message, sender_id: int):
        """Handle send message request."""
        recipient = message.get('recipient')
        channel = message.get('channel')
        plaintext = message.get('plaintext')
        encrypted_payload = message.get('encrypted_payload')

        # Route the message
        message_id = await self.router.route_message(
            sender_id=sender_id,
            recipient_username=recipient,
            channel_name=channel,
            plaintext=plaintext,
            encrypted_payload=encrypted_payload
        )

        if message_id:
            # Send confirmation to sender
            response = Message(
                MessageType.MESSAGE_DELIVERED,
                message_id=message_id
            )
            await websocket.send(response.to_json())
        else:
            await self._send_error(websocket, "Failed to send message")

    async def _handle_message_delivered(self, message, user_id: int):
        """Handle message delivered confirmation."""
        message_id = message.get('message_id')
        if message_id:
            if self.storage.mark_message_delivered(message_id, user_id):
                logger.debug(f"Message {message_id} marked as delivered by user {user_id}")
            else:
                logger.warning(f"User {user_id} tried to mark message {message_id} as delivered but is not authorized")

    async def _handle_message_read(self, message, user_id: int):
        """Handle message read confirmation."""
        message_id = message.get('message_id')
        if message_id:
            if self.storage.mark_message_read(message_id, user_id):
                logger.debug(f"Message {message_id} marked as read by user {user_id}")
            else:
                logger.warning(f"User {user_id} tried to mark message {message_id} as read but is not authorized")

    async def _handle_request_public_key(self, websocket, message):
        """Handle public key request."""
        username = message.get('username')
        if not username:
            await self._send_error(websocket, "Username required")
            return

        public_key = self.storage.get_public_key(username)
        if public_key:
            # Encode public key as base64 for JSON transmission
            public_key_b64 = base64.b64encode(public_key).decode('utf-8')
            response = Message(
                MessageType.PUBLIC_KEY_RESPONSE,
                username=username,
                public_key=public_key_b64
            )
            await websocket.send(response.to_json())
        else:
            await self._send_error(websocket, f"User {username} not found")

    def _validate_channel_name(self, channel_name: str) -> tuple:
        """
        Validate channel name format.

        Returns:
            (is_valid, error_message)
        """
        if not channel_name:
            return False, "Channel name required"
        if len(channel_name) < 2:
            return False, "Channel name must be at least 2 characters"
        if len(channel_name) > 50:
            return False, "Channel name must be 50 characters or less"
        # Allow alphanumeric, hyphens, underscores
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', channel_name):
            return False, "Channel name can only contain letters, numbers, hyphens, and underscores"
        return True, None

    async def _handle_create_channel(self, websocket, message, user_id: int):
        """Handle channel creation request."""
        channel_name = message.get('channel_name')
        encrypted_channel_key = message.get('encrypted_channel_key')  # Creator's encrypted copy

        # Validate channel name
        is_valid, error = self._validate_channel_name(channel_name)
        if not is_valid:
            await self._send_error(websocket, error)
            return

        if not encrypted_channel_key:
            await self._send_error(websocket, "Encrypted channel key required")
            return

        channel_id = self.storage.create_channel(channel_name, user_id)
        if channel_id:
            # Auto-join creator to channel with their encrypted key
            encrypted_key_bytes = base64.b64decode(encrypted_channel_key)
            self.storage.add_channel_member(channel_id, user_id, encrypted_key_bytes)

            response = Message(
                MessageType.CHANNEL_CREATED,
                channel_id=channel_id,
                channel_name=channel_name
            )
            await websocket.send(response.to_json())
            logger.info(f"Channel '{channel_name}' created by user {user_id}")
        else:
            await self._send_error(websocket, "Channel already exists or creation failed")

    async def _handle_join_channel(self, websocket, message, user_id: int):
        """Handle join channel request."""
        channel_name = message.get('channel_name')
        encrypted_channel_key = message.get('encrypted_channel_key')  # Joining user's encrypted copy

        if not channel_name:
            await self._send_error(websocket, "Channel name required")
            return

        if not encrypted_channel_key:
            await self._send_error(websocket, "Encrypted channel key required")
            return

        channel_id = self.storage.get_channel_id(channel_name)
        if not channel_id:
            await self._send_error(websocket, "Channel not found")
            return

        # Add user to channel
        encrypted_key_bytes = base64.b64decode(encrypted_channel_key)
        success = self.storage.add_channel_member(channel_id, user_id, encrypted_key_bytes)

        if success:
            response = Message(
                MessageType.CHANNEL_JOINED,
                channel_id=channel_id,
                channel_name=channel_name
            )
            await websocket.send(response.to_json())
            logger.info(f"User {user_id} joined channel '{channel_name}'")
        else:
            await self._send_error(websocket, "Already a member or join failed")

    async def _handle_list_channels(self, websocket):
        """Handle list channels request."""
        channels = self.storage.list_all_channels()
        response = Message(
            MessageType.CHANNELS_LIST,
            channels=channels
        )
        await websocket.send(response.to_json())

    async def _handle_list_users(self, websocket):
        """Handle list online users request."""
        online_users = self.router.get_online_users()
        response = Message(
            MessageType.USERS_LIST,
            users=online_users
        )
        await websocket.send(response.to_json())

    async def _handle_typing(self, message, sender_id: int):
        """Handle typing indicator."""
        recipient = message.get('recipient')
        channel = message.get('channel')

        await self.router.broadcast_typing_indicator(
            sender_id=sender_id,
            recipient_username=recipient,
            channel_name=channel
        )

    async def _send_error(self, websocket, error: str, msg_type: str = MessageType.ERROR):
        """Send error message to client."""
        response = Message(msg_type, error=error)
        try:
            await websocket.send(response.to_json())
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")

    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename to prevent path traversal and other attacks.

        Returns:
            Sanitized filename
        """
        import re
        from pathlib import Path

        if not filename:
            return "unnamed_file"

        # Extract just the filename, removing any path components
        safe_name = Path(filename).name

        # Remove null bytes and other dangerous characters
        safe_name = safe_name.replace('\x00', '').replace('/', '').replace('\\', '')

        # Remove or replace other potentially dangerous characters
        safe_name = re.sub(r'[<>:"|?*]', '_', safe_name)

        # Limit length
        if len(safe_name) > 255:
            # Keep extension if present
            parts = safe_name.rsplit('.', 1)
            if len(parts) == 2 and len(parts[1]) < 20:
                safe_name = parts[0][:255 - len(parts[1]) - 1] + '.' + parts[1]
            else:
                safe_name = safe_name[:255]

        # Ensure it's not empty or a dot-file
        if not safe_name or safe_name in ('.', '..') or safe_name.startswith('.'):
            safe_name = "file_" + safe_name.lstrip('.')

        return safe_name

    async def _handle_upload_file(self, websocket, message, uploader_id: int):
        """Handle file upload request."""
        file_id = message.get('file_id')
        filename = message.get('filename')
        size_bytes = message.get('size_bytes')
        mime_type = message.get('mime_type')
        encrypted_data = message.get('encrypted_data')
        encrypted_file_key = message.get('encrypted_file_key')
        file_hash = message.get('file_hash')
        recipient = message.get('recipient')
        channel = message.get('channel')

        if not all([file_id, filename, encrypted_data]):
            await self._send_error(websocket, "Missing required file data")
            return

        # Sanitize filename to prevent path traversal
        filename = self._sanitize_filename(filename)

        # Verify channel membership if uploading to a channel
        if channel:
            channel_id = self.storage.get_channel_id(channel)
            if not channel_id:
                await self._send_error(websocket, "Channel not found")
                return
            if not self.storage.is_channel_member(channel_id, uploader_id):
                await self._send_error(websocket, "Not a member of this channel")
                logger.warning(f"User {uploader_id} tried to upload file to channel {channel} without membership")
                return

        # Decode encrypted data from base64
        encrypted_data_bytes = base64.b64decode(encrypted_data)

        # Store file in database
        success = self.storage.store_file(
            file_id=file_id,
            uploader_id=uploader_id,
            encrypted_data=encrypted_data_bytes,
            filename_hint=filename,
            size_bytes=size_bytes
        )

        if not success:
            await self._send_error(websocket, "Failed to store file")
            return

        # Send confirmation to uploader
        response = Message(MessageType.FILE_UPLOADED, file_id=file_id)
        await websocket.send(response.to_json())

        # Notify recipient(s) that file is available
        uploader_username = self.storage.get_username(uploader_id)

        if recipient:
            # Direct message file
            recipient_id = self.storage.get_user_id(recipient)
            if recipient_id:
                # Grant file access to recipient
                self.storage.grant_file_access(file_id, recipient_id)
                await self.router._send_to_user(
                    recipient_id,
                    MessageType.FILE_AVAILABLE,
                    file_id=file_id,
                    sender=uploader_username,
                    recipient=recipient,
                    filename=filename,
                    size_bytes=size_bytes,
                    mime_type=mime_type,
                    encrypted_file_key=encrypted_file_key,
                    file_hash=file_hash
                )

        elif channel:
            # Channel file
            channel_id = self.storage.get_channel_id(channel)
            if channel_id:
                members = self.storage.get_channel_members(channel_id)
                for member_id in members:
                    if member_id != uploader_id:  # Don't send to uploader
                        # Grant file access to channel member
                        self.storage.grant_file_access(file_id, member_id)
                        await self.router._send_to_user(
                            member_id,
                            MessageType.FILE_AVAILABLE,
                            file_id=file_id,
                            sender=uploader_username,
                            channel=channel,
                            filename=filename,
                            size_bytes=size_bytes,
                            mime_type=mime_type,
                            encrypted_file_key=encrypted_file_key,
                            file_hash=file_hash
                        )

        logger.info(f"File {file_id} uploaded by user {uploader_id}")

    async def _handle_download_file(self, websocket, message, user_id: int):
        """Handle file download request."""
        file_id = message.get('file_id')

        if not file_id:
            await self._send_error(websocket, "File ID required")
            return

        # Retrieve file from database
        file_data = self.storage.get_file(file_id)

        if not file_data:
            await self._send_error(websocket, "File not found")
            return

        # Authorization check: verify user is allowed to download this file
        # User must be either the uploader or an intended recipient
        if not self.storage.is_file_accessible(file_id, user_id):
            await self._send_error(websocket, "Not authorized to download this file")
            logger.warning(f"Unauthorized file download attempt: user {user_id} tried to download file {file_id}")
            return

        # Encode encrypted data as base64
        encrypted_data_b64 = base64.b64encode(file_data['encrypted_data']).decode('utf-8')

        # Send file data
        response = Message(
            MessageType.FILE_DATA,
            file_id=file_id,
            encrypted_data=encrypted_data_b64
        )
        await websocket.send(response.to_json())

        logger.info(f"File {file_id} downloaded")
