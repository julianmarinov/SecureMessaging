"""
Shared constants for SecureMessaging.
"""

# Server configuration defaults
DEFAULT_SERVER_HOST = "0.0.0.0"  # Bind to all interfaces by default
DEFAULT_SERVER_PORT = 3005
MAX_CONNECTIONS = 50

# Security constants
SESSION_TIMEOUT_HOURS = 24
MAX_LOGIN_ATTEMPTS = 5
ARGON2_TIME_COST = 3
ARGON2_MEMORY_COST = 65536  # 64 MB
ARGON2_PARALLELISM = 4

# Cryptography constants
KEY_SIZE = 32  # 256 bits for ChaCha20-Poly1305
NONCE_SIZE = 12  # ChaCha20-Poly1305 nonce size

# File transfer
MAX_FILE_SIZE_MB = 100
CHUNK_SIZE = 8192  # 8 KB chunks for file transfer

# WebSocket
PING_INTERVAL = 30  # seconds
PING_TIMEOUT = 10   # seconds

# Database
MESSAGE_RETENTION_DAYS = 0  # 0 = indefinite

# Version
VERSION = "0.1.0"
PROTOCOL_VERSION = "1.0"
