#!/usr/bin/env python3
"""
SecureMessaging Server
Main entry point for the WebSocket server.
"""

import asyncio
import logging
import signal
import json
import argparse
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import websockets
from server.auth import AuthManager
from server.storage import ServerStorage
from server.router import MessageRouter
from server.websocket_handler import WebSocketHandler
from shared.constants import DEFAULT_SERVER_HOST, DEFAULT_SERVER_PORT

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SecureMessagingServer:
    """Main server class."""

    def __init__(self, config_path: str = None):
        """Initialize server with configuration."""
        self.config = self._load_config(config_path)
        self.running = False
        self.server = None

        # Initialize components
        db_path = self.config['database']['path']
        self.auth_manager = AuthManager(db_path)
        self.storage = ServerStorage(db_path)
        self.router = MessageRouter(self.storage)
        self.handler = WebSocketHandler(self.auth_manager, self.storage, self.router)

        logger.info("Server components initialized")

    def _load_config(self, config_path: str = None) -> dict:
        """Load server configuration."""
        if config_path and Path(config_path).exists():
            with open(config_path, 'r') as f:
                config = json.load(f)
                logger.info(f"Loaded configuration from {config_path}")
                return config
        else:
            # Default configuration
            logger.info("Using default configuration")
            return {
                "server": {
                    "host": DEFAULT_SERVER_HOST,
                    "port": DEFAULT_SERVER_PORT,
                    "max_connections": 50
                },
                "database": {
                    "path": "data/server/server.db"
                },
                "security": {
                    "session_timeout_hours": 24,
                    "max_login_attempts": 5
                },
                "storage": {
                    "max_file_size_mb": 100,
                    "file_storage_path": "data/server/files"
                },
                "logging": {
                    "level": "INFO",
                    "file": "data/server/server.log"
                }
            }

    async def start(self):
        """Start the WebSocket server."""
        host = self.config['server']['host']
        port = self.config['server']['port']

        logger.info(f"Starting SecureMessaging server on {host}:{port}")

        try:
            # Start WebSocket server
            self.server = await websockets.serve(
                self.handler.handle_connection,
                host,
                port,
                ping_interval=30,
                ping_timeout=10
            )

            self.running = True
            logger.info(f"✓ Server running on ws://{host}:{port}")

            # Start cleanup task
            asyncio.create_task(self._cleanup_task())

            # Wait until server is stopped
            await self._wait_for_shutdown()

        except Exception as e:
            logger.error(f"Server error: {e}", exc_info=True)
            raise

    async def _cleanup_task(self):
        """Periodic cleanup of expired sessions."""
        while self.running:
            try:
                await asyncio.sleep(3600)  # Run every hour
                deleted = self.auth_manager.cleanup_expired_sessions()
                if deleted > 0:
                    logger.info(f"Cleaned up {deleted} expired sessions")
            except Exception as e:
                logger.error(f"Cleanup task error: {e}")

    async def _wait_for_shutdown(self):
        """Wait for shutdown signal."""
        # This will be interrupted by signal handlers
        while self.running:
            await asyncio.sleep(1)

    def stop(self):
        """Stop the server gracefully."""
        logger.info("Shutting down server...")
        self.running = False

        if self.server:
            self.server.close()

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='SecureMessaging Server')
    parser.add_argument(
        '--config',
        type=str,
        help='Path to configuration file',
        default='config/server_config.json'
    )
    parser.add_argument(
        '--host',
        type=str,
        help='Host to bind to (overrides config)',
        default=None
    )
    parser.add_argument(
        '--port',
        type=int,
        help='Port to bind to (overrides config)',
        default=None
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )

    args = parser.parse_args()

    # Set debug logging if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Create server instance
    server = SecureMessagingServer(args.config)

    # Override config with command-line arguments
    if args.host:
        server.config['server']['host'] = args.host
    if args.port:
        server.config['server']['port'] = args.port

    # Setup signal handlers
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}")
        server.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run server
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

    logger.info("Server stopped")

if __name__ == "__main__":
    main()
