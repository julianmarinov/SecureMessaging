#!/usr/bin/env python3
"""
User creation script for SecureMessaging.
Admin tool to manually create new users.
"""

import sys
import sqlite3
import getpass
from pathlib import Path
from argon2 import PasswordHasher
from cryptography.hazmat.primitives.asymmetric import x25519

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from client.crypto import KeyManager

def create_user(username: str, password: str, db_path: str = None):
    """
    Create a new user with identity keypair.

    Args:
        username: Username for the new account
        password: Password (will be hashed with Argon2)
        db_path: Path to server database (optional)
    """
    if not db_path:
        db_path = Path(__file__).parent.parent / "data" / "server" / "server.db"

    # Validate username
    if len(username) < 3:
        print("Error: Username must be at least 3 characters")
        return False

    if len(password) < 8:
        print("Error: Password must be at least 8 characters")
        return False

    # Generate identity keypair (X25519)
    print("Generating identity keypair...")
    private_key = x25519.X25519PrivateKey.generate()
    public_key = private_key.public_key()
    public_key_bytes = public_key.public_bytes_raw()

    # Hash password with Argon2
    print("Hashing password...")
    ph = PasswordHasher()
    password_hash = ph.hash(password)

    # Store in database
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute(
            """INSERT INTO users (username, password_hash, identity_public_key)
               VALUES (?, ?, ?)""",
            (username, password_hash, public_key_bytes)
        )

        conn.commit()
        user_id = cursor.lastrowid
        conn.close()

        print(f"\n✓ User '{username}' created successfully!")
        print(f"  User ID: {user_id}")
        print(f"  Public key fingerprint: {public_key_bytes.hex()[:16]}...")

        # Also create client database with encrypted private key
        client_db_path = Path(__file__).parent.parent / "data" / "client" / f"{username}.db"
        client_db_path.parent.mkdir(parents=True, exist_ok=True)

        key_manager = KeyManager(str(client_db_path))
        # Store the private key (encrypted with password)
        private_key_bytes = private_key.private_bytes_raw()
        key_manager._store_private_key(private_key_bytes, password)

        print(f"  Client database created: {client_db_path}")

        return True

    except sqlite3.IntegrityError:
        print(f"\nError: Username '{username}' already exists")
        return False

    except Exception as e:
        print(f"\nError creating user: {e}")
        return False

def main():
    """Main entry point."""
    print("SecureMessaging - Create User")
    print("-" * 40)

    # Get username
    if len(sys.argv) > 1:
        username = sys.argv[1]
    else:
        username = input("Username: ").strip()

    if not username:
        print("Error: Username is required")
        sys.exit(1)

    # Validate username length upfront
    while len(username) < 3:
        print("Error: Username must be at least 3 characters")
        username = input("Username: ").strip()
        if not username:
            print("Error: Username is required")
            sys.exit(1)

    # Get password with retry loop for validation
    max_attempts = 3
    for attempt in range(max_attempts):
        password = getpass.getpass("Password (min 8 characters): ")

        if not password:
            print("Error: Password is required")
            continue

        if len(password) < 8:
            remaining = max_attempts - attempt - 1
            if remaining > 0:
                print(f"Error: Password must be at least 8 characters. {remaining} attempts remaining.")
                continue
            else:
                print("Error: Too many failed attempts")
                sys.exit(1)

        password_confirm = getpass.getpass("Confirm password: ")

        if password != password_confirm:
            remaining = max_attempts - attempt - 1
            if remaining > 0:
                print(f"Error: Passwords do not match. {remaining} attempts remaining.")
                continue
            else:
                print("Error: Too many failed attempts")
                sys.exit(1)

        # Password is valid, break out of loop
        break
    else:
        # Loop completed without breaking (shouldn't happen but safety check)
        print("Error: Password validation failed")
        sys.exit(1)

    # Optional: custom database path
    db_path = None
    if len(sys.argv) > 2:
        db_path = sys.argv[2]

    # Create user
    success = create_user(username, password, db_path)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
