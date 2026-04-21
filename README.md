# SecureMessaging

Complete end-to-end encrypted terminal messaging system with file sharing, group channels, and read receipts.

## Overview

SecureMessaging is a **feature-complete**, zero-knowledge messaging system built entirely for the terminal:
- **End-to-end encryption** - Server cannot read messages or files
- **Direct messaging** with Perfect Forward Secrecy
- **Group channels** with symmetric encryption
- **File sharing** with automatic encryption/decryption
- **Read receipts** with visual indicators (✓✓)
- **Real-time delivery** via WebSockets
- **Beautiful Terminal UI** using Textual framework

## Current Status

✓ **Phase 1 Complete** - Core server with authentication
✓ **Phase 2 Complete** - E2E Encryption (X25519 + ChaCha20-Poly1305)
✓ **Phase 3 Complete** - Full TUI client with Textual
✓ **Phase 4 Complete** - Group channels with encrypted key distribution
✓ **Phase 5 Complete** - File sharing with encryption & read receipts

**System is feature-complete and ready for use!**

Future enhancements could include: notification sounds, message editing, message search, video calls

## Quick Start

### 1. Server Setup

```bash
cd /home/julian/Claude/Projects/SecureMessaging

# Activate virtual environment
source .venv/bin/activate

# Database is already initialized, but to reinitialize:
# .venv/bin/python scripts/init_db.py

# Create a user
.venv/bin/python scripts/create_user.py alice

# Start server
.venv/bin/python server/server.py
```

Server runs on `ws://100.96.169.49:3005` (Tailscale network only).

### 2. TUI Client (Phase 3)

Launch the Textual Terminal UI client:

```bash
cd /home/julian/Claude/Projects/SecureMessaging
./scripts/launch_tui.sh
```

**Usage:**
1. Enter username and password on the login screen
2. Press Enter or click "Login" to connect
3. Type `/help` to see all available commands
4. Start a new DM: `@username your message here`
5. Create a channel: `/create #channelname`
6. Send to channel: `#channelname your message here`
7. Upload a file: `/upload /path/to/file`
8. List channels: `/list`
9. List online users: `/users`
10. Click conversations in sidebar (unread count shown)
11. Press Escape to quit

**Visual Indicators:**
- 🔒 = Encrypted message
- ✓ = Message delivered
- ✓✓ = Message read
- (N) = N unread messages
- 📎 = File available

### 3. Command-Line Test Client (Phase 1/2)

For testing or headless usage:

```bash
cd /home/julian/Claude/Projects/SecureMessaging
source .venv/bin/activate

# Simple test client (Phase 1)
.venv/bin/python scripts/test_client.py alice <password>

# Encrypted test client (Phase 2)
.venv/bin/python scripts/encrypted_client.py alice <password>
```

**Commands:**
- `/msg <user> <message>` - Send encrypted message
- `/plain <user> <message>` - Send plaintext (Phase 1 compat)
- `/key <user>` - Get user's public key
- `/quit` - Disconnect

### 4. Multi-User Testing

Open multiple terminals and connect different users to test real-time encrypted messaging.

## Architecture

```
SecureMessaging/
├── server/              # WebSocket server
│   ├── server.py       # Main entry point
│   ├── auth.py         # Argon2 authentication
│   ├── storage.py      # Database operations
│   ├── router.py       # Message routing
│   └── websocket_handler.py
│
├── client/              # TUI client (Phase 3+)
│   ├── ui/             # Textual interface
│   └── crypto/         # Encryption layer
│
├── shared/              # Shared protocol
│   ├── protocol.py     # Message definitions
│   └── constants.py    # Shared constants
│
├── scripts/             # Admin tools
│   ├── init_db.py      # Initialize databases
│   ├── create_user.py  # Create users
│   └── test_client.py  # Phase 1 test client
│
└── data/                # Runtime data
    ├── server/
    │   └── server.db   # SQLite database
    └── client/
```

## Security Model

**Phase 1:**
- Argon2id password hashing
- Session tokens
- Real-time WebSocket messaging

**Phase 2:**
- X25519 ECDH key exchange ✓
- ChaCha20-Poly1305 AEAD encryption ✓
- Perfect Forward Secrecy ✓
- Zero-knowledge server (cannot decrypt) ✓

**Phase 4:**
- Group channels with symmetric encryption ✓
- Encrypted channel key distribution ✓
- Multi-user encrypted group chats ✓
- Channel member management ✓

**Phase 5 (Current):**
- Encrypted file sharing in DMs and channels ✓
- File upload/download with integrity verification ✓
- Read receipts with double checkmark indicators ✓
- Automatic file decryption and saving ✓

## Database Schema

**Server DB** (`data/server/server.db`):
- `users` - User accounts, public keys, passwords
- `sessions` - Active sessions with tokens
- `messages` - Encrypted message storage
- `channels` - Channel metadata
- `channel_members` - Channel membership

**Client DB** (Phase 3+):
- Local decrypted message cache
- Private keys (password-encrypted)
- Public key cache

## Configuration

Server config: `config/server_config.json`

```json
{
  "server": {
    "host": "100.96.169.49",
    "port": 3005,
    "max_connections": 50
  },
  "database": {
    "path": "data/server/server.db"
  }
}
```

## Development

**Dependencies:**
- Python 3.12+
- websockets - WebSocket protocol
- argon2-cffi - Password hashing
- cryptography - E2E encryption (Phase 2+)
- textual - Terminal UI (Phase 3+)

**Install:**
```bash
pip install -r requirements.txt
```

## Deployment (Future)

Server will run as systemd service with sandboxing:
- Dedicated system user
- AppArmor/SELinux
- Resource limits
- Tailscale network only

## Educational Goals

Learn:
- Modern cryptography (ECDH, AEAD)
- Zero-knowledge architecture
- Async programming with WebSockets
- Terminal UI development
- System administration

## License

Educational use only. Not for production.

## Author

Julian Marinov - Flashgate Ltd.
Built with Claude Code (Sonnet 4.5)
