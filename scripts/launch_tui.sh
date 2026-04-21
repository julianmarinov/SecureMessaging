#!/bin/bash
# Launch the SecureMessaging TUI client

cd "$(dirname "$0")/.."
source .venv/bin/activate

python client/main.py "$@"
