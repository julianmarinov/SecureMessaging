#!/usr/bin/env python3
"""
Integration test for SecureMessaging Phase 1.
Tests authentication, direct messaging, and channels.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import websockets
from shared.protocol import Message, MessageType

async def wait_for_message_type(websocket, msg_type: str, timeout: float = 5.0):
    """Wait for a specific message type, ignoring other messages."""
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        remaining = deadline - asyncio.get_event_loop().time()
        if remaining <= 0:
            raise asyncio.TimeoutError(f"Timeout waiting for {msg_type}")

        try:
            response_str = await asyncio.wait_for(websocket.recv(), timeout=remaining)
            response = Message.from_json(response_str)
            if response.type == msg_type:
                return response
            # Otherwise, ignore and continue waiting
        except asyncio.TimeoutError:
            raise asyncio.TimeoutError(f"Timeout waiting for {msg_type}")

async def test_authentication():
    """Test user authentication."""
    print("Test 1: Authentication")
    print("-" * 40)

    try:
        # Connect to server
        async with websockets.connect("ws://100.96.169.49:3005") as ws:
            # Test valid credentials
            msg = Message(MessageType.AUTHENTICATE, username="alice", password="testpass123")
            await ws.send(msg.to_json())

            response_str = await asyncio.wait_for(ws.recv(), timeout=5.0)
            response = Message.from_json(response_str)

            if response.type == MessageType.AUTHENTICATED:
                print("✓ Valid credentials accepted")
                print(f"  Token: {response.get('token')[:20]}...")
            else:
                print("✗ Valid credentials rejected")
                return False

        # Test invalid credentials
        async with websockets.connect("ws://100.96.169.49:3005") as ws:
            msg = Message(MessageType.AUTHENTICATE, username="alice", password="wrongpassword")
            await ws.send(msg.to_json())

            response_str = await asyncio.wait_for(ws.recv(), timeout=5.0)
            response = Message.from_json(response_str)

            if response.type == MessageType.AUTH_ERROR:
                print("✓ Invalid credentials rejected")
            else:
                print("✗ Invalid credentials accepted (security issue!)")
                return False

        print("✓ Authentication tests passed\n")
        return True

    except Exception as e:
        print(f"✗ Authentication test failed: {e}\n")
        return False

async def test_direct_messaging():
    """Test 1-to-1 messaging."""
    print("Test 2: Direct Messaging")
    print("-" * 40)

    try:
        # Connect as Alice
        alice_ws = await websockets.connect("ws://100.96.169.49:3005")
        msg = Message(MessageType.AUTHENTICATE, username="alice", password="testpass123")
        await alice_ws.send(msg.to_json())
        response = Message.from_json(await alice_ws.recv())
        alice_token = response.get('token')

        # Connect as Bob
        bob_ws = await websockets.connect("ws://100.96.169.49:3005")
        msg = Message(MessageType.AUTHENTICATE, username="bob", password="testpass456")
        await bob_ws.send(msg.to_json())
        response = Message.from_json(await bob_ws.recv())
        bob_token = response.get('token')

        # Alice sends message to Bob
        msg = Message(
            MessageType.SEND_MESSAGE,
            auth_token=alice_token,
            recipient="bob",
            plaintext="Hello Bob!"
        )
        await alice_ws.send(msg.to_json())

        # Bob should receive the message (ignore user_status broadcasts)
        response = await wait_for_message_type(bob_ws, MessageType.NEW_MESSAGE, timeout=5.0)

        if response.type == MessageType.NEW_MESSAGE:
            sender = response.get('sender')
            text = response.get('plaintext')
            if sender == "alice" and text == "Hello Bob!":
                print("✓ Direct message delivered correctly")
                print(f"  From: {sender}")
                print(f"  Text: {text}")
            else:
                print(f"✗ Message content incorrect: {sender} - {text}")
                await alice_ws.close()
                await bob_ws.close()
                return False
        else:
            print(f"✗ Expected NEW_MESSAGE, got {response.type}")
            await alice_ws.close()
            await bob_ws.close()
            return False

        await alice_ws.close()
        await bob_ws.close()
        print("✓ Direct messaging tests passed\n")
        return True

    except Exception as e:
        print(f"✗ Direct messaging test failed: {e}\n")
        return False

async def test_channels():
    """Test channel creation."""
    print("Test 3: Channel Creation")
    print("-" * 40)

    try:
        # Connect as Alice
        alice_ws = await websockets.connect("ws://100.96.169.49:3005")
        msg = Message(MessageType.AUTHENTICATE, username="alice", password="testpass123")
        await alice_ws.send(msg.to_json())
        response = Message.from_json(await alice_ws.recv())
        alice_token = response.get('token')
        print(f"  Alice authenticated, token: {alice_token[:20]}...")

        # Consume any user_status messages
        await asyncio.sleep(0.5)

        # Alice creates a channel
        print("  Sending CREATE_CHANNEL message...")
        channel_name = "testchannel"
        msg = Message(MessageType.CREATE_CHANNEL, auth_token=alice_token, channel_name=channel_name)
        await alice_ws.send(msg.to_json())
        print(f"  Sent: {msg.to_json()}")

        # Wait for response
        try:
            response = await wait_for_message_type(alice_ws, MessageType.CHANNEL_CREATED, timeout=5.0)
            channel_name = response.get('channel_name')
            print(f"✓ Channel '{channel_name}' created")
        except asyncio.TimeoutError as e:
            # Try to receive any message to see what we got
            try:
                any_msg = await asyncio.wait_for(alice_ws.recv(), timeout=1.0)
                print(f"  Got unexpected message: {any_msg}")
            except:
                pass
            raise e

        await alice_ws.close()
        print("✓ Channel tests passed\n")
        return True

    except Exception as e:
        print(f"✗ Channel test failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all integration tests."""
    print("\n" + "=" * 40)
    print("SecureMessaging Phase 1 Integration Tests")
    print("=" * 40 + "\n")

    results = []

    # Test 1: Authentication
    results.append(await test_authentication())

    # Test 2: Direct Messaging
    results.append(await test_direct_messaging())

    # Test 3: Channels
    results.append(await test_channels())

    # Summary
    print("=" * 40)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("✓ All tests passed!")
        print("=" * 40 + "\n")
        return 0
    else:
        print("✗ Some tests failed")
        print("=" * 40 + "\n")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
