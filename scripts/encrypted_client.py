#!/usr/bin/env python3
"""
Encrypted client for SecureMessaging (Phase 2).
Demonstrates E2E encryption with X25519 + ChaCha20-Poly1305.
"""

import asyncio
import base64
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import websockets
from shared.protocol import Message, MessageType
from client.crypto import KeyManager, MessageEncryptor, ECDHKeyExchange

class EncryptedClient:
    """E2E encrypted test client."""

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
        self.private_key = None

    async def connect(self):
        """Connect to the server."""
        print(f"Connecting to {self.server_url}...")
        self.websocket = await websockets.connect(self.server_url)
        print("✓ Connected!")
        self.running = True

    async def initialize_keys(self):
        """Initialize or load encryption keys."""
        if not self.key_manager.has_identity_key():
            print("Generating new identity keypair...")
            public_key, private_key = self.key_manager.generate_identity_keypair(self.password)
            print(f"✓ Identity keypair generated")
            print(f"  Public key fingerprint: {public_key.hex()[:16]}...")
        else:
            print("Loading existing identity key...")

        # Load private key
        self.private_key = self.key_manager.load_private_key(self.password)
        if not self.private_key:
            print("✗ Failed to load private key (wrong password?)")
            return False

        print("✓ Identity key loaded")
        return True

    async def authenticate(self):
        """Authenticate with the server."""
        print(f"Authenticating as {self.username}...")

        # Send authentication request
        msg = Message(MessageType.AUTHENTICATE, username=self.username, password=self.password)
        await self.websocket.send(msg.to_json())

        # Wait for response
        response_str = await self.websocket.recv()
        response = Message.from_json(response_str)

        if response.type == MessageType.AUTHENTICATED:
            self.token = response.get('token')
            self.authenticated = True
            print(f"✓ Authenticated as {self.username}")
            print(f"  Token: {self.token[:20]}...")
            return True
        else:
            error = response.get('error', 'Unknown error')
            print(f"✗ Authentication failed: {error}")
            return False

    async def get_public_key(self, username: str) -> bytes:
        """
        Get a user's public key (with caching).

        Args:
            username: Username to get key for

        Returns:
            Public key bytes
        """
        # Check cache first
        cached_key = self.key_manager.get_cached_public_key(username)
        if cached_key:
            return cached_key

        # Request from server
        msg = Message(MessageType.REQUEST_PUBLIC_KEY, auth_token=self.token, username=username)
        await self.websocket.send(msg.to_json())

        # Wait for response
        while True:
            response_str = await self.websocket.recv()
            response = Message.from_json(response_str)

            if response.type == MessageType.PUBLIC_KEY_RESPONSE:
                if response.get('username') == username:
                    public_key_b64 = response.get('public_key')
                    public_key = base64.b64decode(public_key_b64)

                    # Cache it
                    self.key_manager.cache_public_key(username, public_key)

                    return public_key
            elif response.type == MessageType.ERROR:
                print(f"Error getting public key: {response.get('error')}")
                return None

    async def send_encrypted_message(self, recipient: str, text: str):
        """
        Send an encrypted message.

        Args:
            recipient: Username to send to
            text: Plaintext message
        """
        if not self.authenticated:
            print("Error: Not authenticated")
            return

        # Get recipient's public key
        print(f"  Getting {recipient}'s public key...")
        recipient_public_key = await self.get_public_key(recipient)
        if not recipient_public_key:
            print(f"  Error: Could not get public key for {recipient}")
            return

        # Generate ephemeral keypair for Perfect Forward Secrecy
        ephemeral_private, ephemeral_public = self.key_manager.generate_ephemeral_keypair()

        # Encrypt message
        print(f"  Encrypting message...")
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

        await self.websocket.send(msg.to_json())
        print(f"→ Sent encrypted: \"{text}\" to {recipient}")

    async def receive_messages(self):
        """Receive and decrypt incoming messages."""
        try:
            async for message_str in self.websocket:
                message = Message.from_json(message_str)

                if message.type == MessageType.NEW_MESSAGE:
                    sender = message.get('sender')
                    encrypted_payload = message.get('encrypted_payload')

                    if encrypted_payload:
                        # Encrypted message - decrypt it
                        try:
                            plaintext = ECDHKeyExchange.decrypt_from_sender(
                                encrypted_payload,
                                self.private_key
                            )
                            print(f"\n← [ENCRYPTED] (DM from {sender}): {plaintext}")
                        except Exception as e:
                            print(f"\n← [ENCRYPTED - FAILED TO DECRYPT] from {sender}: {e}")
                    else:
                        # Plaintext (Phase 1 compatibility)
                        text = message.get('plaintext', '[no content]')
                        print(f"\n← (DM from {sender}): {text}")

                    # Send delivery confirmation
                    msg_id = message.get('message_id')
                    if msg_id:
                        confirm = Message(MessageType.MESSAGE_DELIVERED, message_id=msg_id)
                        await self.websocket.send(confirm.to_json())

                elif message.type == MessageType.USER_STATUS:
                    username = message.get('username')
                    online = message.get('online')
                    status = "online" if online else "offline"
                    print(f"\n• {username} is now {status}")

                elif message.type == MessageType.TYPING_INDICATOR:
                    username = message.get('username')
                    print(f"\n• {username} is typing...")

                elif message.type == MessageType.ERROR:
                    error = message.get('error')
                    print(f"\n✗ Error: {error}")

                # Re-print prompt
                if self.running:
                    print("> ", end='', flush=True)

        except websockets.exceptions.ConnectionClosed:
            print("\nConnection closed")
            self.running = False

    async def interactive_loop(self):
        """Interactive command loop."""
        print("\nCommands:")
        print("  /msg <user> <message>  - Send encrypted message")
        print("  /plain <user> <message> - Send plaintext (Phase 1 compat)")
        print("  /key <user>            - Get user's public key")
        print("  /quit                  - Disconnect")
        print()

        # Start message receiver in background
        receiver_task = asyncio.create_task(self.receive_messages())

        try:
            while self.running:
                try:
                    # Get user input
                    line = await asyncio.get_event_loop().run_in_executor(
                        None, input, "> "
                    )

                    if not line:
                        continue

                    # Parse command
                    if line.startswith('/msg '):
                        parts = line.split(' ', 2)
                        if len(parts) >= 3:
                            recipient = parts[1]
                            text = parts[2]
                            await self.send_encrypted_message(recipient, text)
                        else:
                            print("Usage: /msg <user> <message>")

                    elif line.startswith('/plain '):
                        # Plaintext for testing/Phase 1 compatibility
                        parts = line.split(' ', 2)
                        if len(parts) >= 3:
                            recipient = parts[1]
                            text = parts[2]
                            msg = Message(
                                MessageType.SEND_MESSAGE,
                                auth_token=self.token,
                                recipient=recipient,
                                plaintext=text
                            )
                            await self.websocket.send(msg.to_json())
                            print(f"→ Sent plaintext: {text}")
                        else:
                            print("Usage: /plain <user> <message>")

                    elif line.startswith('/key '):
                        username = line.split(' ', 1)[1]
                        public_key = await self.get_public_key(username)
                        if public_key:
                            print(f"{username}'s public key: {public_key.hex()}")

                    elif line == '/quit':
                        print("Disconnecting...")
                        self.running = False
                        break

                    else:
                        print("Unknown command. Available: /msg, /plain, /key, /quit")

                except EOFError:
                    break
                except KeyboardInterrupt:
                    break

        finally:
            receiver_task.cancel()
            await self.websocket.close()

    async def run(self):
        """Run the client."""
        try:
            # Initialize keys
            if not await self.initialize_keys():
                return

            # Connect and authenticate
            await self.connect()

            if await self.authenticate():
                await self.interactive_loop()

        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

async def main():
    """Main entry point."""
    if len(sys.argv) < 3:
        print("Usage: encrypted_client.py <username> <password> [server_url]")
        print("Example: encrypted_client.py alice mypassword ws://100.96.169.49:3005")
        sys.exit(1)

    username = sys.argv[1]
    password = sys.argv[2]
    server_url = sys.argv[3] if len(sys.argv) > 3 else "ws://100.96.169.49:3005"

    client = EncryptedClient(server_url, username, password)
    await client.run()

if __name__ == "__main__":
    asyncio.run(main())
