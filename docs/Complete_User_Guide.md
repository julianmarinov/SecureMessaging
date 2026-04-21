# SecureMessaging: Complete User Guide

## Table of Contents

1. [Getting Started](#getting-started)
2. [Basic Messaging](#basic-messaging)
3. [Group Channels](#group-channels)
4. [File Sharing](#file-sharing)
5. [Commands Reference](#commands-reference)
6. [Security Features](#security-features)
7. [Troubleshooting](#troubleshooting)

---

## Getting Started

### Prerequisites

- Server must be running
- User account created
- TUI client installed

### First Login

1. **Launch the client**:
   ```bash
   cd /home/julian/Claude/Projects/SecureMessaging
   ./scripts/launch_tui.sh
   ```

2. **Enter credentials**:
   - Username: your_username
   - Password: your_password

3. **Press Enter or click Login**

You're now connected and ready to chat securely!

---

## Basic Messaging

### Send a Direct Message

**First time chatting with someone:**
```
@bob Hello Bob!
```

**Continuing a conversation:**
```
Just type your message and press Enter
```

### Visual Indicators

- **🔒** = Message is encrypted
- **✓✓** = Message has been read (outgoing only)
- **You** = Your messages
- **Username** = Their messages

### Example Conversation

```
> @alice Hi Alice!

[Alice receives and reads]

[Your screen shows]
[12:34:56] You 🔒 ✓✓
Hi Alice!

← [ENCRYPTED] (DM from alice): Hi! How are you?

> I'm great, thanks!
```

---

## Group Channels

### Create a Channel

```
/create #general
```

This creates an encrypted channel named "general" and automatically adds you as a member.

### Send to a Channel

**Method 1:** Use # prefix
```
#general Hello everyone!
```

**Method 2:** Select channel first, then type
1. Click `#general` in sidebar
2. Type your message
3. Press Enter

### Channel vs DM

| Feature | DMs | Channels |
|---------|-----|----------|
| Prefix | @ | # |
| Recipients | One person | Multiple people |
| Encryption | ECDH (ephemeral keys) | Symmetric (shared key) |
| Read receipts | Yes ✓✓ | No |
| Example | `@bob Hi!` | `#general Hi!` |

---

## File Sharing

### Upload a File

**To a person (DM):**
```
> @bob Check out this photo
> /upload /home/user/photo.jpg
```

**To a channel:**
```
> #general Here's the document
> /upload /home/user/document.pdf
```

### Download a File

When someone shares a file, you'll see:
```
📎 File available: photo.jpg (2.5 MB) - Use /download abc123 to download
```

To download:
```
> /download abc123
```

File saved to: `data/client/downloads/your_username/`

### Supported File Types

All file types are supported:
- Documents: PDF, DOC, TXT
- Images: JPG, PNG, GIF
- Videos: MP4, AVI, MOV
- Archives: ZIP, TAR, GZ
- Any other file type

### File Security

- ✅ Files encrypted before upload
- ✅ Server cannot read file contents
- ✅ Integrity verified (SHA-256 hash)
- ✅ Automatic decryption on download
- ✅ Separate encryption key per file

---

## Commands Reference

### Messaging

| Command | Description | Example |
|---------|-------------|---------|
| `@user message` | Send DM | `@bob Hello!` |
| `#channel message` | Send to channel | `#general Hi all!` |
| Just type | Reply in current conversation | `How are you?` |

### Channels

| Command | Description | Example |
|---------|-------------|---------|
| `/create #name` | Create new channel | `/create #dev` |
| Click `#name` | Switch to channel | Click `#general` |

### File Sharing

| Command | Description | Example |
|---------|-------------|---------|
| `/upload <path>` | Upload file | `/upload ~/photo.jpg` |
| `/download <id>` | Download file | `/download abc123` |

### Navigation

| Command | Description |
|---------|-------------|
| Click conversation | Switch to that conversation |
| ESC | Quit application |
| Ctrl+C | Quit (alternative) |

---

## Security Features

### End-to-End Encryption

**Direct Messages:**
- Algorithm: X25519 ECDH + ChaCha20-Poly1305
- Perfect Forward Secrecy: New key for each message
- Server cannot decrypt: Zero-knowledge architecture

**Channel Messages:**
- Algorithm: Symmetric ChaCha20-Poly1305
- Shared key among members
- Server cannot decrypt: Stores encrypted keys only

**Files:**
- Random 32-byte key per file
- File key encrypted for each recipient
- Integrity verification with SHA-256

### What's Encrypted

✅ All message contents
✅ All file contents
✅ Channel keys (encrypted per-member)

### What's NOT Encrypted

❌ Usernames (visible to server)
❌ Channel names (visible to server)
❌ Timestamps (visible to server)
❌ Who's talking to whom (metadata)

### Privacy Features

- **Read receipts** only for DMs (not channels)
- **Local key storage** (encrypted with your password)
- **No message logging** on server (except encrypted)
- **No cloud sync** (everything local)

---

## Troubleshooting

### Cannot Connect

**Problem:** "Failed to connect"

**Solutions:**
1. Check server is running: `pgrep -f server.py`
2. Verify password is correct
3. Check Tailscale connection (if using Tailscale network)

### Cannot Decrypt Message

**Problem:** "[Failed to decrypt: ...]"

**Possible causes:**
1. Wrong password (can't load private key)
2. Corrupted key database
3. Key mismatch

**Solution:**
- For DMs: Keys auto-exchanged, should work automatically
- For channels: Must be member with channel key
- Try restarting client

### File Upload Fails

**Problem:** Upload not working

**Solutions:**
1. Check file exists: `ls -la /path/to/file`
2. Check file permissions: Must be readable
3. Select conversation first before uploading
4. Check server has space

### File Download Fails

**Problem:** Cannot download file

**Solutions:**
1. Check file_id is correct
2. Verify you have encryption keys (member of channel or recipient of DM)
3. Check downloads directory exists and is writable

### Channel Not Working

**Problem:** Cannot see channel messages

**Possible causes:**
1. Not a member of channel
2. Don't have channel key

**Solution:**
- Create the channel yourself: `/create #name`
- Get invited (manual process in current version)

### No Read Receipts

**Problem:** No ✓✓ appearing

**This is normal if:**
- Recipient hasn't viewed message yet
- Message is in a channel (no read receipts for channels)
- Message is incoming (only outgoing show ✓✓)

---

## Best Practices

### Security

1. **Use strong passwords**: 12+ characters, mixed case, numbers, symbols
2. **Keep keys safe**: Don't share your password or delete `data/client/username.db`
3. **Verify recipients**: Make sure you're sending to the right person
4. **Trust on first use**: Keys exchanged automatically, but verify identity out-of-band

### Performance

1. **Small files work best**: <10 MB for good performance
2. **Close old conversations**: Click on active ones only
3. **Restart periodically**: If UI becomes slow

### Organization

1. **Use descriptive channel names**: `#project-alpha` not `#abc`
2. **Create channels for teams**: Better than group DMs
3. **Upload files to channels**: Easier for multiple people to access

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Enter | Send message / Submit |
| Tab | Move between fields (login screen) |
| ESC | Quit application |
| Ctrl+C | Quit (alternative) |
| Ctrl+N | New conversation (shows help) |

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────┐
│          SECUREMESSAGING QUICK REFERENCE            │
├─────────────────────────────────────────────────────┤
│ DIRECT MESSAGES                                     │
│   @user message       Send DM                       │
│                                                     │
│ CHANNELS                                            │
│   /create #name       Create channel                │
│   #channel message    Send to channel               │
│                                                     │
│ FILES                                               │
│   /upload <path>      Upload file                   │
│   /download <id>      Download file                 │
│                                                     │
│ INDICATORS                                          │
│   🔒  Encrypted       ✓✓  Read                     │
│   #  Channel          @  Direct message             │
│   📎  File available                                │
│                                                     │
│ NAVIGATION                                          │
│   ESC                 Quit                          │
│   Click name          Switch conversation           │
└─────────────────────────────────────────────────────┘
```

---

## Getting Help

**In the app:**
- Check status bar for messages
- Error messages show in status bar

**Documentation:**
- `/docs/Quick_Start_TUI.md` - Basic getting started
- `/docs/Channel_Quick_Start.md` - Channel guide
- `/docs/Phase5_File_Sharing_And_Polish.md` - File sharing details

**Issues:**
- Server logs: Check server terminal for errors
- Client logs: Check client terminal for errors

---

## Example Workflows

### Scenario 1: Team Collaboration

1. Create project channel:
   ```
   /create #project-alpha
   ```

2. Share document:
   ```
   #project-alpha Here's the latest design
   /upload /home/user/design.pdf
   ```

3. Team downloads and discusses:
   ```
   /download abc123
   #project-alpha Looks great! Just one question...
   ```

### Scenario 2: Private Document Sharing

1. Start conversation:
   ```
   @bob I have that confidential report you asked for
   ```

2. Upload encrypted:
   ```
   /upload /home/user/confidential.pdf
   ```

3. Bob downloads:
   ```
   /download def456
   ```

4. Confirm receipt:
   ```
   @alice Got it, thanks! ✓✓
   ```

### Scenario 3: Quick Team Update

1. Send to team channel:
   ```
   #general Meeting at 3pm today in the conference room
   ```

2. Team sees message:
   ```
   ← [ENCRYPTED] (#general from alice): Meeting at 3pm...
   ```

3. No file uploads needed, just quick sync

---

**Enjoy secure, encrypted messaging!** 🔒
