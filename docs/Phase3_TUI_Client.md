# Phase 3: Textual TUI Client

## Overview

Phase 3 implements a full-featured Terminal User Interface (TUI) using the Textual framework. The client provides a modern, interactive chat experience entirely in the terminal with real-time encrypted messaging.

## Features

### ✓ Implemented

1. **Login Screen**
   - Username/password authentication
   - Connection status feedback
   - Error handling with clear messages

2. **Main Chat Interface**
   - Two-panel layout: sidebar + messages
   - Conversation list in sidebar
   - Real-time message display
   - Message history per conversation

3. **Encrypted Messaging**
   - Automatic E2E encryption using X25519 + ChaCha20-Poly1305
   - Perfect Forward Secrecy with ephemeral keys
   - Visual indicators for encrypted messages (🔒)
   - Seamless key exchange in background

4. **Real-Time Features**
   - Live message delivery
   - User status updates (online/offline)
   - Typing indicators
   - Automatic message delivery confirmations

5. **User Experience**
   - Click conversations to switch between them
   - @username format to start new conversations
   - Status bar for notifications
   - Keyboard shortcuts (ESC to quit, Ctrl+N for new chat)

## Architecture

### Components

```
client/
├── connection.py           # WebSocket connection manager
├── main.py                 # Entry point
└── ui/
    ├── app.py             # Main Textual application
    └── screens.py         # Login and Chat screens
```

### Connection Manager

`connection.py` provides:
- WebSocket connection handling
- Authentication flow
- Public key fetching and caching
- Message encryption/decryption
- Event callbacks for UI updates

**Key Methods:**
- `connect()` - Connect and authenticate
- `send_message()` - Send encrypted message
- `disconnect()` - Clean disconnection

**Callbacks:**
- `on_message_callback` - New message received
- `on_status_callback` - User status changed
- `on_typing_callback` - Typing indicator
- `on_error_callback` - Error occurred

### UI Screens

#### LoginScreen

Simple authentication interface:
- Username input
- Password input (hidden)
- Login button
- Status/error messages

#### ChatScreen

Main chat interface:
- **Sidebar**: Conversation list (clickable)
- **Messages Area**: Scrollable message history
- **Input**: Message composition
- **Status Bar**: Notifications and status

## Usage

### Starting the Client

```bash
cd /home/julian/Claude/Projects/SecureMessaging
./scripts/launch_tui.sh
```

Or manually:
```bash
source .venv/bin/activate
python client/main.py
```

### Login

1. Enter your username
2. Enter your password
3. Press Enter or click "Login"
4. Wait for connection confirmation

### Sending Messages

**Start a new conversation:**
```
@alice Hello! How are you?
```

**Reply in current conversation:**
```
I'm doing great, thanks!
```

### Navigation

- **Switch conversations**: Click on username in sidebar
- **Scroll messages**: Arrow keys or mouse wheel
- **New chat**: Ctrl+N (shows help message)
- **Quit**: ESC key

## Message Flow

### Outgoing Message

1. User types message and presses Enter
2. UI displays message immediately (optimistic update)
3. Connection manager fetches recipient's public key (cached after first use)
4. Message is encrypted with ephemeral key (Perfect Forward Secrecy)
5. Encrypted payload sent to server
6. Server routes to recipient

### Incoming Message

1. Server forwards encrypted message
2. Connection manager receives WebSocket message
3. Message decrypted using private key
4. Callback notifies UI with plaintext
5. UI displays message in conversation
6. Delivery confirmation sent to server

## Security

### End-to-End Encryption

- **All direct messages are encrypted** before leaving your device
- Server **cannot read** message contents
- Uses **X25519 ECDH** for key exchange
- Uses **ChaCha20-Poly1305 AEAD** for message encryption
- **Perfect Forward Secrecy**: Each message uses a new ephemeral key

### Key Management

- **Identity Keys**: Long-term X25519 keypair per user
  - Private key stored locally, encrypted with user password
  - Public key stored on server for distribution

- **Ephemeral Keys**: Generated for each message
  - Used for Perfect Forward Secrecy
  - Never reused or stored

- **Key Caching**: Public keys cached locally to reduce server requests

### Visual Indicators

- 🔒 Lock emoji indicates encrypted message
- Regular text indicates plaintext (Phase 1 compatibility mode)

## Implementation Details

### Async Architecture

The client uses Python's `asyncio` for:
- Non-blocking WebSocket communication
- Concurrent UI updates and network operations
- Background message receiving

### Message Callbacks

Connection manager uses callbacks to decouple network and UI:

```python
async def handle_message(sender, recipient, channel, message, timestamp, is_encrypted):
    # Called when new message arrives
    # UI updates display asynchronously
```

### Public Key Fetching

Uses async Futures for clean key retrieval:

```python
# Request public key
future = asyncio.Future()
send_request()

# Wait for response (handled in receiver task)
public_key = await asyncio.wait_for(future, timeout=5.0)
```

## Testing

### Manual Testing

1. **Start server** (if not running):
   ```bash
   source .venv/bin/activate
   python server/server.py
   ```

2. **Open two terminals**, launch TUI in each:
   ```bash
   ./scripts/launch_tui.sh
   ```

3. **Login as different users**:
   - Terminal 1: alice
   - Terminal 2: bob

4. **Send messages**:
   - Alice: `@bob Hello Bob!`
   - Bob: `@alice Hi Alice!`

5. **Observe**:
   - Real-time delivery
   - Encryption indicators
   - Conversation switching
   - Status updates

### Known Test Users

Default test users (if database is initialized):
- Username: `alice`
- Username: `bob`

Passwords set during user creation.

## Future Enhancements (Phase 4+)

- [ ] Group channels with symmetric encryption
- [ ] File sharing with encrypted uploads
- [ ] Message search
- [ ] Notification sounds
- [ ] Custom themes/colors
- [ ] Multi-line message composition
- [ ] Emoji picker
- [ ] Read receipts
- [ ] Message editing/deletion

## Troubleshooting

### "Failed to connect"

- Check server is running: `pgrep -f server.py`
- Verify server URL in client/ui/app.py (default: `ws://100.96.169.49:3005`)
- Check Tailscale connection if using Tailscale network

### "Failed to load encryption keys"

- Wrong password
- Corrupted key database: `rm data/client/{username}.db` and try again

### "Could not get public key"

- Recipient user doesn't exist
- Server connection lost
- Check server logs for errors

### Messages not appearing

- Check both users are connected
- Verify encryption keys initialized
- Check server logs for routing errors

## Technical Notes

### Why Textual?

- **Rich terminal UI**: Modern, interactive interface
- **Cross-platform**: Works on Linux, macOS, Windows
- **Async-native**: Built on asyncio, perfect for real-time apps
- **CSS-like styling**: Easy to customize appearance
- **Reactive updates**: Efficient UI updates

### Performance

- **Key caching**: Public keys cached after first fetch
- **Optimistic updates**: Outgoing messages shown immediately
- **Async I/O**: Non-blocking network operations
- **Message batching**: WebSocket frames efficiently batched

## Code Quality

- **Type hints**: Full type annotations throughout
- **Error handling**: Comprehensive try/except blocks
- **Clean separation**: Connection logic separate from UI
- **Async/await**: Proper async patterns, no blocking calls
- **Documentation**: Inline comments and docstrings

## Educational Value

Phase 3 demonstrates:
- **Modern terminal UI** development with Textual
- **Async programming** with asyncio
- **WebSocket client** implementation
- **Callback patterns** for event-driven architecture
- **Real-time application** design
- **UI/logic separation** for maintainability

---

**Status**: ✅ Complete and ready for use
**Next**: Phase 4 - Group channels with key distribution
