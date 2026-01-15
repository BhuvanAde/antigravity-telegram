#!/bin/bash

# Kill any existing instances
pkill -f "src.main" || true

# Start the bridge in the background
nohup python3 -m src.main > bridge.log 2>&1 &

echo "🚀 Telegram Bridge started in background!"
echo "Logs are being written to: bridge.log"
echo "PID: $!"
