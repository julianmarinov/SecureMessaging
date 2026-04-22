#!/usr/bin/env python3
"""
Database initialization script for SecureMessaging.
Creates server and client database schemas.
"""

import sqlite3
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

def init_server_db(db_path: str):
    """Initialize server database with schema."""
    print(f"Initializing server database at {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            identity_public_key BLOB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP
        )
    """)

    # Sessions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    # Channels table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            channel_id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_name TEXT UNIQUE NOT NULL,
            created_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users(user_id)
        )
    """)

    # Channel members table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS channel_members (
            channel_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            encrypted_channel_key BLOB NOT NULL,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (channel_id, user_id),
            FOREIGN KEY (channel_id) REFERENCES channels(channel_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    # Messages table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            recipient_id INTEGER,
            channel_id INTEGER,
            encrypted_payload BLOB NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            delivered BOOLEAN DEFAULT FALSE,
            read BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (sender_id) REFERENCES users(user_id),
            FOREIGN KEY (recipient_id) REFERENCES users(user_id),
            FOREIGN KEY (channel_id) REFERENCES channels(channel_id)
        )
    """)

    # Files table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS files (
            file_id TEXT PRIMARY KEY,
            uploader_id INTEGER NOT NULL,
            encrypted_data BLOB NOT NULL,
            filename_hint TEXT,
            size_bytes INTEGER NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (uploader_id) REFERENCES users(user_id)
        )
    """)

    # File access control table (tracks who can download which files)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS file_access (
            file_id TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (file_id, user_id),
            FOREIGN KEY (file_id) REFERENCES files(file_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    # Login attempts table (for persistent rate limiting)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS login_attempts (
            username TEXT PRIMARY KEY,
            attempt_count INTEGER NOT NULL DEFAULT 0,
            last_attempt TIMESTAMP NOT NULL,
            locked_until TIMESTAMP
        )
    """)

    # Create indexes for performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_recipient ON messages(recipient_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_channel ON messages(channel_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at)")

    conn.commit()
    conn.close()
    print("✓ Server database initialized successfully")

def init_client_db(db_path: str):
    """Initialize client database schema (template)."""
    print(f"Initializing client database template at {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # User keys table (encrypted private keys)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_keys (
            key_type TEXT PRIMARY KEY,
            encrypted_key BLOB NOT NULL,
            salt BLOB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Public keys cache
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS public_keys (
            username TEXT PRIMARY KEY,
            public_key BLOB NOT NULL,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Channel keys
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS channel_keys (
            channel_name TEXT PRIMARY KEY,
            channel_key BLOB NOT NULL,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Messages (decrypted cache)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_name TEXT,
            recipient_username TEXT,
            sender_username TEXT NOT NULL,
            message_text TEXT NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            delivered BOOLEAN DEFAULT FALSE,
            read BOOLEAN DEFAULT FALSE
        )
    """)

    # Files
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS files (
            file_id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            file_key BLOB NOT NULL,
            local_path TEXT,
            size_bytes INTEGER,
            downloaded BOOLEAN DEFAULT FALSE
        )
    """)

    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_channel ON messages(channel_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_recipient ON messages(recipient_username)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)")

    conn.commit()
    conn.close()
    print("✓ Client database template initialized successfully")

def main():
    """Main initialization function."""
    project_root = Path(__file__).parent.parent

    # Initialize server database
    server_db_path = project_root / "data" / "server" / "server.db"
    server_db_path.parent.mkdir(parents=True, exist_ok=True)
    init_server_db(str(server_db_path))

    # Initialize client database template
    client_db_path = project_root / "data" / "client" / "template.db"
    client_db_path.parent.mkdir(parents=True, exist_ok=True)
    init_client_db(str(client_db_path))

    print("\n✓ All databases initialized successfully!")
    print(f"  Server DB: {server_db_path}")
    print(f"  Client template: {client_db_path}")

if __name__ == "__main__":
    main()
