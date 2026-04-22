"""
Message routing for SecureMessaging server.
Handles routing messages between users and broadcasting to channels.
"""

import asyncio
import logging
import base64
from typing import Dict, Set, Optional, Any
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.protocol import Message, MessageType
from server.storage import ServerStorage

logger = logging.getLogger(__name__)

class MessageRouter:
    """Routes messages between connected clients."""

    def __init__(self, storage: ServerStorage):
        self.storage = storage
        # Map of user_id -> websocket connection
        self.connections: Dict[int, Any] = {}
        # Map of user_id -> username (for quick lookup)
        self.user_sessions: Dict[int, str] = {}
        # Lock for thread-safe connection registry operations
        self._connections_lock = asyncio.Lock()

    async def register_connection(self, user_id: int, username: str, websocket):
        """Register a new WebSocket connection."""
        async with self._connections_lock:
            # Close existing connection if user is already connected
            if user_id in self.connections:
                old_websocket = self.connections[user_id]
                try:
                    await old_websocket.close()
                except Exception:
                    pass  # Ignore errors closing old connection

            self.connections[user_id] = websocket
            self.user_sessions[user_id] = username

        logger.info(f"User {username} (ID: {user_id}) connected")

        # Broadcast user online status
        await self._broadcast_user_status(username, online=True)

    async def unregister_connection(self, user_id: int):
        """Unregister a WebSocket connection."""
        username = None
        async with self._connections_lock:
            if user_id in self.connections:
                username = self.user_sessions.get(user_id, "unknown")
                del self.connections[user_id]
                if user_id in self.user_sessions:
                    del self.user_sessions[user_id]

        if username:
            logger.info(f"User {username} (ID: {user_id}) disconnected")
            # Broadcast user offline status
            await self._broadcast_user_status(username, online=False)

    async def route_message(
        self,
        sender_id: int,
        recipient_username: Optional[str] = None,
        channel_name: Optional[str] = None,
        encrypted_payload: Optional[Dict] = None,  # Dict from JSON
        plaintext: Optional[str] = None
    ) -> Optional[int]:
        """
        Route a message to recipient(s).

        Returns:
            message_id if successful, None otherwise
        """
        recipient_id = None
        channel_id = None

        # Determine destination
        if recipient_username:
            # 1-to-1 message
            recipient_id = self.storage.get_user_id(recipient_username)
            if not recipient_id:
                logger.warning(f"Recipient {recipient_username} not found")
                return None

        elif channel_name:
            # Channel message
            channel_id = self.storage.get_channel_id(channel_name)
            if not channel_id:
                logger.warning(f"Channel {channel_name} not found")
                return None

            # Verify sender is a member
            if not self.storage.is_channel_member(channel_id, sender_id):
                logger.warning(f"User {sender_id} not a member of channel {channel_name}")
                return None

        else:
            logger.error("Message must have either recipient or channel")
            return None

        # Store message in database
        message_id = self.storage.store_message(
            sender_id=sender_id,
            recipient_id=recipient_id,
            channel_id=channel_id,
            encrypted_payload=encrypted_payload,
            plaintext=plaintext
        )

        # Send to connected recipients
        sender_username = self.storage.get_username(sender_id)
        timestamp = datetime.now().timestamp()

        if recipient_id:
            # Send to single recipient
            await self._send_to_user(
                recipient_id,
                MessageType.NEW_MESSAGE,
                message_id=message_id,
                sender=sender_username,
                recipient=recipient_username,
                plaintext=plaintext,
                encrypted_payload=encrypted_payload,
                timestamp=timestamp
            )

        elif channel_id:
            # Broadcast to channel members
            members = self.storage.get_channel_members(channel_id)
            for member_id in members:
                if member_id != sender_id:  # Don't echo back to sender
                    await self._send_to_user(
                        member_id,
                        MessageType.NEW_MESSAGE,
                        message_id=message_id,
                        sender=sender_username,
                        channel=channel_name,
                        plaintext=plaintext,
                        encrypted_payload=encrypted_payload,
                        timestamp=timestamp
                    )

        return message_id

    async def _send_to_user(self, user_id: int, msg_type: str, **data):
        """Send a message to a specific user if connected."""
        if user_id in self.connections:
            websocket = self.connections[user_id]

            # Encode bytes fields to base64 for JSON serialization
            if 'encrypted_payload' in data and isinstance(data['encrypted_payload'], bytes):
                data['encrypted_payload'] = base64.b64encode(data['encrypted_payload']).decode('utf-8')

            message = Message(msg_type, **data)
            try:
                await websocket.send(message.to_json())
                logger.debug(f"Sent {msg_type} to user {user_id}")
            except Exception as e:
                logger.error(f"Error sending to user {user_id}: {e}")

    async def _broadcast_user_status(self, username: str, online: bool):
        """Broadcast user online/offline status to all connected users."""
        message = Message(MessageType.USER_STATUS, username=username, online=online)
        json_msg = message.to_json()

        # Get a snapshot of connections under lock
        async with self._connections_lock:
            connections_snapshot = list(self.connections.items())

        # Send to all connections (outside the lock to avoid blocking)
        for user_id, websocket in connections_snapshot:
            try:
                await asyncio.wait_for(websocket.send(json_msg), timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning(f"Timeout broadcasting status to user {user_id}")
            except Exception as e:
                logger.error(f"Error broadcasting status to user {user_id}: {e}")

    async def broadcast_typing_indicator(
        self,
        sender_id: int,
        recipient_username: Optional[str] = None,
        channel_name: Optional[str] = None
    ):
        """Broadcast typing indicator."""
        sender_username = self.storage.get_username(sender_id)

        if recipient_username:
            # Send to single recipient
            recipient_id = self.storage.get_user_id(recipient_username)
            if recipient_id:
                await self._send_to_user(
                    recipient_id,
                    MessageType.TYPING_INDICATOR,
                    username=sender_username,
                    recipient=recipient_username
                )

        elif channel_name:
            # Broadcast to channel members
            channel_id = self.storage.get_channel_id(channel_name)
            if channel_id:
                members = self.storage.get_channel_members(channel_id)
                for member_id in members:
                    if member_id != sender_id:
                        await self._send_to_user(
                            member_id,
                            MessageType.TYPING_INDICATOR,
                            username=sender_username,
                            channel=channel_name
                        )

    async def send_undelivered_messages(self, user_id: int):
        """Send all undelivered messages to a newly connected user."""
        messages = self.storage.get_undelivered_messages(user_id)
        logger.info(f"Sending {len(messages)} undelivered messages to user {user_id}")

        for msg in messages:
            # Safely get channel name - handle case where channel may have been deleted
            channel_name = None
            if msg['channel_id']:
                channel_info = self.storage.get_channel_info(msg['channel_id'])
                if channel_info:
                    channel_name = channel_info['channel_name']
                else:
                    # Channel was deleted, skip this message
                    logger.warning(f"Skipping message {msg['message_id']} - channel {msg['channel_id']} no longer exists")
                    self.storage.mark_message_delivered(msg['message_id'])
                    continue

            await self._send_to_user(
                user_id,
                MessageType.NEW_MESSAGE,
                message_id=msg['message_id'],
                sender=msg['sender'],
                recipient=self.storage.get_username(user_id) if msg['recipient_id'] else None,
                channel=channel_name,
                plaintext=msg.get('plaintext'),
                encrypted_payload=msg.get('encrypted_payload'),
                timestamp=msg['timestamp']
            )

            # Mark as delivered
            self.storage.mark_message_delivered(msg['message_id'])

    def get_online_users(self) -> list:
        """Get list of currently connected usernames."""
        return list(self.user_sessions.values())

    def is_user_online(self, username: str) -> bool:
        """Check if a user is currently connected."""
        user_id = self.storage.get_user_id(username)
        return user_id in self.connections if user_id else False
