#!/usr/bin/env python3
"""
SecureMessaging TUI Client
Entry point for the Textual-based terminal UI.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from client.ui.app import main

if __name__ == "__main__":
    main()
