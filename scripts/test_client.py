#!/usr/bin/env python3
"""
Simple test client for SecureMessaging (Phase 1).
Command-line interface for testing server functionality.
"""

import asyncio
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import websockets
from shared.protocol import Message, MessageType

class TestClient:
    """Simple test client for Phase 1."""

    def __init__(self, server_url: str):
        self.server_url = server_url
        self.websocket = None
        self.authenticated = False
        self.token = None
        self.username = None
        self.running = False

    async def connect(self):
        """Connect to the server."""
        print(f"Connecting to {self.server_url}...")
        self.websocket = await websockets.connect(self.server_url)
        print("✓ Connected!")
        self.running = True

    async def authenticate(self, username: str, password: str):
        """Authenticate with the server."""
        print(f"Authenticating as {username}...")

        # Send authentication request
        msg = Message(MessageType.AUTHENTICATE, username=username, password=password)
        await self.websocket.send(msg.to_json())

        # Wait for response
        response_str = await self.websocket.recv()
        response = Message.from_json(response_str)

        if response.type == MessageType.AUTHENTICATED:
            self.token = response.get('token')
            self.username = response.get('username')
            self.authenticated = True
            print(f"✓ Authenticated as {self.username}")
            print(f"  Token: {self.token[:20]}...")
            return True
        else:
            error = response.get('error', 'Unknown error')
            print(f"✗ Authentication failed: {error}")
            return False

    async def send_message(self, recipient: str = None, channel: str = None, text: str = ""):
        """Send a message."""
        if not self.authenticated:
            print("Error: Not authenticated")
            return

        msg = Message(
            MessageType.SEND_MESSAGE,
            auth_token=self.token,
            recipient=recipient,
            channel=channel,
            plaintext=text
        )

        await self.websocket.send(msg.to_json())
        print(f"→ Sent: {text}")

    async def receive_messages(self):
        """Receive and display incoming messages."""
        try:
            async for message_str in self.websocket:
                message = Message.from_json(message_str)

                if message.type == MessageType.NEW_MESSAGE:
                    sender = message.get('sender')
                    text = message.get('plaintext', '[encrypted]')
                    channel = message.get('channel')
                    recipient = message.get('recipient')

                    if channel:
                        print(f"\n← [{channel}] {sender}: {text}")
                    else:
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
        print("  /msg <user> <message>  - Send direct message")
        print("  /channel <name>        - Create/join channel")
        print("  /c <channel> <message> - Send channel message")
        print("  /list                  - List channels")
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
                            await self.send_message(recipient=recipient, text=text)
                        else:
                            print("Usage: /msg <user> <message>")

                    elif line.startswith('/c '):
                        parts = line.split(' ', 2)
                        if len(parts) >= 3:
                            channel = parts[1]
                            text = parts[2]
                            await self.send_message(channel=channel, text=text)
                        else:
                            print("Usage: /c <channel> <message>")

                    elif line.startswith('/channel '):
                        channel_name = line.split(' ', 1)[1]
                        msg = Message(
                            MessageType.CREATE_CHANNEL,
                            auth_token=self.token,
                            channel_name=channel_name
                        )
                        await self.websocket.send(msg.to_json())
                        print(f"Created channel: {channel_name}")

                    elif line == '/list':
                        msg = Message(MessageType.LIST_CHANNELS, auth_token=self.token)
                        await self.websocket.send(msg.to_json())

                    elif line == '/quit':
                        print("Disconnecting...")
                        self.running = False
                        break

                    else:
                        print("Unknown command. Available: /msg, /c, /channel, /list, /quit")

                except EOFError:
                    break
                except KeyboardInterrupt:
                    break

        finally:
            receiver_task.cancel()
            await self.websocket.close()

    async def run(self, username: str, password: str):
        """Run the client."""
        try:
            await self.connect()

            if await self.authenticate(username, password):
                await self.interactive_loop()

        except Exception as e:
            print(f"Error: {e}")

async def main():
    """Main entry point."""
    if len(sys.argv) < 3:
        print("Usage: test_client.py <username> <password> [server_url]")
        print("Example: test_client.py alice mypassword ws://100.96.169.49:3005")
        sys.exit(1)

    username = sys.argv[1]
    password = sys.argv[2]
    server_url = sys.argv[3] if len(sys.argv) > 3 else "ws://100.96.169.49:3005"

    client = TestClient(server_url)
    await client.run(username, password)

if __name__ == "__main__":
    asyncio.run(main())
