"""
Server storage operations for SecureMessaging.
Handles database operations for messages, channels, files, etc.
"""

import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any
import json

class ServerStorage:
    """Manages server-side database operations."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # Message operations
    def store_message(
        self,
        sender_id: int,
        recipient_id: Optional[int] = None,
        channel_id: Optional[int] = None,
        encrypted_payload: Optional[Any] = None,  # Can be dict or bytes
        plaintext: Optional[str] = None  # Phase 1 only
    ) -> int:
        """
        Store a message in the database.

        Returns:
            message_id
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Determine payload to store
            if encrypted_payload:
                # Phase 2: encrypted payload (dict or bytes)
                if isinstance(encrypted_payload, dict):
                    payload = json.dumps(encrypted_payload).encode('utf-8')
                else:
                    payload = encrypted_payload
            elif plaintext:
                # Phase 1: plaintext compatibility
                payload = json.dumps({"plaintext": plaintext}).encode('utf-8')
            else:
                payload = b''

            cursor.execute(
                """INSERT INTO messages (sender_id, recipient_id, channel_id, encrypted_payload)
                   VALUES (?, ?, ?, ?)""",
                (sender_id, recipient_id, channel_id, payload)
            )
            message_id = cursor.lastrowid
            conn.commit()
            return message_id

        finally:
            conn.close()

    def get_undelivered_messages(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all undelivered messages for a user."""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """SELECT m.message_id, m.sender_id, m.recipient_id, m.channel_id,
                          m.encrypted_payload, m.timestamp, u.username as sender
                   FROM messages m
                   JOIN users u ON m.sender_id = u.user_id
                   WHERE (m.recipient_id = ? OR m.channel_id IN (
                       SELECT channel_id FROM channel_members WHERE user_id = ?
                   ))
                   AND m.delivered = FALSE
                   ORDER BY m.timestamp ASC""",
                (user_id, user_id)
            )

            messages = []
            for row in cursor.fetchall():
                msg = dict(row)
                # Decode payload (supports both Phase 1 plaintext and Phase 2 encrypted)
                try:
                    payload_data = json.loads(msg['encrypted_payload'])
                    # Check if it's plaintext (Phase 1) or encrypted (Phase 2)
                    if 'plaintext' in payload_data:
                        msg['plaintext'] = payload_data['plaintext']
                        msg['encrypted_payload'] = None
                    else:
                        # It's an encrypted payload dict
                        msg['encrypted_payload'] = payload_data
                        msg['plaintext'] = None
                except (json.JSONDecodeError, TypeError, UnicodeDecodeError):
                    # Failed to decode, keep as bytes (binary encrypted payload)
                    pass
                messages.append(msg)

            return messages

        finally:
            conn.close()

    def mark_message_delivered(self, message_id: int, user_id: int) -> bool:
        """
        Mark a message as delivered if user is the recipient.

        Returns:
            True if message was marked, False if unauthorized
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            # Verify user is the recipient or a member of the channel
            cursor.execute(
                """UPDATE messages SET delivered = TRUE
                   WHERE message_id = ? AND (
                       recipient_id = ? OR
                       channel_id IN (SELECT channel_id FROM channel_members WHERE user_id = ?)
                   )""",
                (message_id, user_id, user_id)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def mark_message_read(self, message_id: int, user_id: int) -> bool:
        """
        Mark a message as read if user is the recipient.

        Returns:
            True if message was marked, False if unauthorized
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            # Verify user is the recipient or a member of the channel
            cursor.execute(
                """UPDATE messages SET read = TRUE
                   WHERE message_id = ? AND (
                       recipient_id = ? OR
                       channel_id IN (SELECT channel_id FROM channel_members WHERE user_id = ?)
                   )""",
                (message_id, user_id, user_id)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # Channel operations
    def create_channel(self, channel_name: str, created_by: int) -> Optional[int]:
        """
        Create a new channel.

        Returns:
            channel_id or None if channel already exists
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "INSERT INTO channels (channel_name, created_by) VALUES (?, ?)",
                (channel_name, created_by)
            )
            channel_id = cursor.lastrowid
            conn.commit()
            return channel_id

        except sqlite3.IntegrityError:
            # Channel name already exists
            return None

        finally:
            conn.close()

    def get_channel_id(self, channel_name: str) -> Optional[int]:
        """Get channel ID by name."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT channel_id FROM channels WHERE channel_name = ?",
                (channel_name,)
            )
            row = cursor.fetchone()
            return row['channel_id'] if row else None
        finally:
            conn.close()

    def get_channel_info(self, channel_id: int) -> Optional[Dict[str, Any]]:
        """Get channel information."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """SELECT c.channel_id, c.channel_name, c.created_by, c.created_at,
                          u.username as creator
                   FROM channels c
                   JOIN users u ON c.created_by = u.user_id
                   WHERE c.channel_id = ?""",
                (channel_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_all_channels(self) -> List[Dict[str, Any]]:
        """List all channels."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """SELECT c.channel_id, c.channel_name, c.created_by, c.created_at,
                          u.username as creator,
                          COUNT(cm.user_id) as member_count
                   FROM channels c
                   JOIN users u ON c.created_by = u.user_id
                   LEFT JOIN channel_members cm ON c.channel_id = cm.channel_id
                   GROUP BY c.channel_id
                   ORDER BY c.channel_name"""
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def add_channel_member(
        self,
        channel_id: int,
        user_id: int,
        encrypted_channel_key: bytes
    ) -> bool:
        """
        Add a user to a channel.

        Returns:
            True if successful, False if already a member
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """INSERT INTO channel_members (channel_id, user_id, encrypted_channel_key)
                   VALUES (?, ?, ?)""",
                (channel_id, user_id, encrypted_channel_key)
            )
            conn.commit()
            return True

        except sqlite3.IntegrityError:
            # Already a member
            return False

        finally:
            conn.close()

    def remove_channel_member(self, channel_id: int, user_id: int):
        """Remove a user from a channel."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM channel_members WHERE channel_id = ? AND user_id = ?",
                (channel_id, user_id)
            )
            conn.commit()
        finally:
            conn.close()

    def get_channel_members(self, channel_id: int) -> List[int]:
        """Get list of user IDs in a channel."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT user_id FROM channel_members WHERE channel_id = ?",
                (channel_id,)
            )
            return [row['user_id'] for row in cursor.fetchall()]
        finally:
            conn.close()

    def is_channel_member(self, channel_id: int, user_id: int) -> bool:
        """Check if user is a member of a channel."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT 1 FROM channel_members WHERE channel_id = ? AND user_id = ?",
                (channel_id, user_id)
            )
            return cursor.fetchone() is not None
        finally:
            conn.close()

    def get_user_channel_key(self, channel_id: int, user_id: int) -> Optional[bytes]:
        """Get a user's encrypted channel key."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT encrypted_channel_key FROM channel_members WHERE channel_id = ? AND user_id = ?",
                (channel_id, user_id)
            )
            row = cursor.fetchone()
            return row['encrypted_channel_key'] if row else None
        finally:
            conn.close()

    def get_user_channels(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all channels a user is a member of."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """SELECT c.channel_id, c.channel_name, c.created_by, c.created_at,
                          u.username as creator,
                          COUNT(cm.user_id) as member_count
                   FROM channels c
                   JOIN users u ON c.created_by = u.user_id
                   LEFT JOIN channel_members cm ON c.channel_id = cm.channel_id
                   WHERE c.channel_id IN (
                       SELECT channel_id FROM channel_members WHERE user_id = ?
                   )
                   GROUP BY c.channel_id
                   ORDER BY c.channel_name""",
                (user_id,)
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    # User operations
    def get_user_id(self, username: str) -> Optional[int]:
        """Get user ID by username."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT user_id FROM users WHERE username = ?", (username,))
            row = cursor.fetchone()
            return row['user_id'] if row else None
        finally:
            conn.close()

    def get_username(self, user_id: int) -> Optional[str]:
        """Get username by user ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return row['username'] if row else None
        finally:
            conn.close()

    def get_public_key(self, username: str) -> Optional[bytes]:
        """Get user's public identity key."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT identity_public_key FROM users WHERE username = ?",
                (username,)
            )
            row = cursor.fetchone()
            return row['identity_public_key'] if row else None
        finally:
            conn.close()

    def list_online_users(self, minutes: int = 5) -> List[str]:
        """
        Get list of recently active users.

        Args:
            minutes: Consider users active if seen within this many minutes

        Returns:
            List of usernames
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """SELECT username FROM users
                   WHERE last_seen >= datetime('now', '-' || ? || ' minutes')
                   ORDER BY username""",
                (minutes,)
            )
            return [row['username'] for row in cursor.fetchall()]
        finally:
            conn.close()

    # File operations (for future phases)
    def store_file(
        self,
        file_id: str,
        uploader_id: int,
        encrypted_data: bytes,
        filename_hint: str,
        size_bytes: int
    ) -> bool:
        """Store an encrypted file."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """INSERT INTO files (file_id, uploader_id, encrypted_data, filename_hint, size_bytes)
                   VALUES (?, ?, ?, ?, ?)""",
                (file_id, uploader_id, encrypted_data, filename_hint, size_bytes)
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    def get_file(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve an encrypted file."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """SELECT file_id, uploader_id, encrypted_data, filename_hint,
                          size_bytes, uploaded_at
                   FROM files WHERE file_id = ?""",
                (file_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def is_file_accessible(self, file_id: str, user_id: int) -> bool:
        """
        Check if a user is authorized to access a file.

        A user can access a file if they are:
        - The uploader of the file
        - A recipient of a direct message containing this file
        - A member of a channel where this file was shared

        Returns:
            True if user is authorized to access the file
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            # Check if user is the uploader
            cursor.execute(
                "SELECT uploader_id FROM files WHERE file_id = ?",
                (file_id,)
            )
            row = cursor.fetchone()
            if not row:
                return False
            if row['uploader_id'] == user_id:
                return True

            # Check if user is a recipient of a file notification
            # This requires tracking file access in a separate table
            # For now, check if file was shared with user via messages table
            cursor.execute(
                """SELECT 1 FROM file_access
                   WHERE file_id = ? AND user_id = ?""",
                (file_id, user_id)
            )
            if cursor.fetchone():
                return True

            return False
        finally:
            conn.close()

    def grant_file_access(self, file_id: str, user_id: int):
        """Grant a user access to download a file."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO file_access (file_id, user_id) VALUES (?, ?)",
                (file_id, user_id)
            )
            conn.commit()
        finally:
            conn.close()
