#!/usr/bin/env python3
"""
Phase 2 Encryption Tests for SecureMessaging.
Verifies E2E encryption works correctly.
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import websockets
from shared.protocol import Message, MessageType
from client.crypto import KeyManager, ECDHKeyExchange

async def test_key_generation():
    """Test key generation and storage."""
    print("Test 1: Key Generation & Storage")
    print("-" * 40)

    try:
        # Create temporary key manager
        db_path = "/tmp/test_keymanager.db"
        Path(db_path).unlink(missing_ok=True)

        key_manager = KeyManager(db_path)

        # Generate keypair
        public_key, private_key_bytes = key_manager.generate_identity_keypair("testpassword")
        print(f"✓ Generated keypair")
        print(f"  Public key: {public_key.hex()[:32]}...")

        # Try to load with correct password
        private_key = key_manager.load_private_key("testpassword")
        if private_key:
            print("✓ Loaded private key with correct password")
        else:
            print("✗ Failed to load private key")
            return False

        # Try to load with wrong password
        wrong_key = key_manager.load_private_key("wrongpassword")
        if wrong_key is None:
            print("✓ Rejected wrong password")
        else:
            print("✗ Accepted wrong password (security issue!)")
            return False

        # Cleanup
        Path(db_path).unlink(missing_ok=True)

        print("✓ Key generation tests passed\n")
        return True

    except Exception as e:
        print(f"✗ Key generation test failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False

async def test_encryption_decryption():
    """Test message encryption and decryption."""
    print("Test 2: Encryption & Decryption")
    print("-" * 40)

    try:
        # Create two key managers
        alice_db = "/tmp/test_alice.db"
        bob_db = "/tmp/test_bob.db"
        Path(alice_db).unlink(missing_ok=True)
        Path(bob_db).unlink(missing_ok=True)

        alice_km = KeyManager(alice_db)
        bob_km = KeyManager(bob_db)

        # Generate keypairs
        alice_public, _ = alice_km.generate_identity_keypair("alice123")
        bob_public, _ = bob_km.generate_identity_keypair("bob123")

        # Load private keys
        alice_private = alice_km.load_private_key("alice123")
        bob_private = bob_km.load_private_key("bob123")

        print("✓ Generated keypairs for Alice and Bob")

        # Alice encrypts message for Bob
        alice_ephemeral, _ = alice_km.generate_ephemeral_keypair()
        test_message = "Hello Bob, this is a secret message!"

        encrypted = ECDHKeyExchange.encrypt_for_recipient(
            test_message,
            bob_public,
            alice_ephemeral
        )

        print(f"✓ Alice encrypted message")
        print(f"  Ephemeral key: {encrypted['ephemeral_public_key'][:32]}...")
        print(f"  Ciphertext: {encrypted['ciphertext'][:32]}...")

        # Bob decrypts message
        decrypted = ECDHKeyExchange.decrypt_from_sender(
            encrypted,
            bob_private
        )

        if decrypted == test_message:
            print(f"✓ Bob decrypted correctly: \"{decrypted}\"")
        else:
            print(f"✗ Decryption mismatch!")
            print(f"  Expected: {test_message}")
            print(f"  Got: {decrypted}")
            return False

        # Test that Alice cannot decrypt (wrong key)
        try:
            wrong_decrypt = ECDHKeyExchange.decrypt_from_sender(
                encrypted,
                alice_private  # Alice tries to decrypt her own message
            )
            print("✗ Alice was able to decrypt (should fail!)")
            return False
        except Exception:
            print("✓ Alice cannot decrypt message (as expected)")

        # Cleanup
        Path(alice_db).unlink(missing_ok=True)
        Path(bob_db).unlink(missing_ok=True)

        print("✓ Encryption/decryption tests passed\n")
        return True

    except Exception as e:
        print(f"✗ Encryption test failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False

async def test_e2e_messaging():
    """Test end-to-end encrypted messaging through server."""
    print("Test 3: E2E Encrypted Messaging")
    print("-" * 40)

    try:
        # Setup key managers for alice and bob
        alice_db = Path(__file__).parent.parent / "data" / "client" / "alice.db"
        bob_db = Path(__file__).parent.parent / "data" / "client" / "bob.db"

        alice_km = KeyManager(str(alice_db))
        bob_km = KeyManager(str(bob_db))

        # Generate or load keys
        if not alice_km.has_identity_key():
            alice_km.generate_identity_keypair("testpass123")
        if not bob_km.has_identity_key():
            bob_km.generate_identity_keypair("testpass456")

        alice_private = alice_km.load_private_key("testpass123")
        bob_private = bob_km.load_private_key("testpass456")

        print("✓ Loaded Alice and Bob's keys")

        # Connect both clients
        alice_ws = await websockets.connect("ws://100.96.169.49:3005")
        bob_ws = await websockets.connect("ws://100.96.169.49:3005")

        # Authenticate Alice
        msg = Message(MessageType.AUTHENTICATE, username="alice", password="testpass123")
        await alice_ws.send(msg.to_json())
        response = Message.from_json(await alice_ws.recv())
        alice_token = response.get('token')
        print("✓ Alice authenticated")

        # Authenticate Bob
        msg = Message(MessageType.AUTHENTICATE, username="bob", password="testpass456")
        await bob_ws.send(msg.to_json())
        response = Message.from_json(await bob_ws.recv())
        bob_token = response.get('token')
        print("✓ Bob authenticated")

        # Wait for user_status broadcasts
        await asyncio.sleep(0.5)

        # Alice gets Bob's public key from server
        msg = Message(MessageType.REQUEST_PUBLIC_KEY, auth_token=alice_token, username="bob")
        await alice_ws.send(msg.to_json())

        # Wait for public key response
        bob_public_key = None
        for _ in range(5):
            response_str = await asyncio.wait_for(alice_ws.recv(), timeout=2.0)
            response = Message.from_json(response_str)
            if response.type == MessageType.PUBLIC_KEY_RESPONSE:
                import base64
                bob_public_key = base64.b64decode(response.get('public_key'))
                print(f"✓ Alice received Bob's public key")
                break

        if not bob_public_key:
            print("✗ Failed to get Bob's public key")
            return False

        # Alice encrypts message for Bob
        alice_ephemeral, _ = alice_km.generate_ephemeral_keypair()
        test_message = "This is an encrypted test message!"

        encrypted_payload = ECDHKeyExchange.encrypt_for_recipient(
            test_message,
            bob_public_key,
            alice_ephemeral
        )

        print(f"✓ Alice encrypted message")

        # Alice sends encrypted message
        msg = Message(
            MessageType.SEND_MESSAGE,
            auth_token=alice_token,
            recipient="bob",
            encrypted_payload=encrypted_payload
        )
        await alice_ws.send(msg.to_json())
        print("✓ Alice sent encrypted message")

        # Bob receives encrypted message
        received = None
        for _ in range(10):
            response_str = await asyncio.wait_for(bob_ws.recv(), timeout=2.0)
            response = Message.from_json(response_str)
            if response.type == MessageType.NEW_MESSAGE:
                received = response
                break

        if not received:
            print("✗ Bob did not receive message")
            return False

        print("✓ Bob received encrypted message")

        # Bob decrypts message
        encrypted_payload_received = received.get('encrypted_payload')
        if not encrypted_payload_received:
            print("✗ No encrypted payload in received message")
            return False

        decrypted = ECDHKeyExchange.decrypt_from_sender(
            encrypted_payload_received,
            bob_private
        )

        if decrypted == test_message:
            print(f"✓ Bob decrypted correctly: \"{decrypted}\"")
        else:
            print(f"✗ Decryption mismatch!")
            print(f"  Expected: {test_message}")
            print(f"  Got: {decrypted}")
            await alice_ws.close()
            await bob_ws.close()
            return False

        await alice_ws.close()
        await bob_ws.close()

        print("✓ E2E encrypted messaging test passed\n")
        return True

    except Exception as e:
        print(f"✗ E2E messaging test failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all encryption tests."""
    print("\n" + "=" * 40)
    print("SecureMessaging Phase 2 Encryption Tests")
    print("=" * 40 + "\n")

    results = []

    # Test 1: Key Generation
    results.append(await test_key_generation())

    # Test 2: Encryption/Decryption
    results.append(await test_encryption_decryption())

    # Test 3: E2E Messaging
    results.append(await test_e2e_messaging())

    # Summary
    print("=" * 40)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("✓ All encryption tests passed!")
        print("=" * 40 + "\n")
        return 0
    else:
        print("✗ Some tests failed")
        print("=" * 40 + "\n")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
