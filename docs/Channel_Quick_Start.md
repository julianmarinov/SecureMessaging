# Quick Start: Group Channels

## Creating Your First Channel

1. **Login to the TUI client**:
   ```bash
   ./scripts/launch_tui.sh
   ```

2. **Create a channel**:
   ```
   /create #general
   ```

3. **Channel appears in sidebar**:
   ```
   Conversations
   ┌────────────┐
   │ #general   │  ← Your new channel
   └────────────┘
   ```

4. **Send a message**:
   ```
   Welcome to #general!
   ```

## Sending Channel Messages

### Method 1: Select the channel first

1. Click on `#general` in the sidebar
2. Type your message and press Enter
3. Message is encrypted and sent to all members

### Method 2: Use #channel prefix

From anywhere, type:
```
#general Hello everyone!
```

This will:
- Switch to #general
- Send the message
- Add #general to your conversation list

## Channel vs Direct Messages

### Direct Messages (DMs)
- Start with `@username message`
- Encrypted with ECDH (Perfect Forward Secrecy)
- One recipient
- Example: `@alice Hello Alice!`

### Channels
- Start with `#channel message`
- Encrypted with symmetric key (shared among members)
- Multiple recipients
- Example: `#general Hello everyone!`

## How Channel Encryption Works

### Creating a Channel

```
You create #general:
┌─────────────────────────────────────────┐
│ 1. Generate random 32-byte channel key  │
│ 2. Encrypt key for yourself             │
│ 3. Send to server (server can't read)   │
│ 4. Store key locally                    │
└─────────────────────────────────────────┘
```

### Sending Messages

```
You send "Hello!" to #general:
┌─────────────────────────────────────────┐
│ 1. Get channel key from local storage   │
│ 2. Encrypt "Hello!" with channel key    │
│ 3. Send encrypted message to server     │
│ 4. Server broadcasts to all members     │
│ 5. Members decrypt with their key       │
└─────────────────────────────────────────┘
```

### Server Cannot Read

```
Server sees:
{
  "channel": "general",
  "encrypted_payload": {
    "ciphertext": "xK9mP...",  ← Gibberish
    "nonce": "aB3cD..."
  }
}

Server does NOT see:
"Hello!"  ← Your actual message
```

## Commands Summary

| Command | Description | Example |
|---------|-------------|---------|
| `/create #name` | Create new channel | `/create #general` |
| `#name message` | Send to channel | `#general Hi all!` |
| `@user message` | Send direct message | `@alice Hey!` |
| Click `#name` | Switch to channel | Click `#general` |
| ESC | Quit application | Press ESC key |

## Visual Indicators

### In Conversation List

```
Conversations
#general   ← Channel (# prefix)
#random
alice      ← Direct message (no prefix)
bob
```

### In Messages

```
[12:34:56] alice 🔒
Hello from #general!

🔒 = Encrypted message
```

## Multi-User Example

**Terminal 1 (Alice):**
```
Login as: alice
Password: ****

> /create #general
Channel #general created!

> Welcome to the channel!
→ Sent encrypted: "Welcome to the channel!" to #general
```

**Terminal 2 (Bob):**
```
Login as: bob
Password: ****

[Bob sees alice's message after joining]
← [ENCRYPTED] (#general from alice): Welcome to the channel!

> #general Hey Alice!
→ Sent encrypted: "Hey Alice!" to #general
```

**Terminal 1 (Alice):**
```
← [ENCRYPTED] (#general from bob): Hey Alice!

> #general How are you?
```

## Security Notes

### What's Encrypted

- ✅ All channel messages
- ✅ All direct messages
- ✅ Channel keys (encrypted per-member)

### What's NOT Encrypted

- ❌ Channel names (visible to server)
- ❌ Usernames (visible to server)
- ❌ Timestamps (visible to server)
- ❌ Who's talking to whom (metadata)

### Zero-Knowledge Server

- Server **routes** encrypted messages
- Server **stores** encrypted keys
- Server **cannot read** message contents
- Server **cannot read** channel keys

## Current Limitations

**Phase 4 limitations:**

1. **Manual joining**: No automatic invite system yet
   - Workaround: Share channel name and key out-of-band

2. **No member list**: Can't see who's in a channel
   - Workaround: Send a message and see who responds

3. **No key rotation**: Channel key never changes
   - Workaround: Create a new channel periodically

4. **No member removal**: Can't kick users
   - Workaround: Create a new channel without them

These will be addressed in Phase 5 and beyond.

## Troubleshooting

### "No key for channel #general"

You're not a member of this channel yet. Either:
- Create it: `/create #general`
- Join it: (manual process in Phase 4)

### "Not a member of #general"

You haven't joined this channel. The channel key is missing from your local storage.

### Channel messages not appearing

- Check you're connected (status bar shows "Ready")
- Verify other users are in the same channel
- Check server is running
- Try sending a test message

### Can't create channel (already exists)

Channel names are global and unique. Try:
- Different name: `/create #general2`
- Join existing: (manual in Phase 4)

## Best Practices

1. **Use descriptive names**: `#project-alpha` not `#abc`
2. **Test first**: Send a test message before important chats
3. **Check encryption**: Look for 🔒 emoji on messages
4. **Keep keys safe**: Your client database contains decrypted keys
5. **Use channels for groups**: More efficient than multiple DMs

## Next Steps

- **Create your first channel**: `/create #testing`
- **Invite friends**: (Share channel name)
- **Send encrypted messages**: `#testing Hello!`
- **Explore**: Try both DMs and channels

---

**Enjoy secure group messaging!** 🔒
