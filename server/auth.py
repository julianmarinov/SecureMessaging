"""
Authentication and session management for SecureMessaging server.
Handles password verification, session tokens, and user authentication.
"""

import secrets
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Tuple
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.constants import SESSION_TIMEOUT_HOURS, MAX_LOGIN_ATTEMPTS

class AuthManager:
    """Manages authentication and sessions."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.password_hasher = PasswordHasher()
        self.login_attempts = {}  # username -> (count, last_attempt_time)

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def verify_password(self, username: str, password: str) -> Tuple[bool, Optional[int], Optional[str]]:
        """
        Verify user credentials.

        Returns:
            (success, user_id, error_message)
        """
        # Check login attempts
        if username in self.login_attempts:
            count, last_attempt = self.login_attempts[username]
            if count >= MAX_LOGIN_ATTEMPTS:
                # Lock for 15 minutes after max attempts
                if datetime.now() - last_attempt < timedelta(minutes=15):
                    return False, None, "Too many failed attempts. Try again later."
                else:
                    # Reset counter after lockout period
                    del self.login_attempts[username]

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "SELECT user_id, password_hash FROM users WHERE username = ?",
                (username,)
            )
            row = cursor.fetchone()

            if not row:
                self._record_failed_attempt(username)
                return False, None, "Invalid username or password"

            user_id = row['user_id']
            password_hash = row['password_hash']

            try:
                # Verify password with Argon2
                self.password_hasher.verify(password_hash, password)

                # Check if rehashing is needed (argon2-cffi feature)
                if self.password_hasher.check_needs_rehash(password_hash):
                    new_hash = self.password_hasher.hash(password)
                    cursor.execute(
                        "UPDATE users SET password_hash = ? WHERE user_id = ?",
                        (new_hash, user_id)
                    )
                    conn.commit()

                # Clear failed attempts on success
                if username in self.login_attempts:
                    del self.login_attempts[username]

                return True, user_id, None

            except VerifyMismatchError:
                self._record_failed_attempt(username)
                return False, None, "Invalid username or password"

        finally:
            conn.close()

    def _record_failed_attempt(self, username: str):
        """Record a failed login attempt."""
        if username in self.login_attempts:
            count, _ = self.login_attempts[username]
            self.login_attempts[username] = (count + 1, datetime.now())
        else:
            self.login_attempts[username] = (1, datetime.now())

    def create_session(self, user_id: int) -> str:
        """
        Create a new session for authenticated user.

        Returns:
            session token
        """
        session_id = secrets.token_urlsafe(32)
        token = secrets.token_urlsafe(64)
        expires_at = datetime.now() + timedelta(hours=SESSION_TIMEOUT_HOURS)

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """INSERT INTO sessions (session_id, user_id, token, expires_at)
                   VALUES (?, ?, ?, ?)""",
                (session_id, user_id, token, expires_at)
            )

            # Update last_seen
            cursor.execute(
                "UPDATE users SET last_seen = CURRENT_TIMESTAMP WHERE user_id = ?",
                (user_id,)
            )

            conn.commit()
            return token

        finally:
            conn.close()

    def verify_token(self, token: str) -> Tuple[bool, Optional[int], Optional[str]]:
        """
        Verify session token.

        Returns:
            (valid, user_id, username)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """SELECT s.user_id, s.expires_at, u.username
                   FROM sessions s
                   JOIN users u ON s.user_id = u.user_id
                   WHERE s.token = ?""",
                (token,)
            )
            row = cursor.fetchone()

            if not row:
                return False, None, None

            user_id = row['user_id']
            username = row['username']
            expires_at = datetime.fromisoformat(row['expires_at'])

            if datetime.now() > expires_at:
                # Session expired, clean it up
                self._delete_session(token)
                return False, None, None

            # Update last_seen
            cursor.execute(
                "UPDATE users SET last_seen = CURRENT_TIMESTAMP WHERE user_id = ?",
                (user_id,)
            )
            conn.commit()

            return True, user_id, username

        finally:
            conn.close()

    def _delete_session(self, token: str):
        """Delete expired session."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
            conn.commit()
        finally:
            conn.close()

    def delete_session(self, token: str):
        """Logout - delete session."""
        self._delete_session(token)

    def cleanup_expired_sessions(self):
        """Remove all expired sessions from database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM sessions WHERE expires_at < ?",
                (datetime.now(),)
            )
            deleted = cursor.rowcount
            conn.commit()
            return deleted
        finally:
            conn.close()

    def get_user_info(self, user_id: int) -> Optional[dict]:
        """Get user information by user_id."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT user_id, username, identity_public_key, created_at, last_seen FROM users WHERE user_id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        finally:
            conn.close()

    def get_user_by_username(self, username: str) -> Optional[dict]:
        """Get user information by username."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT user_id, username, identity_public_key, created_at, last_seen FROM users WHERE username = ?",
                (username,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        finally:
            conn.close()
