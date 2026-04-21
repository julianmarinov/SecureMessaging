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
                            self.router.register_connection(user_id, username, websocket)

                            # Send undelivered messages
                            await self.router.send_undelivered_messages(user_id)

                    elif msg_type == MessageType.SEND_MESSAGE:
                        await self._handle_send_message(websocket, message, user_id)

                    elif msg_type == MessageType.MESSAGE_DELIVERED:
                        await self._handle_message_delivered(message)

                    elif msg_type == MessageType.MESSAGE_READ:
                        await self._handle_message_read(message)

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
                        await self._handle_download_file(websocket, message)

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
                self.router.unregister_connection(user_id)

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

    async def _handle_message_delivered(self, message):
        """Handle message delivered confirmation."""
        message_id = message.get('message_id')
        if message_id:
            self.storage.mark_message_delivered(message_id)
            logger.debug(f"Message {message_id} marked as delivered")

    async def _handle_message_read(self, message):
        """Handle message read confirmation."""
        message_id = message.get('message_id')
        if message_id:
            self.storage.mark_message_read(message_id)
            logger.debug(f"Message {message_id} marked as read")

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

    async def _handle_create_channel(self, websocket, message, user_id: int):
        """Handle channel creation request."""
        channel_name = message.get('channel_name')
        encrypted_channel_key = message.get('encrypted_channel_key')  # Creator's encrypted copy

        if not channel_name:
            await self._send_error(websocket, "Channel name required")
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

    async def _handle_download_file(self, websocket, message):
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
