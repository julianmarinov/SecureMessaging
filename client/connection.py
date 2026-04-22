"""
WebSocket connection manager for SecureMessaging client.
Handles connection, authentication, and message routing.
"""

import asyncio
import base64
import json
import logging
from typing import Optional, Callable, Dict, Any
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

import websockets
from shared.protocol import Message, MessageType
from client.crypto import KeyManager, MessageEncryptor, ECDHKeyExchange, ChannelKeyManager
from client.file_manager import FileManager

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connection and message handling."""

    def __init__(self, server_url: str, username: str, password: str):
        self.server_url = server_url
        self.username = username
        self.password = password
        self.websocket = None
        self.authenticated = False
        self.token = None
        self.running = False

        # Key management
        db_path = Path(__file__).parent.parent / "data" / "client" / f"{username}.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.key_manager = KeyManager(str(db_path))
        self.channel_key_manager = ChannelKeyManager(str(db_path))
        self.private_key = None

        # File management
        downloads_dir = Path(__file__).parent.parent / "data" / "client" / "downloads" / username
        self.file_manager = FileManager(str(downloads_dir))

        # Message callbacks
        self.on_message_callback: Optional[Callable] = None
        self.on_status_callback: Optional[Callable] = None
        self.on_typing_callback: Optional[Callable] = None
        self.on_error_callback: Optional[Callable] = None
        self.on_channel_created_callback: Optional[Callable] = None
        self.on_channel_joined_callback: Optional[Callable] = None
        self.on_file_available_callback: Optional[Callable] = None
        self.on_channels_list_callback: Optional[Callable] = None
        self.on_message_delivered_callback: Optional[Callable] = None
        self.on_users_list_callback: Optional[Callable] = None

        # Background tasks
        self.receiver_task = None

        # Public key request tracking
        self.pending_key_requests = {}  # {username: asyncio.Future}

        # Reconnection settings
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 10
        self._reconnect_delay = 1.0  # Initial delay in seconds
        self._max_reconnect_delay = 60.0  # Maximum delay
        self._should_reconnect = True
        self._reconnecting = False

    async def _safe_send(self, message: str, timeout: float = 10.0) -> bool:
        """
        Safely send a message over websocket with null check and timeout.

        Args:
            message: JSON message to send
            timeout: Maximum time to wait for send

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.websocket or not self.running:
            return False

        try:
            await asyncio.wait_for(self.websocket.send(message), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            if self.on_error_callback:
                await self.on_error_callback("Send timeout - server not responding")
            return False
        except Exception as e:
            if self.on_error_callback:
                await self.on_error_callback(f"Send error: {str(e)}")
            return False

    def set_callbacks(
        self,
        on_message: Optional[Callable] = None,
        on_status: Optional[Callable] = None,
        on_typing: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
        on_channel_created: Optional[Callable] = None,
        on_channel_joined: Optional[Callable] = None,
        on_file_available: Optional[Callable] = None,
        on_channels_list: Optional[Callable] = None,
        on_message_delivered: Optional[Callable] = None,
        on_users_list: Optional[Callable] = None
    ):
        """Set event callbacks for the UI."""
        if on_message:
            self.on_message_callback = on_message
        if on_status:
            self.on_status_callback = on_status
        if on_typing:
            self.on_typing_callback = on_typing
        if on_error:
            self.on_error_callback = on_error
        if on_channel_created:
            self.on_channel_created_callback = on_channel_created
        if on_channel_joined:
            self.on_channel_joined_callback = on_channel_joined
        if on_file_available:
            self.on_file_available_callback = on_file_available
        if on_channels_list:
            self.on_channels_list_callback = on_channels_list
        if on_message_delivered:
            self.on_message_delivered_callback = on_message_delivered
        if on_users_list:
            self.on_users_list_callback = on_users_list

    async def initialize_keys(self) -> bool:
        """Initialize or load encryption keys."""
        if not self.key_manager.has_identity_key():
            # Generate new keypair
            public_key, private_key = self.key_manager.generate_identity_keypair(self.password)
            # Keys just generated, reconstruct private key object
            from cryptography.hazmat.primitives.asymmetric import x25519
            self.private_key = x25519.X25519PrivateKey.from_private_bytes(private_key)
            return True

        # Load existing private key
        self.private_key = self.key_manager.load_private_key(self.password)
        if self.private_key is None:
            # Wrong password - delete corrupted keys to allow retry
            import os
            if os.path.exists(self.key_manager.db_path):
                os.remove(self.key_manager.db_path)
            return False
        return True

    async def connect(self) -> bool:
        """Connect to the server and authenticate."""
        try:
            # Initialize keys first
            if not await self.initialize_keys():
                if self.on_error_callback:
                    await self.on_error_callback("Failed to load encryption keys (wrong password?)")
                return False

            # Connect to WebSocket
            self.websocket = await websockets.connect(self.server_url)

            # Authenticate
            msg = Message(MessageType.AUTHENTICATE, username=self.username, password=self.password)
            await self._safe_send(msg.to_json())

            # Wait for response
            response_str = await self.websocket.recv()
            try:
                response = Message.from_json(response_str)
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                if self.on_error_callback:
                    await self.on_error_callback(f"Invalid server response: {str(e)}")
                return False

            if response.type == MessageType.AUTHENTICATED:
                self.token = response.get('token')
                self.authenticated = True
                self.running = True

                # Start message receiver with exception callback
                self.receiver_task = asyncio.create_task(self._receive_messages())
                self.receiver_task.add_done_callback(self._receiver_task_done)

                return True
            else:
                error = response.get('error', 'Unknown error')
                if self.on_error_callback:
                    await self.on_error_callback(f"Authentication failed: {error}")
                return False

        except Exception as e:
            if self.on_error_callback:
                await self.on_error_callback(f"Connection error: {str(e)}")
            return False

    def _receiver_task_done(self, task: asyncio.Task):
        """Callback when receiver task completes or fails."""
        try:
            # Get the exception if any (this won't raise)
            exc = task.exception()
            if exc:
                logger.error(f"Receiver task failed with exception: {exc}")
                # Schedule error callback on the event loop
                if self.on_error_callback:
                    asyncio.create_task(self.on_error_callback(f"Receiver error: {exc}"))
        except asyncio.CancelledError:
            pass  # Task was cancelled, that's fine
        except asyncio.InvalidStateError:
            pass  # Task still running, shouldn't happen in done callback

    async def disconnect(self):
        """Disconnect from the server."""
        self._should_reconnect = False  # Disable reconnection on intentional disconnect
        self.running = False

        # Clean up pending key requests
        for username, future in list(self.pending_key_requests.items()):
            if not future.done():
                future.cancel()
        self.pending_key_requests.clear()

        if self.receiver_task:
            self.receiver_task.cancel()
            try:
                await self.receiver_task
            except asyncio.CancelledError:
                pass

        if self.websocket:
            try:
                await self.websocket.close()
            except Exception:
                pass  # Ignore errors during close
            self.websocket = None

    async def _receive_messages(self):
        """Background task to receive and process messages."""
        try:
            async for message_str in self.websocket:
                try:
                    message = Message.from_json(message_str)
                except (json.JSONDecodeError, KeyError, TypeError) as e:
                    logger.warning(f"Failed to parse message: {e}")
                    continue  # Skip malformed messages

                if message.type == MessageType.NEW_MESSAGE:
                    await self._handle_new_message(message)

                elif message.type == MessageType.USER_STATUS:
                    if self.on_status_callback:
                        username = message.get('username')
                        online = message.get('online')
                        await self.on_status_callback(username, online)

                elif message.type == MessageType.TYPING_INDICATOR:
                    if self.on_typing_callback:
                        username = message.get('username')
                        recipient = message.get('recipient')
                        channel = message.get('channel')
                        await self.on_typing_callback(username, recipient, channel)

                elif message.type == MessageType.PUBLIC_KEY_RESPONSE:
                    # Handle public key response
                    username = message.get('username')
                    public_key_b64 = message.get('public_key')

                    if public_key_b64 and username:
                        try:
                            public_key = base64.b64decode(public_key_b64)
                        except Exception as e:
                            logger.warning(f"Failed to decode public key for {username}: {e}")
                            continue

                        # Cache it
                        self.key_manager.cache_public_key(username, public_key)

                        # Resolve pending future if exists
                        if username in self.pending_key_requests:
                            future = self.pending_key_requests.pop(username)
                            if not future.done():
                                future.set_result(public_key)

                elif message.type == MessageType.CHANNEL_CREATED:
                    if self.on_channel_created_callback:
                        channel_id = message.get('channel_id')
                        channel_name = message.get('channel_name')
                        await self.on_channel_created_callback(channel_id, channel_name)

                elif message.type == MessageType.CHANNEL_JOINED:
                    if self.on_channel_joined_callback:
                        channel_id = message.get('channel_id')
                        channel_name = message.get('channel_name')
                        await self.on_channel_joined_callback(channel_id, channel_name)

                elif message.type == MessageType.FILE_UPLOADED:
                    file_id = message.get('file_id')
                    if file_id:
                        self.file_manager.clear_pending_upload(file_id)

                elif message.type == MessageType.FILE_AVAILABLE:
                    await self._handle_file_available(message)

                elif message.type == MessageType.FILE_DATA:
                    await self._handle_file_data(message)

                elif message.type == MessageType.CHANNELS_LIST:
                    if self.on_channels_list_callback:
                        channels = message.get('channels', [])
                        await self.on_channels_list_callback(channels)

                elif message.type == MessageType.MESSAGE_DELIVERED:
                    if self.on_message_delivered_callback:
                        message_id = message.get('message_id')
                        if message_id:
                            await self.on_message_delivered_callback(message_id)

                elif message.type == MessageType.USERS_LIST:
                    if self.on_users_list_callback:
                        users = message.get('users', [])
                        await self.on_users_list_callback(users)

                elif message.type == MessageType.ERROR:
                    if self.on_error_callback:
                        error = message.get('error')
                        await self.on_error_callback(error)

        except websockets.exceptions.ConnectionClosed:
            self.running = False
            self.websocket = None
            if self._should_reconnect and not self._reconnecting:
                await self._attempt_reconnect()
            elif self.on_error_callback:
                await self.on_error_callback("Connection closed")
        except Exception as e:
            self.running = False
            if self.on_error_callback:
                await self.on_error_callback(f"Receive error: {str(e)}")
            if self._should_reconnect and not self._reconnecting:
                await self._attempt_reconnect()

    async def _attempt_reconnect(self):
        """Attempt to reconnect with exponential backoff."""
        if self._reconnecting:
            return

        self._reconnecting = True

        while self._should_reconnect and self._reconnect_attempts < self._max_reconnect_attempts:
            self._reconnect_attempts += 1
            delay = min(
                self._reconnect_delay * (2 ** (self._reconnect_attempts - 1)),
                self._max_reconnect_delay
            )

            logger.info(f"Reconnecting in {delay:.1f}s (attempt {self._reconnect_attempts}/{self._max_reconnect_attempts})")
            if self.on_error_callback:
                await self.on_error_callback(f"Reconnecting in {delay:.1f}s...")

            await asyncio.sleep(delay)

            if not self._should_reconnect:
                break

            try:
                # Attempt to reconnect
                self.websocket = await websockets.connect(self.server_url)

                # Re-authenticate
                msg = Message(MessageType.AUTHENTICATE, username=self.username, password=self.password)
                await self.websocket.send(msg.to_json())

                response_str = await self.websocket.recv()
                response = Message.from_json(response_str)

                if response.type == MessageType.AUTHENTICATED:
                    self.token = response.get('token')
                    self.authenticated = True
                    self.running = True
                    self._reconnect_attempts = 0  # Reset counter on success
                    self._reconnecting = False

                    # Restart message receiver
                    self.receiver_task = asyncio.create_task(self._receive_messages())

                    logger.info("Reconnected successfully")
                    if self.on_status_callback:
                        await self.on_status_callback("system", True)  # Notify reconnected

                    return
                else:
                    logger.warning(f"Reconnection authentication failed: {response.get('error')}")

            except Exception as e:
                logger.warning(f"Reconnection attempt {self._reconnect_attempts} failed: {e}")

        self._reconnecting = False
        if self._reconnect_attempts >= self._max_reconnect_attempts:
            if self.on_error_callback:
                await self.on_error_callback("Failed to reconnect after maximum attempts")

    async def _handle_new_message(self, message: Message):
        """Handle incoming message and decrypt if needed."""
        sender = message.get('sender')
        recipient = message.get('recipient')
        channel = message.get('channel')
        encrypted_payload = message.get('encrypted_payload')
        timestamp = message.get('timestamp', 0)
        message_id = message.get('message_id')

        plaintext = None
        is_encrypted = False

        if encrypted_payload:
            # Encrypted message
            try:
                if channel:
                    # Channel message - decrypt with symmetric key
                    channel_key = self.channel_key_manager.get_channel_key(channel)
                    if channel_key:
                        plaintext = self.channel_key_manager.decrypt_channel_message(
                            encrypted_payload['ciphertext'],
                            encrypted_payload['nonce'],
                            channel_key
                        )
                        is_encrypted = True
                    else:
                        logger.warning(f"Missing channel key for #{channel} - unable to decrypt message from {sender}")
                        plaintext = f"[No key for channel #{channel}]"
                        # Notify UI of the issue
                        if self.on_error_callback:
                            asyncio.create_task(
                                self.on_error_callback(f"Cannot decrypt message: missing key for #{channel}")
                            )
                else:
                    # Direct message - decrypt with ECDH
                    plaintext = ECDHKeyExchange.decrypt_from_sender(
                        encrypted_payload,
                        self.private_key
                    )
                    is_encrypted = True
            except Exception as e:
                plaintext = f"[Failed to decrypt: {str(e)}]"
        else:
            # Plaintext (Phase 1 compatibility)
            plaintext = message.get('plaintext', '[no content]')

        # Send delivery confirmation
        if message_id:
            confirm = Message(MessageType.MESSAGE_DELIVERED, message_id=message_id)
            await self._safe_send(confirm.to_json())

        # Notify UI
        if self.on_message_callback:
            await self.on_message_callback(
                sender=sender,
                recipient=recipient,
                channel=channel,
                message=plaintext,
                timestamp=timestamp,
                is_encrypted=is_encrypted,
                message_id=message_id
            )

    async def send_message(self, recipient: Optional[str] = None, channel: Optional[str] = None, text: str = ""):
        """Send an encrypted message."""
        if not self.authenticated:
            if self.on_error_callback:
                await self.on_error_callback("Not authenticated")
            return

        if recipient:
            # Direct message - encrypt with ECDH
            await self._send_encrypted_dm(recipient, text)
        elif channel:
            # Channel message - encrypt with symmetric key
            await self._send_encrypted_channel_message(channel, text)
        else:
            if self.on_error_callback:
                await self.on_error_callback("Must specify recipient or channel")

    async def _send_encrypted_dm(self, recipient: str, text: str):
        """Send encrypted direct message."""
        # Get recipient's public key
        recipient_public_key = await self._get_public_key(recipient)
        if not recipient_public_key:
            if self.on_error_callback:
                await self.on_error_callback(f"Could not get public key for {recipient}")
            return

        # Generate ephemeral keypair for Perfect Forward Secrecy
        ephemeral_private, ephemeral_public = self.key_manager.generate_ephemeral_keypair()

        # Encrypt message
        encrypted_payload = ECDHKeyExchange.encrypt_for_recipient(
            text,
            recipient_public_key,
            ephemeral_private
        )

        # Send encrypted message
        msg = Message(
            MessageType.SEND_MESSAGE,
            auth_token=self.token,
            recipient=recipient,
            encrypted_payload=encrypted_payload
        )

        await self._safe_send(msg.to_json())

    async def _get_public_key(self, username: str) -> Optional[bytes]:
        """Get a user's public key (with caching)."""
        # Check cache first
        cached_key = self.key_manager.get_cached_public_key(username)
        if cached_key:
            return cached_key

        # Create future for this request
        future = asyncio.Future()
        self.pending_key_requests[username] = future

        # Request from server
        msg = Message(MessageType.REQUEST_PUBLIC_KEY, auth_token=self.token, username=username)
        await self._safe_send(msg.to_json())

        # Wait for response (with timeout)
        try:
            public_key = await asyncio.wait_for(future, timeout=5.0)
            return public_key
        except asyncio.TimeoutError:
            self.pending_key_requests.pop(username, None)
            return None
        except Exception:
            self.pending_key_requests.pop(username, None)
            return None

    async def send_typing_indicator(self, recipient: Optional[str] = None, channel: Optional[str] = None):
        """Send typing indicator."""
        if self.authenticated:
            msg = Message(
                MessageType.TYPING,
                auth_token=self.token,
                recipient=recipient,
                channel=channel
            )
            await self._safe_send(msg.to_json())

    async def _send_encrypted_channel_message(self, channel: str, text: str):
        """Send encrypted channel message."""
        # Get channel key
        channel_key = self.channel_key_manager.get_channel_key(channel)
        if not channel_key:
            if self.on_error_callback:
                await self.on_error_callback(f"Not a member of #{channel}")
            return

        # Encrypt message with channel key
        encrypted_payload = self.channel_key_manager.encrypt_channel_message(text, channel_key)

        # Send encrypted message
        msg = Message(
            MessageType.SEND_MESSAGE,
            auth_token=self.token,
            channel=channel,
            encrypted_payload=encrypted_payload
        )

        await self._safe_send(msg.to_json())

    async def create_channel(self, channel_name: str):
        """Create a new channel."""
        if not self.authenticated:
            if self.on_error_callback:
                await self.on_error_callback("Not authenticated")
            return

        # Generate channel key
        channel_key = self.channel_key_manager.generate_channel_key()

        # Encrypt channel key for ourselves
        my_public_key = self.key_manager.get_cached_public_key(self.username)
        if not my_public_key:
            # Get our own public key from server
            my_public_key = await self._get_public_key(self.username)

        if not my_public_key:
            if self.on_error_callback:
                await self.on_error_callback("Could not get own public key")
            return

        encrypted_channel_key = self.channel_key_manager.encrypt_channel_key_for_user(
            channel_key,
            my_public_key
        )

        # Store channel key locally
        self.channel_key_manager.store_channel_key(channel_name, channel_key)

        # Send create channel request
        try:
            encrypted_key_combined = base64.b64encode(
                base64.b64decode(encrypted_channel_key['ephemeral_public_key']) +
                base64.b64decode(encrypted_channel_key['ciphertext']) +
                base64.b64decode(encrypted_channel_key['nonce'])
            ).decode('utf-8')
        except Exception as e:
            if self.on_error_callback:
                await self.on_error_callback(f"Failed to encode channel key: {e}")
            return

        msg = Message(
            MessageType.CREATE_CHANNEL,
            auth_token=self.token,
            channel_name=channel_name,
            encrypted_channel_key=encrypted_key_combined
        )

        await self._safe_send(msg.to_json())

    async def join_channel(self, channel_name: str, channel_key: bytes):
        """Join an existing channel."""
        if not self.authenticated:
            if self.on_error_callback:
                await self.on_error_callback("Not authenticated")
            return

        # Encrypt channel key for ourselves
        my_public_key = self.key_manager.get_cached_public_key(self.username)
        if not my_public_key:
            my_public_key = await self._get_public_key(self.username)

        if not my_public_key:
            if self.on_error_callback:
                await self.on_error_callback("Could not get own public key")
            return

        encrypted_channel_key = self.channel_key_manager.encrypt_channel_key_for_user(
            channel_key,
            my_public_key
        )

        # Store channel key locally
        self.channel_key_manager.store_channel_key(channel_name, channel_key)

        # Send join channel request
        try:
            encrypted_key_combined = base64.b64encode(
                base64.b64decode(encrypted_channel_key['ephemeral_public_key']) +
                base64.b64decode(encrypted_channel_key['ciphertext']) +
                base64.b64decode(encrypted_channel_key['nonce'])
            ).decode('utf-8')
        except Exception as e:
            if self.on_error_callback:
                await self.on_error_callback(f"Failed to encode channel key: {e}")
            return

        msg = Message(
            MessageType.JOIN_CHANNEL,
            auth_token=self.token,
            channel_name=channel_name,
            encrypted_channel_key=encrypted_key_combined
        )

        await self._safe_send(msg.to_json())

    async def list_channels(self):
        """Request list of all channels."""
        if self.authenticated:
            msg = Message(MessageType.LIST_CHANNELS, auth_token=self.token)
            await self._safe_send(msg.to_json())

    async def list_users(self):
        """Request list of online users."""
        if self.authenticated:
            msg = Message(MessageType.LIST_USERS, auth_token=self.token)
            await self._safe_send(msg.to_json())

    async def upload_file(
        self,
        file_path: str,
        recipient: Optional[str] = None,
        channel: Optional[str] = None
    ):
        """
        Upload an encrypted file.

        Args:
            file_path: Path to file to upload
            recipient: Username for DM
            channel: Channel name for channel file
        """
        if not self.authenticated:
            if self.on_error_callback:
                await self.on_error_callback("Not authenticated")
            return

        try:
            # Prepare file for upload
            recipient_public_key = None
            channel_key = None

            if recipient:
                # Get recipient's public key
                recipient_public_key = await self._get_public_key(recipient)
                if not recipient_public_key:
                    if self.on_error_callback:
                        await self.on_error_callback(f"Could not get public key for {recipient}")
                    return

            elif channel:
                # Get channel key
                channel_key = self.channel_key_manager.get_channel_key(channel)
                if not channel_key:
                    if self.on_error_callback:
                        await self.on_error_callback(f"Not a member of #{channel}")
                    return

            # Prepare upload
            upload_info = await self.file_manager.prepare_file_upload(
                file_path,
                recipient_public_key=recipient_public_key,
                channel_key=channel_key,
                key_manager=self.key_manager
            )

            # Send upload request
            msg = Message(
                MessageType.UPLOAD_FILE,
                auth_token=self.token,
                recipient=recipient,
                channel=channel,
                file_id=upload_info['file_id'],
                filename=upload_info['filename'],
                size_bytes=upload_info['size_bytes'],
                mime_type=upload_info['mime_type'],
                encrypted_data=base64.b64encode(upload_info['encrypted_data']).decode('utf-8'),
                encrypted_file_key=upload_info['encrypted_file_key'],
                file_hash=upload_info['file_hash']
            )

            await self._safe_send(msg.to_json())

        except Exception as e:
            if self.on_error_callback:
                await self.on_error_callback(f"File upload error: {str(e)}")

    async def download_file(self, file_id: str):
        """Request file download."""
        if self.authenticated:
            msg = Message(MessageType.DOWNLOAD_FILE, auth_token=self.token, file_id=file_id)
            await self._safe_send(msg.to_json())

    async def _handle_file_available(self, message: Message):
        """Handle file available notification."""
        file_id = message.get('file_id')
        sender = message.get('sender')
        filename = message.get('filename')
        size_bytes = message.get('size_bytes')
        mime_type = message.get('mime_type')
        encrypted_file_key = message.get('encrypted_file_key')
        file_hash = message.get('file_hash')
        recipient = message.get('recipient')
        channel = message.get('channel')

        await self.file_manager.handle_file_available(
            file_id=file_id,
            sender=sender,
            filename=filename,
            size_bytes=size_bytes,
            mime_type=mime_type,
            encrypted_file_key=encrypted_file_key,
            file_hash=file_hash,
            recipient=recipient,
            channel=channel
        )

        # Notify UI
        if self.on_file_available_callback:
            await self.on_file_available_callback(
                file_id=file_id,
                sender=sender,
                filename=filename,
                size_bytes=size_bytes,
                conversation=channel if channel else sender
            )

    async def _handle_file_data(self, message: Message):
        """Handle file data response."""
        file_id = message.get('file_id')
        encrypted_data_b64 = message.get('encrypted_data')

        if not encrypted_data_b64:
            return

        try:
            encrypted_data = base64.b64decode(encrypted_data_b64)
        except Exception as e:
            logger.error(f"Failed to decode file data for {file_id}: {e}")
            if self.on_error_callback:
                await self.on_error_callback(f"Failed to decode file data: {e}")
            return

        # Get file info
        file_info = self.file_manager.get_available_file(file_id)
        if not file_info:
            return

        # Determine decryption method
        channel_key = None
        if file_info.get('channel'):
            channel_key = self.channel_key_manager.get_channel_key(file_info['channel'])

        try:
            # Download and decrypt
            output_path = await self.file_manager.download_and_decrypt_file(
                file_id=file_id,
                encrypted_data=encrypted_data,
                private_key=self.private_key,
                channel_key=channel_key
            )

            # Notify UI
            if self.on_message_callback:
                conversation = file_info.get('channel') or file_info.get('sender')
                await self.on_message_callback(
                    sender=file_info['sender'],
                    recipient=file_info.get('recipient'),
                    channel=file_info.get('channel'),
                    message=f"📎 File received: {file_info['filename']} → {output_path}",
                    timestamp=asyncio.get_event_loop().time(),
                    is_encrypted=True
                )

        except Exception as e:
            if self.on_error_callback:
                await self.on_error_callback(f"File download error: {str(e)}")
