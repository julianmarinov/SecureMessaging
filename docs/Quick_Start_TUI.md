# Quick Start: TUI Client

## Prerequisites

1. **Server must be running**
   ```bash
   # Check if running
   pgrep -f "server/server.py"

   # If not running, start it
   cd /home/julian/Claude/Projects/SecureMessaging
   source .venv/bin/activate
   python server/server.py
   ```

2. **User accounts must exist**
   ```bash
   # Check existing users
   sqlite3 data/server/server.db "SELECT username FROM users"

   # Create users if needed
   source .venv/bin/activate
   python scripts/create_user.py alice
   python scripts/create_user.py bob
   ```

## Launch TUI Client

```bash
cd /home/julian/Claude/Projects/SecureMessaging
./scripts/launch_tui.sh
```

## First Time Usage

### 1. Login Screen

```
┌─────────────────────────────────────────┐
│         SecureMessaging                 │
│  End-to-end encrypted terminal chat     │
│                                         │
│  Username:                              │
│  alice                                  │
│                                         │
│  Password:                              │
│  ••••••••                               │
│                                         │
│  [        Login        ]                │
└─────────────────────────────────────────┘
```

- Type your username
- Press Tab to move to password field
- Type your password (hidden)
- Press Enter or click Login button

### 2. Chat Screen

After successful login:

```
┌────────────────────────────────────────────────────────┐
│         SecureMessaging - alice                        │
├──────────────┬─────────────────────────────────────────┤
│ Conversations│                                         │
│              │                                         │
│              │                                         │
│              │                                         │
│              │                                         │
├──────────────┼─────────────────────────────────────────┤
│              │ Type a message (Ctrl+N for new chat):  │
│              │ @bob Hello Bob!                         │
├──────────────┴─────────────────────────────────────────┤
│ Ready                                                  │
└────────────────────────────────────────────────────────┘
```

### 3. Start Your First Conversation

Type: `@bob Hello Bob!`

This will:
- Start a new conversation with bob
- Send the encrypted message
- Add bob to your conversation list
- Show the message in the chat area

### 4. Continue Chatting

Once a conversation is selected:
- Just type your message and press Enter
- No need to use @username again
- Messages are automatically encrypted

### 5. Switch Conversations

Click on any username in the sidebar to switch conversations.

## Example Session

**Terminal 1 (Alice):**
```
Login as: alice
Password: ****

> @bob Hey Bob, how's it going?
> Great! Want to grab lunch?
```

**Terminal 2 (Bob):**
```
Login as: bob
Password: ****

[Receives] Hey Bob, how's it going?
> @alice Pretty good! Sure, where do you want to go?

[Receives] Great! Want to grab lunch?
> How about that new pizza place?
```

## Features to Try

1. **Real-time delivery**: Send messages and see them appear instantly
2. **Encryption**: Look for 🔒 emoji on encrypted messages
3. **Multiple conversations**: Chat with different users simultaneously
4. **Status updates**: See when users come online/offline
5. **Conversation switching**: Click usernames in sidebar

## Keyboard Shortcuts

- **Enter**: Send message / Submit login
- **Tab**: Move between fields (login screen)
- **Escape**: Quit application
- **Ctrl+N**: New conversation (shows help)
- **Ctrl+C**: Quit (alternative to Escape)

## Tips

- Always start new conversations with `@username message`
- Your messages appear on the right (slightly different color)
- Received messages appear on the left
- Timestamps show when messages were sent
- The status bar at the bottom shows notifications

## Troubleshooting

**"Failed to connect"**
- Make sure server is running
- Check your username and password
- Verify Tailscale connection if using Tailscale network

**"No conversation selected"**
- Use `@username message` to start a new chat
- Or click on an existing conversation in the sidebar

**"Could not get public key"**
- The recipient user doesn't exist
- Check the username spelling
- Make sure the recipient has logged in at least once

## Testing Real-Time Messaging

1. Open **two terminal windows** side by side
2. Run the TUI client in each: `./scripts/launch_tui.sh`
3. Login as **different users** (alice and bob)
4. Send messages between them
5. Watch messages appear in real-time!

## Next Steps

- Try chatting with multiple users
- Test sending longer messages
- Observe the encryption indicators
- Check out the Phase 4 features when available (group channels)

---

**Have fun chatting securely!** 🔒
