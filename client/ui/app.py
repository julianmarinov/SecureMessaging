"""
Main Textual application for SecureMessaging client.
"""

import asyncio
from typing import Optional
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from textual.app import App
from textual.binding import Binding

from client.ui.screens import LoginScreen, ChatScreen
from client.connection import ConnectionManager


class SecureMessagingApp(App):
    """Secure Messaging TUI Application."""

    TITLE = "SecureMessaging"
    CSS_PATH = None  # CSS is inline in screens

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=False),
    ]

    def __init__(self, server_url: str = "ws://localhost:3005"):
        super().__init__()
        self.server_url = server_url
        self.connection: Optional[ConnectionManager] = None
        self.chat_screen: Optional[ChatScreen] = None
        self.username: Optional[str] = None

    def on_mount(self) -> None:
        """Show login screen on start."""
        self.push_screen(LoginScreen(self.server_url))

    def action_login(self, username: str, password: str, server_url: str) -> None:
        """Handle login action."""
        self.username = username

        # Create connection manager
        self.connection = ConnectionManager(server_url, username, password)

        # Set up callbacks
        self.connection.set_callbacks(
            on_message=self.handle_message,
            on_status=self.handle_status,
            on_typing=self.handle_typing,
            on_error=self.handle_error,
            on_channel_created=self.handle_channel_created,
            on_channel_joined=self.handle_channel_joined,
            on_file_available=self.handle_file_available,
            on_channels_list=self.handle_channels_list,
            on_message_delivered=self.handle_message_delivered,
            on_users_list=self.handle_users_list
        )

        # Start connection in background
        asyncio.create_task(self.connect_to_server())

    async def connect_to_server(self) -> None:
        """Connect to the server and transition to chat screen."""
        success = await self.connection.connect()

        if success:
            # Switch to chat screen
            self.chat_screen = ChatScreen(self.username)
            self.switch_screen(self.chat_screen)
        else:
            # Show error on login screen
            login_screen = self.screen
            if isinstance(login_screen, LoginScreen):
                login_screen.show_error("Failed to connect. Check credentials and try again.")

    def action_send_message(self, recipient: Optional[str] = None, channel: Optional[str] = None, message: str = "") -> None:
        """Send a message."""
        if not self.connection or not self.connection.authenticated:
            if self.chat_screen:
                self.chat_screen.show_status("Not connected")
            return

        # Add to UI immediately (optimistic update)
        if self.chat_screen:
            self.chat_screen.add_message(
                sender=self.username,
                message=message,
                timestamp=time.time(),
                is_encrypted=True,
                is_outgoing=True,
                channel=channel
            )

        # Send via connection
        asyncio.create_task(self.connection.send_message(recipient=recipient, channel=channel, text=message))

    def action_create_channel(self, channel_name: str) -> None:
        """Create a new channel."""
        if not self.connection or not self.connection.authenticated:
            if self.chat_screen:
                self.chat_screen.show_status("Not connected")
            return

        # Show status
        if self.chat_screen:
            self.chat_screen.show_status(f"Creating channel #{channel_name}...")

        # Create channel
        asyncio.create_task(self.connection.create_channel(channel_name))

    async def handle_message(
        self,
        sender: str,
        recipient: Optional[str],
        channel: Optional[str],
        message: str,
        timestamp: float,
        is_encrypted: bool,
        message_id: Optional[int] = None
    ) -> None:
        """Handle incoming message."""
        if self.chat_screen:
            # Show channel messages or direct messages to us
            if channel:
                # Channel message
                self.chat_screen.add_message(
                    sender=sender,
                    message=message,
                    timestamp=timestamp,
                    is_encrypted=is_encrypted,
                    is_outgoing=False,
                    channel=channel,
                    message_id=message_id
                )

                # Auto-select channel if not set
                if not self.chat_screen.current_conversation:
                    self.chat_screen.select_conversation(channel)

            elif recipient == self.username:
                # Direct message to us
                self.chat_screen.add_message(
                    sender=sender,
                    message=message,
                    timestamp=timestamp,
                    is_encrypted=is_encrypted,
                    is_outgoing=False,
                    message_id=message_id
                )

                # Auto-select conversation if not set
                if not self.chat_screen.current_conversation:
                    self.chat_screen.select_conversation(sender)

    async def handle_status(self, username: str, online: bool) -> None:
        """Handle user status change."""
        if self.chat_screen:
            status = "online" if online else "offline"
            self.chat_screen.show_status(f"{username} is now {status}")

    async def handle_typing(self, username: str, recipient: Optional[str], channel: Optional[str]) -> None:
        """Handle typing indicator."""
        if self.chat_screen and recipient == self.username:
            self.chat_screen.show_status(f"{username} is typing...")

    async def handle_error(self, error: str) -> None:
        """Handle connection error."""
        if self.chat_screen:
            self.chat_screen.show_status(f"Error: {error}")
        else:
            # On login screen
            login_screen = self.screen
            if isinstance(login_screen, LoginScreen):
                login_screen.show_error(error)

    async def handle_channel_created(self, channel_id: int, channel_name: str) -> None:
        """Handle channel created confirmation."""
        if self.chat_screen:
            self.chat_screen.show_status(f"Channel #{channel_name} created!")
            # Add to channels and select it
            self.chat_screen.channels.add(channel_name)
            self.chat_screen.conversations[channel_name] = []
            self.chat_screen.update_conversation_list()
            self.chat_screen.select_conversation(channel_name)

    async def handle_channel_joined(self, channel_id: int, channel_name: str) -> None:
        """Handle channel joined confirmation."""
        if self.chat_screen:
            self.chat_screen.show_status(f"Joined channel #{channel_name}!")
            # Add to channels
            self.chat_screen.channels.add(channel_name)
            self.chat_screen.conversations[channel_name] = []
            self.chat_screen.update_conversation_list()
            self.chat_screen.select_conversation(channel_name)

    async def handle_file_available(self, file_id: str, sender: str, filename: str, size_bytes: int, conversation: str) -> None:
        """Handle file available notification."""
        if self.chat_screen:
            # Add a message about the file
            from client.crypto.file_encryption import FileEncryptor
            size_str = FileEncryptor.format_file_size(size_bytes)

            self.chat_screen.add_message(
                sender=sender,
                message=f"📎 File available: {filename} ({size_str}) - Use /download {file_id} to download",
                timestamp=time.time(),
                is_encrypted=True,
                is_outgoing=False,
                channel=conversation if conversation in self.chat_screen.channels else None
            )

    def action_upload_file(self, file_path: str, recipient: Optional[str] = None, channel: Optional[str] = None) -> None:
        """Upload a file."""
        if not self.connection or not self.connection.authenticated:
            if self.chat_screen:
                self.chat_screen.show_status("Not connected")
            return

        # Check if file exists
        import os
        if not os.path.isfile(file_path):
            if self.chat_screen:
                self.chat_screen.show_status(f"File not found: {file_path}")
            return

        # Show status
        if self.chat_screen:
            self.chat_screen.show_status(f"Uploading {os.path.basename(file_path)}...")

        # Upload file
        asyncio.create_task(self.connection.upload_file(file_path, recipient=recipient, channel=channel))

    def action_download_file(self, file_id: str) -> None:
        """Download a file."""
        if not self.connection or not self.connection.authenticated:
            if self.chat_screen:
                self.chat_screen.show_status("Not connected")
            return

        # Show status
        if self.chat_screen:
            self.chat_screen.show_status(f"Downloading file {file_id}...")

        # Download file
        asyncio.create_task(self.connection.download_file(file_id))

    def action_mark_message_read(self, message_id: int) -> None:
        """Mark a message as read."""
        if not self.connection or not self.connection.authenticated:
            return

        # Send read receipt to server
        asyncio.create_task(self._send_read_receipt(message_id))

    async def _send_read_receipt(self, message_id: int):
        """Send read receipt to server."""
        if self.connection and self.connection.websocket:
            from shared.protocol import message_read_msg
            msg = message_read_msg(message_id)
            await self.connection.websocket.send(msg.to_json())

    def action_list_channels(self) -> None:
        """Request list of all channels."""
        if not self.connection or not self.connection.authenticated:
            if self.chat_screen:
                self.chat_screen.show_status("Not connected")
            return

        asyncio.create_task(self.connection.list_channels())

    async def handle_channels_list(self, channels: list) -> None:
        """Handle channels list response."""
        if self.chat_screen:
            if not channels:
                self.chat_screen.show_status("No channels available")
                return

            # Format channels list
            channel_info = "Available Channels:\n"
            for ch in channels:
                name = ch.get('channel_name', 'unknown')
                creator = ch.get('creator', 'unknown')
                member_count = ch.get('member_count', 0)
                channel_info += f"  #{name} - created by {creator} - {member_count} members\n"

            # Show as system message
            self.chat_screen.add_message(
                sender="System",
                message=channel_info.strip(),
                timestamp=time.time(),
                is_encrypted=False,
                is_outgoing=False
            )
            self.chat_screen.show_status(f"Found {len(channels)} channels")

    def action_list_users(self) -> None:
        """Request list of online users."""
        if not self.connection or not self.connection.authenticated:
            if self.chat_screen:
                self.chat_screen.show_status("Not connected")
            return

        asyncio.create_task(self.connection.list_users())

    async def handle_users_list(self, users: list) -> None:
        """Handle users list response."""
        if self.chat_screen:
            if not users:
                self.chat_screen.show_status("No users online")
                return

            # Format users list
            users_info = "Online Users:\n"
            for user in users:
                # Mark current user
                marker = " (you)" if user == self.username else ""
                users_info += f"  • {user}{marker}\n"

            # Show as system message
            self.chat_screen.add_message(
                sender="System",
                message=users_info.strip(),
                timestamp=time.time(),
                is_encrypted=False,
                is_outgoing=False
            )
            self.chat_screen.show_status(f"Found {len(users)} online users")

    async def handle_message_delivered(self, message_id: int) -> None:
        """Handle message delivered confirmation."""
        if self.chat_screen:
            self.chat_screen.mark_message_delivered(message_id)

    async def action_quit(self) -> None:
        """Quit the application."""
        if self.connection:
            await self.connection.disconnect()
        self.exit()


def main():
    """Entry point for the TUI client."""
    import sys
    import os

    # Server URL priority: CLI argument > environment variable > default
    default_url = "ws://localhost:3005"
    server_url = os.environ.get('SECURE_MESSAGING_SERVER', default_url)

    if len(sys.argv) > 1:
        server_url = sys.argv[1]

    app = SecureMessagingApp(server_url=server_url)
    app.run()


if __name__ == "__main__":
    main()
