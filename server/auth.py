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

# Dummy hash for timing attack prevention - pre-computed Argon2 hash
# This ensures consistent timing whether user exists or not
DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$YmFzZTY0c2FsdA$dummyhashfortimingtiming"

class AuthManager:
    """Manages authentication and sessions."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.password_hasher = PasswordHasher()
        self._ensure_login_attempts_table()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_login_attempts_table(self):
        """Ensure the login_attempts table exists."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS login_attempts (
                    username TEXT PRIMARY KEY,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    last_attempt TIMESTAMP NOT NULL,
                    locked_until TIMESTAMP
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def verify_password(self, username: str, password: str) -> Tuple[bool, Optional[int], Optional[str]]:
        """
        Verify user credentials.

        Returns:
            (success, user_id, error_message)
        """
        # Check login attempts from database (persistent across restarts)
        if self._is_account_locked(username):
            return False, None, "Too many failed attempts. Try again later."

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "SELECT user_id, password_hash FROM users WHERE username = ?",
                (username,)
            )
            row = cursor.fetchone()

            if not row:
                # Perform dummy verification to prevent timing attack
                # This ensures the response time is similar whether user exists or not
                try:
                    self.password_hasher.verify(DUMMY_HASH, password)
                except VerifyMismatchError:
                    pass  # Expected - just ensuring consistent timing
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
                self._clear_login_attempts(username)

                return True, user_id, None

            except VerifyMismatchError:
                self._record_failed_attempt(username)
                return False, None, "Invalid username or password"

        finally:
            conn.close()

    def _record_failed_attempt(self, username: str):
        """Record a failed login attempt in the database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            now = datetime.now()
            cursor.execute(
                """INSERT INTO login_attempts (username, attempt_count, last_attempt)
                   VALUES (?, 1, ?)
                   ON CONFLICT(username) DO UPDATE SET
                   attempt_count = attempt_count + 1,
                   last_attempt = ?,
                   locked_until = CASE
                       WHEN attempt_count + 1 >= ? THEN datetime(?, '+15 minutes')
                       ELSE locked_until
                   END""",
                (username, now, now, MAX_LOGIN_ATTEMPTS, now)
            )
            conn.commit()
        finally:
            conn.close()

    def _is_account_locked(self, username: str) -> bool:
        """Check if account is currently locked due to failed attempts."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """SELECT attempt_count, locked_until FROM login_attempts
                   WHERE username = ?""",
                (username,)
            )
            row = cursor.fetchone()
            if not row:
                return False

            # Check if locked and lock hasn't expired
            if row['locked_until']:
                locked_until = datetime.fromisoformat(row['locked_until'])
                if datetime.now() < locked_until:
                    return True
                else:
                    # Lock expired, clear the record
                    self._clear_login_attempts(username)
                    return False

            return False
        finally:
            conn.close()

    def _clear_login_attempts(self, username: str):
        """Clear login attempts after successful login or lockout expiry."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM login_attempts WHERE username = ?",
                (username,)
            )
            conn.commit()
        finally:
            conn.close()

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
