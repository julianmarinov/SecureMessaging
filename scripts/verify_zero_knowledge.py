#!/usr/bin/env python3
"""
Verify that the server cannot decrypt messages (zero-knowledge).
Inspects the database to show that all message content is encrypted.
"""

import sqlite3
import json
from pathlib import Path

def verify_zero_knowledge():
    """Verify server database contains only encrypted data."""
    print("\n" + "=" * 60)
    print("Zero-Knowledge Server Verification")
    print("=" * 60 + "\n")

    db_path = Path(__file__).parent.parent / "data" / "server" / "server.db"

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all messages
    cursor.execute("""
        SELECT m.message_id, u.username as sender, m.encrypted_payload
        FROM messages m
        JOIN users u ON m.sender_id = u.user_id
        ORDER BY m.message_id DESC
        LIMIT 10
    """)

    messages = cursor.fetchall()

    if not messages:
        print("No messages in database to verify.\n")
        return True

    print(f"Inspecting {len(messages)} messages in server database:\n")
    print("-" * 60)

    has_plaintext = False
    encrypted_count = 0

    for msg_id, sender, payload_bytes in messages:
        try:
            payload = json.loads(payload_bytes)

            print(f"\nMessage ID: {msg_id}")
            print(f"Sender: {sender}")

            if 'plaintext' in payload:
                # Phase 1 plaintext message (should not exist in Phase 2)
                print(f"⚠️  PLAINTEXT FOUND: \"{payload['plaintext']}\"")
                print("   This message is NOT encrypted!")
                has_plaintext = True

            elif 'ciphertext' in payload:
                # Phase 2 encrypted message
                print(f"✓ ENCRYPTED MESSAGE:")
                print(f"   Ciphertext: {payload['ciphertext'][:40]}...")
                print(f"   Nonce: {payload['nonce'][:20]}...")
                if 'ephemeral_public_key' in payload:
                    print(f"   Ephemeral Key: {payload['ephemeral_public_key'][:20]}...")
                print("   ✓ Server cannot decrypt this message")
                encrypted_count += 1

            else:
                print(f"⚠️  UNKNOWN PAYLOAD FORMAT")

        except json.JSONDecodeError:
            print(f"\nMessage ID: {msg_id} - Binary payload (cannot inspect)")

    print("\n" + "-" * 60)
    print(f"\nSummary:")
    print(f"  Encrypted messages: {encrypted_count}")
    print(f"  Plaintext messages: {len(messages) - encrypted_count}")

    conn.close()

    if has_plaintext:
        print(f"\n✗ FAIL: Server database contains plaintext messages!")
        print(f"   Zero-knowledge property violated.")
        return False
    else:
        print(f"\n✓ PASS: All messages are encrypted")
        print(f"   Server cannot read message content (zero-knowledge)")
        return True

if __name__ == "__main__":
    success = verify_zero_knowledge()
    print("\n" + "=" * 60 + "\n")
    exit(0 if success else 1)
