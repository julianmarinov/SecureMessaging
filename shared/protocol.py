"""
Protocol definitions for SecureMessaging.
Defines message formats for client-server communication.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
import json

# Message type constants
class MessageType:
    """WebSocket message type identifiers."""
    # Authentication
    AUTHENTICATE = "authenticate"
    AUTHENTICATED = "authenticated"
    AUTH_ERROR = "auth_error"

    # Messaging
    SEND_MESSAGE = "send_message"
    NEW_MESSAGE = "new_message"
    MESSAGE_DELIVERED = "message_delivered"
    MESSAGE_READ = "message_read"

    # Key management
    REQUEST_PUBLIC_KEY = "request_public_key"
    PUBLIC_KEY_RESPONSE = "public_key_response"

    # Channels
    CREATE_CHANNEL = "create_channel"
    CHANNEL_CREATED = "channel_created"
    JOIN_CHANNEL = "join_channel"
    CHANNEL_JOINED = "channel_joined"
    LEAVE_CHANNEL = "leave_channel"
    LIST_CHANNELS = "list_channels"
    CHANNELS_LIST = "channels_list"

    # Presence
    TYPING = "typing"
    TYPING_INDICATOR = "typing_indicator"
    USER_STATUS = "user_status"

    # Files
    UPLOAD_FILE = "upload_file"
    FILE_UPLOADED = "file_uploaded"
    DOWNLOAD_FILE = "download_file"
    FILE_DATA = "file_data"
    FILE_AVAILABLE = "file_available"

    # General
    ERROR = "error"
    PING = "ping"
    PONG = "pong"
    LIST_USERS = "list_users"
    USERS_LIST = "users_list"

@dataclass
class EncryptedPayload:
    """Container for encrypted message data."""
    ephemeral_public_key: Optional[str] = None  # Base64 encoded (for ECDH)
    ciphertext: str = ""                         # Base64 encoded
    nonce: str = ""                              # Base64 encoded

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EncryptedPayload':
        return cls(**data)

class Message:
    """Base message class with serialization."""

    def __init__(self, msg_type: str, **kwargs):
        self.type = msg_type
        self.data = kwargs

    def to_json(self) -> str:
        """Serialize message to JSON."""
        return json.dumps({"type": self.type, **self.data})

    @classmethod
    def from_json(cls, json_str: str) -> 'Message':
        """Deserialize message from JSON."""
        data = json.loads(json_str)
        msg_type = data.pop("type")
        return cls(msg_type, **data)

    def __getitem__(self, key: str) -> Any:
        """Allow dict-like access to data."""
        return self.data.get(key)

    def get(self, key: str, default: Any = None) -> Any:
        """Get data value with default."""
        return self.data.get(key, default)

# Authentication messages
def authenticate_msg(username: str, password: str) -> Message:
    """Client -> Server: Authentication request."""
    return Message(MessageType.AUTHENTICATE, username=username, password=password)

def authenticated_msg(token: str, user_id: int, username: str) -> Message:
    """Server -> Client: Authentication successful."""
    return Message(MessageType.AUTHENTICATED, token=token, user_id=user_id, username=username)

def auth_error_msg(error: str) -> Message:
    """Server -> Client: Authentication failed."""
    return Message(MessageType.AUTH_ERROR, error=error)

# Messaging
def send_message_msg(
    auth_token: str,
    recipient: Optional[str] = None,
    channel: Optional[str] = None,
    encrypted_payload: Optional[Dict[str, Any]] = None,
    plaintext: Optional[str] = None,  # Phase 1 only
    timestamp: Optional[float] = None
) -> Message:
    """Client -> Server: Send a message."""
    return Message(
        MessageType.SEND_MESSAGE,
        auth_token=auth_token,
        recipient=recipient,
        channel=channel,
        encrypted_payload=encrypted_payload,
        plaintext=plaintext,
        timestamp=timestamp
    )

def new_message_msg(
    message_id: int,
    sender: str,
    recipient: Optional[str] = None,
    channel: Optional[str] = None,
    encrypted_payload: Optional[Dict[str, Any]] = None,
    plaintext: Optional[str] = None,  # Phase 1 only
    timestamp: float = 0
) -> Message:
    """Server -> Client: New incoming message."""
    return Message(
        MessageType.NEW_MESSAGE,
        message_id=message_id,
        sender=sender,
        recipient=recipient,
        channel=channel,
        encrypted_payload=encrypted_payload,
        plaintext=plaintext,
        timestamp=timestamp
    )

def message_delivered_msg(message_id: int) -> Message:
    """Client -> Server: Message delivered confirmation."""
    return Message(MessageType.MESSAGE_DELIVERED, message_id=message_id)

def message_read_msg(message_id: int) -> Message:
    """Client -> Server: Message read confirmation."""
    return Message(MessageType.MESSAGE_READ, message_id=message_id)

# Key management
def request_public_key_msg(auth_token: str, username: str) -> Message:
    """Client -> Server: Request user's public key."""
    return Message(MessageType.REQUEST_PUBLIC_KEY, auth_token=auth_token, username=username)

def public_key_response_msg(username: str, public_key: str) -> Message:
    """Server -> Client: Public key response."""
    return Message(MessageType.PUBLIC_KEY_RESPONSE, username=username, public_key=public_key)

# Channels
def create_channel_msg(auth_token: str, channel_name: str) -> Message:
    """Client -> Server: Create a new channel."""
    return Message(MessageType.CREATE_CHANNEL, auth_token=auth_token, channel_name=channel_name)

def channel_created_msg(channel_id: int, channel_name: str) -> Message:
    """Server -> Client: Channel created successfully."""
    return Message(MessageType.CHANNEL_CREATED, channel_id=channel_id, channel_name=channel_name)

def list_channels_msg(auth_token: str) -> Message:
    """Client -> Server: List all channels."""
    return Message(MessageType.LIST_CHANNELS, auth_token=auth_token)

def channels_list_msg(channels: List[Dict[str, Any]]) -> Message:
    """Server -> Client: List of channels."""
    return Message(MessageType.CHANNELS_LIST, channels=channels)

# Presence
def typing_msg(auth_token: str, recipient: Optional[str] = None, channel: Optional[str] = None) -> Message:
    """Client -> Server: User is typing."""
    return Message(MessageType.TYPING, auth_token=auth_token, recipient=recipient, channel=channel)

def typing_indicator_msg(username: str, recipient: Optional[str] = None, channel: Optional[str] = None) -> Message:
    """Server -> Client: Typing indicator broadcast."""
    return Message(MessageType.TYPING_INDICATOR, username=username, recipient=recipient, channel=channel)

def user_status_msg(username: str, online: bool) -> Message:
    """Server -> Client: User online/offline status."""
    return Message(MessageType.USER_STATUS, username=username, online=online)

# General
def error_msg(error: str, details: Optional[str] = None) -> Message:
    """Server -> Client: Error message."""
    return Message(MessageType.ERROR, error=error, details=details)

def ping_msg() -> Message:
    """Keepalive ping."""
    return Message(MessageType.PING)

def pong_msg() -> Message:
    """Keepalive pong."""
    return Message(MessageType.PONG)

# File sharing
def upload_file_msg(
    auth_token: str,
    recipient: Optional[str] = None,
    channel: Optional[str] = None,
    file_id: str = "",
    filename: str = "",
    size_bytes: int = 0,
    mime_type: str = "",
    encrypted_data: str = "",  # Base64
    encrypted_file_key: Optional[Dict[str, Any]] = None,
    file_hash: str = ""
) -> Message:
    """Client -> Server: Upload encrypted file."""
    return Message(
        MessageType.UPLOAD_FILE,
        auth_token=auth_token,
        recipient=recipient,
        channel=channel,
        file_id=file_id,
        filename=filename,
        size_bytes=size_bytes,
        mime_type=mime_type,
        encrypted_data=encrypted_data,
        encrypted_file_key=encrypted_file_key,
        file_hash=file_hash
    )

def file_uploaded_msg(file_id: str) -> Message:
    """Server -> Client: File upload confirmation."""
    return Message(MessageType.FILE_UPLOADED, file_id=file_id)

def file_available_msg(
    file_id: str,
    sender: str,
    filename: str,
    size_bytes: int,
    mime_type: str,
    encrypted_file_key: Dict[str, Any],
    file_hash: str,
    recipient: Optional[str] = None,
    channel: Optional[str] = None
) -> Message:
    """Server -> Client: File available for download."""
    return Message(
        MessageType.FILE_AVAILABLE,
        file_id=file_id,
        sender=sender,
        recipient=recipient,
        channel=channel,
        filename=filename,
        size_bytes=size_bytes,
        mime_type=mime_type,
        encrypted_file_key=encrypted_file_key,
        file_hash=file_hash
    )

def download_file_msg(auth_token: str, file_id: str) -> Message:
    """Client -> Server: Request file download."""
    return Message(MessageType.DOWNLOAD_FILE, auth_token=auth_token, file_id=file_id)

def file_data_msg(file_id: str, encrypted_data: str) -> Message:
    """Server -> Client: File data response."""
    return Message(MessageType.FILE_DATA, file_id=file_id, encrypted_data=encrypted_data)

# User discovery
def list_users_msg(auth_token: str) -> Message:
    """Client -> Server: Request list of online users."""
    return Message(MessageType.LIST_USERS, auth_token=auth_token)

def users_list_msg(users: List[str]) -> Message:
    """Server -> Client: List of online users."""
    return Message(MessageType.USERS_LIST, users=users)
