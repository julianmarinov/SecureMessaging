"""
Textual UI screens for SecureMessaging client.
"""

from typing import Optional
from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Header, Footer, Input, Button, Static, Label
from textual.binding import Binding
from textual.reactive import reactive


class LoginScreen(Screen):
    """Login screen for authentication."""

    BINDINGS = [
        Binding("escape", "app.quit", "Quit"),
    ]

    CSS = """
    LoginScreen {
        align: center middle;
    }

    #login_container {
        width: 60;
        height: auto;
        border: solid $accent;
        background: $surface;
        padding: 2 4;
    }

    #login_title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    #login_subtitle {
        text-align: center;
        color: $text-muted;
        margin-bottom: 2;
    }

    .input_label {
        margin-top: 1;
        margin-bottom: 1;
        color: $text;
    }

    Input {
        margin-bottom: 1;
    }

    #login_button {
        width: 100%;
        margin-top: 1;
    }

    #error_message {
        color: $error;
        text-align: center;
        margin-top: 1;
        height: auto;
    }

    #status_message {
        color: $success;
        text-align: center;
        margin-top: 1;
        height: auto;
    }
    """

    def __init__(self, server_url: str = "ws://100.96.169.49:3005"):
        super().__init__()
        self.server_url = server_url

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header()
        with Container(id="login_container"):
            yield Label("SecureMessaging", id="login_title")
            yield Label("End-to-end encrypted terminal chat", id="login_subtitle")

            yield Label("Username:", classes="input_label")
            yield Input(placeholder="Enter username", id="username_input")

            yield Label("Password:", classes="input_label")
            yield Input(placeholder="Enter password", password=True, id="password_input")

            yield Button("Login", variant="primary", id="login_button")

            yield Label("", id="error_message")
            yield Label("", id="status_message")

        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle login button press."""
        if event.button.id == "login_button":
            self.attempt_login()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in input fields."""
        self.attempt_login()

    def attempt_login(self) -> None:
        """Attempt to log in with provided credentials."""
        username_input = self.query_one("#username_input", Input)
        password_input = self.query_one("#password_input", Input)

        username = username_input.value.strip()
        password = password_input.value

        # Clear error/status messages
        self.query_one("#error_message", Label).update("")
        self.query_one("#status_message", Label).update("")

        # Validate input
        if not username:
            self.show_error("Username is required")
            return

        if not password:
            self.show_error("Password is required")
            return

        # Show connecting status
        self.show_status("Connecting...")

        # Notify app to connect
        self.app.action_login(username, password, self.server_url)

    def show_error(self, message: str) -> None:
        """Display error message."""
        self.query_one("#error_message", Label).update(message)
        self.query_one("#status_message", Label).update("")

    def show_status(self, message: str) -> None:
        """Display status message."""
        self.query_one("#status_message", Label).update(message)
        self.query_one("#error_message", Label).update("")


class ChatScreen(Screen):
    """Main chat interface."""

    BINDINGS = [
        Binding("escape", "quit_prompt", "Quit"),
        Binding("ctrl+n", "new_conversation", "New Chat"),
    ]

    CSS = """
    ChatScreen {
        layout: grid;
        grid-size: 4 12;
        grid-columns: 1fr 3fr;
        grid-rows: auto 1fr auto;
    }

    #chat_header {
        column-span: 2;
        height: 3;
        background: $accent;
        color: $text;
        content-align: center middle;
        text-style: bold;
    }

    #sidebar {
        row-span: 10;
        border-right: solid $accent;
        background: $surface;
        padding: 1;
    }

    #conversation_list_title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    #conversation_list {
        height: 1fr;
        overflow-y: auto;
    }

    .conversation_item {
        padding: 1;
        margin-bottom: 1;
        background: $boost;
        color: $text;
    }

    .conversation_item:hover {
        background: $accent-darken-1;
    }

    .conversation_item_selected {
        background: $accent;
        color: $text;
        text-style: bold;
    }

    #messages_container {
        row-span: 8;
        height: 1fr;
        overflow-y: auto;
        padding: 1;
        background: $background;
    }

    .message {
        margin-bottom: 1;
        padding: 1;
        width: 100%;
    }

    .message_received {
        background: $surface;
        color: $text;
    }

    .message_sent {
        background: $accent-darken-1;
        color: $text;
    }

    .message_header {
        color: $text-muted;
        text-style: italic;
    }

    .message_encrypted {
        color: $success;
    }

    #input_container {
        row-span: 2;
        height: auto;
        background: $surface;
        padding: 1;
    }

    #input_label {
        color: $text-muted;
        margin-bottom: 1;
    }

    #message_input {
        width: 100%;
    }

    #status_bar {
        column-span: 2;
        height: 1;
        background: $boost;
        color: $text-muted;
        content-align: center middle;
    }
    """

    def __init__(self, username: str):
        super().__init__()
        self.username = username
        self.current_conversation = None
        self.conversations = {}  # {username/channel: [messages]}
        self.channels = set()  # Set of channel names we're in
        self.typing_users = set()
        self.unread_counts = {}  # {conversation: unread_count}

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Static(f"SecureMessaging - {self.username}", id="chat_header")

        # Sidebar with conversation list
        with Container(id="sidebar"):
            yield Label("Conversations", id="conversation_list_title")
            yield Container(id="conversation_list")

        # Messages area
        yield Container(id="messages_container")

        # Input area
        with Container(id="input_container"):
            yield Label("@user msg | #channel msg | /create #name | /upload <file>:", id="input_label")
            yield Input(placeholder="Enter message...", id="message_input")

        # Status bar
        yield Static("Ready", id="status_bar")

    def on_mount(self) -> None:
        """Called when screen is mounted."""
        self.query_one("#message_input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle message submission."""
        if event.input.id == "message_input":
            self.send_message()

    def send_message(self) -> None:
        """Send the typed message."""
        message_input = self.query_one("#message_input", Input)
        text = message_input.value.strip()

        if not text:
            return

        # Check for /create #channel command
        if text.startswith('/create '):
            parts = text.split(' ', 1)
            if len(parts) == 2 and parts[1].startswith('#'):
                channel_name = parts[1][1:]  # Remove #
                message_input.value = ""
                self.app.action_create_channel(channel_name)
                return
            else:
                self.show_status("Format: /create #channelname")
                return

        # Check for /upload <filepath> command
        if text.startswith('/upload '):
            parts = text.split(' ', 1)
            if len(parts) == 2:
                file_path = parts[1].strip()
                message_input.value = ""

                if not self.current_conversation:
                    self.show_status("Select a conversation first")
                    return

                # Determine if uploading to channel or DM
                if self.current_conversation in self.channels:
                    self.app.action_upload_file(file_path=file_path, channel=self.current_conversation)
                else:
                    self.app.action_upload_file(file_path=file_path, recipient=self.current_conversation)
                return
            else:
                self.show_status("Format: /upload /path/to/file")
                return

        # Check for /download <file_id> command
        if text.startswith('/download '):
            parts = text.split(' ', 1)
            if len(parts) == 2:
                file_id = parts[1].strip()
                message_input.value = ""
                self.app.action_download_file(file_id)
                return
            else:
                self.show_status("Format: /download <file_id>")
                return

        # Check for /help command
        if text == '/help':
            message_input.value = ""
            self.show_help()
            return

        # Check for /list command
        if text == '/list':
            message_input.value = ""
            self.app.action_list_channels()
            return

        # Check for /users or /online command
        if text == '/users' or text == '/online':
            message_input.value = ""
            self.app.action_list_users()
            return

        # Check if message starts with @username (new DM conversation)
        if text.startswith('@'):
            parts = text.split(' ', 1)
            if len(parts) >= 2:
                recipient = parts[0][1:]  # Remove @
                message_text = parts[1]

                # Start conversation with this user
                if recipient not in self.conversations:
                    self.conversations[recipient] = []
                    self.update_conversation_list()

                self.select_conversation(recipient)

                # Clear input
                message_input.value = ""

                # Send message
                self.app.action_send_message(recipient=recipient, message=message_text)
                return
            else:
                self.show_status("Format: @username message")
                return

        # Check if message starts with #channel (channel message)
        if text.startswith('#'):
            parts = text.split(' ', 1)
            if len(parts) >= 2:
                channel = parts[0][1:]  # Remove #
                message_text = parts[1]

                # Select channel conversation
                if channel not in self.conversations:
                    self.conversations[channel] = []
                    self.channels.add(channel)
                    self.update_conversation_list()

                self.select_conversation(channel)

                # Clear input
                message_input.value = ""

                # Send message
                self.app.action_send_message(channel=channel, message=message_text)
                return
            else:
                self.show_status("Format: #channel message")
                return

        if not self.current_conversation:
            self.show_status("No conversation selected. Use @user or #channel to start.")
            return

        # Clear input
        message_input.value = ""

        # Determine if current conversation is a channel or DM
        if self.current_conversation in self.channels:
            self.app.action_send_message(channel=self.current_conversation, message=text)
        else:
            self.app.action_send_message(recipient=self.current_conversation, message=text)

    def add_message(
        self,
        sender: str,
        message: str,
        timestamp: float,
        is_encrypted: bool = False,
        is_outgoing: bool = False,
        channel: Optional[str] = None,
        message_id: Optional[int] = None
    ) -> None:
        """Add a message to the display."""
        # Determine conversation key
        if channel:
            conversation_key = channel
            # Mark as channel
            if channel not in self.channels:
                self.channels.add(channel)
        elif is_outgoing:
            conversation_key = self.current_conversation
        else:
            conversation_key = sender

        if conversation_key not in self.conversations:
            self.conversations[conversation_key] = []
            self.unread_counts[conversation_key] = 0
            self.update_conversation_list()

        self.conversations[conversation_key].append({
            'sender': sender,
            'message': message,
            'timestamp': timestamp,
            'is_encrypted': is_encrypted,
            'is_outgoing': is_outgoing,
            'message_id': message_id,
            'delivered': False,  # For outgoing messages
            'read': False  # For outgoing messages
        })

        # Update unread count for incoming messages
        if not is_outgoing and conversation_key != self.current_conversation:
            self.unread_counts[conversation_key] = self.unread_counts.get(conversation_key, 0) + 1
            self.update_conversation_list()

        # Update display if this is the current conversation
        if conversation_key == self.current_conversation:
            self.refresh_messages()

            # Mark incoming messages as read and clear unread count
            if not is_outgoing and message_id:
                self.unread_counts[conversation_key] = 0
                self.update_conversation_list()
                self.app.action_mark_message_read(message_id)

    def refresh_messages(self) -> None:
        """Refresh the message display for current conversation."""
        if not self.current_conversation:
            return

        messages_container = self.query_one("#messages_container", Container)
        messages_container.remove_children()

        messages = self.conversations.get(self.current_conversation, [])

        for msg in messages:
            from datetime import datetime
            dt = datetime.fromtimestamp(msg['timestamp'])
            time_str = dt.strftime("%H:%M:%S")

            is_outgoing = msg['is_outgoing']
            sender_label = "You" if is_outgoing else msg['sender']
            encrypted_mark = " 🔒" if msg['is_encrypted'] else ""

            # Delivery/read receipt indicators for outgoing messages
            status_indicator = ""
            if is_outgoing:
                if msg.get('read'):
                    status_indicator = " ✓✓"  # Double checkmark for read
                elif msg.get('delivered'):
                    status_indicator = " ✓"   # Single checkmark for delivered

            header = f"[{time_str}] {sender_label}{encrypted_mark}{status_indicator}"
            message_class = "message_sent" if is_outgoing else "message_received"

            message_widget = Static(
                f"{header}\n{msg['message']}",
                classes=f"message {message_class}"
            )
            messages_container.mount(message_widget)

        # Scroll to bottom
        messages_container.scroll_end(animate=False)

    def update_conversation_list(self) -> None:
        """Update the list of conversations."""
        conv_list = self.query_one("#conversation_list", Container)

        # Use Textual's built-in method to remove all children synchronously
        if conv_list.children:
            conv_list.remove_children()

        # Separate channels and DMs
        channels_list = [name for name in self.conversations.keys() if name in self.channels]
        dms_list = [name for name in self.conversations.keys() if name not in self.channels]

        # Collect all widgets to mount at once
        widgets_to_mount = []

        # Show channels first
        for idx, channel in enumerate(sorted(channels_list)):
            is_selected = channel == self.current_conversation
            class_name = "conversation_item_selected" if is_selected else "conversation_item"

            # Add unread indicator
            unread = self.unread_counts.get(channel, 0)
            unread_badge = f" ({unread})" if unread > 0 and not is_selected else ""
            display_name = f"#{channel}{unread_badge}"

            # Use index to ensure unique IDs
            item = Button(display_name, classes=class_name, id=f"conv_ch_{idx}_{channel}")
            item.data_name = channel  # Store actual name for lookup
            widgets_to_mount.append(item)

        # Then show DMs
        for idx, username in enumerate(sorted(dms_list)):
            is_selected = username == self.current_conversation
            class_name = "conversation_item_selected" if is_selected else "conversation_item"

            # Add unread indicator
            unread = self.unread_counts.get(username, 0)
            unread_badge = f" ({unread})" if unread > 0 and not is_selected else ""
            display_name = f"{username}{unread_badge}"

            # Use index to ensure unique IDs
            item = Button(display_name, classes=class_name, id=f"conv_dm_{idx}_{username}")
            item.data_name = username  # Store actual name for lookup
            widgets_to_mount.append(item)

        # Mount all widgets at once
        if widgets_to_mount:
            conv_list.mount(*widgets_to_mount)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle clicking on conversation items."""
        button = event.button
        if button.id and button.id.startswith("conv_"):
            # Use stored data_name attribute instead of parsing ID
            name = getattr(button, 'data_name', None)
            if name and name in self.conversations:
                self.select_conversation(name)

    def select_conversation(self, name: str) -> None:
        """Select a conversation to view."""
        self.current_conversation = name

        # Clear unread count when selecting conversation
        if name in self.unread_counts:
            self.unread_counts[name] = 0

        self.update_conversation_list()
        self.refresh_messages()

        # Update input label
        if name in self.channels:
            self.query_one("#input_label", Label).update(f"To #{name}:")
        else:
            self.query_one("#input_label", Label).update(f"To {name}:")

    def show_status(self, message: str) -> None:
        """Update status bar."""
        self.query_one("#status_bar", Static).update(message)

    def action_new_conversation(self) -> None:
        """Start a new conversation."""
        # This would show a dialog to enter username
        # For now, just show a status message
        self.show_status("Enter recipient username in the input field (format: @username message)")

    def action_quit_prompt(self) -> None:
        """Show quit confirmation."""
        self.app.action_quit()

    def mark_message_delivered(self, message_id: int):
        """Mark a specific message as delivered in the conversation history."""
        # Find and mark the message
        for conversation in self.conversations.values():
            for msg in conversation:
                if msg.get('message_id') == message_id and msg.get('is_outgoing'):
                    msg['delivered'] = True

        # Refresh display if needed
        if self.current_conversation:
            self.refresh_messages()

    def mark_message_read(self, message_id: int):
        """Mark a specific message as read in the conversation history."""
        # Find and mark the message
        for conversation in self.conversations.values():
            for msg in conversation:
                if msg.get('message_id') == message_id and msg.get('is_outgoing'):
                    msg['delivered'] = True  # Read implies delivered
                    msg['read'] = True

        # Refresh display if needed
        if self.current_conversation:
            self.refresh_messages()

    def show_help(self):
        """Display help information."""
        help_text = """
╔════════════════════════════════════════════════════════╗
║           SecureMessaging - Command Reference          ║
╠════════════════════════════════════════════════════════╣
║ MESSAGING                                              ║
║   @user message       Send encrypted DM                ║
║   #channel message    Send to channel                  ║
║                                                        ║
║ CHANNELS                                               ║
║   /create #name       Create new channel               ║
║   /list               List all available channels      ║
║                                                        ║
║ FILES                                                  ║
║   /upload <path>      Upload encrypted file            ║
║   /download <id>      Download file                    ║
║                                                        ║
║ USERS                                                  ║
║   /users              List online users                ║
║   /online             Same as /users                   ║
║                                                        ║
║ NAVIGATION                                             ║
║   Click conversation  Switch to that chat              ║
║   ESC                 Quit application                 ║
║                                                        ║
║ INDICATORS                                             ║
║   🔒  Message encrypted                                ║
║   ✓   Message delivered                                ║
║   ✓✓  Message read                                     ║
║   📎  File available                                   ║
╚════════════════════════════════════════════════════════╝
"""
        self.show_status("Help displayed - see messages above")
        # Add help as a system message
        import time
        self.add_message(
            sender="System",
            message=help_text,
            timestamp=time.time(),
            is_encrypted=False,
            is_outgoing=False
        )
