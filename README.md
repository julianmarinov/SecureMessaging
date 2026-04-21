# SecureMessaging

[![License](https://img.shields.io/badge/license-Educational-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey.svg)]()

Complete end-to-end encrypted terminal messaging system with file sharing, group channels, and read receipts.

## One-Command Installation

### macOS / Linux
```bash
curl -fsSL https://raw.githubusercontent.com/julianmarinov/SecureMessaging/main/install.sh | bash
```

### Windows (PowerShell)
```powershell
iwr -useb https://raw.githubusercontent.com/julianmarinov/SecureMessaging/main/install.ps1 | iex
```

**Requirements:**
- Git (the installer will auto-install Python on macOS if needed)
- 50MB disk space

The installer will automatically:
1. Install Python 3.12 via Homebrew (macOS only, if needed)
2. Clone the repository
3. Create a virtual environment
4. Install dependencies
5. Initialize the database
6. Create your first user
7. Set up launcher scripts

### Client-Only Installation

To connect to an existing server without installing the server components:

**macOS / Linux:**
```bash
curl -fsSL https://raw.githubusercontent.com/julianmarinov/SecureMessaging/main/install-client-only.sh | bash
```

This installs only the client and prompts for the server address during setup.

### Manual Installation

If you prefer to install manually:

```bash
# Clone the repository
git clone https://github.com/julianmarinov/SecureMessaging.git
cd SecureMessaging

# Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup configuration
cp config/server_config.example.json config/server_config.json

# Initialize database
python scripts/init_db.py

# Create your first user
python scripts/create_user.py <username>
```

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

After installation, start using SecureMessaging:

### 1. Start the Server

```bash
cd ~/SecureMessaging
./securemsg-server
```

The server runs on `0.0.0.0:3005` by default (accessible from your local network).

### 2. Start the Client

Open a new terminal and launch the client:

```bash
cd ~/SecureMessaging
./securemsg
```

On Windows:
```cmd
cd %USERPROFILE%\SecureMessaging
securemsg.bat
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

### 3. Create Additional Users

```bash
cd ~/SecureMessaging
source .venv/bin/activate
python scripts/create_user.py <username>
```

### 4. Multi-User Testing

Open multiple terminals and connect different users to test real-time encrypted messaging.

For headless testing, you can use the command-line clients:

```bash
cd ~/SecureMessaging
source .venv/bin/activate
python scripts/encrypted_client.py <username> <password>
```

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

## Deployment

The installation script creates launcher scripts for easy deployment.

### Running as a Service (Linux)

Create a systemd service file at `/etc/systemd/system/securemsg.service`:

```ini
[Unit]
Description=SecureMessaging Server
After=network.target

[Service]
Type=simple
User=yourusername
WorkingDirectory=/home/yourusername/SecureMessaging
ExecStart=/home/yourusername/SecureMessaging/securemsg-server
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then enable and start:
```bash
sudo systemctl enable securemsg
sudo systemctl start securemsg
```

### Network Configuration

By default, the server binds to `0.0.0.0:3005` (all interfaces).

For production deployments:
- Use a reverse proxy (nginx, Caddy) with TLS
- Configure firewall rules
- Consider Tailscale for zero-trust networking
- Run behind a VPN for private networks

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
