#!/bin/bash
# Start the hybrid Docker+AI bridge server
# Run this before starting Cowrie

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[+] Starting hybrid bridge server..."

# Make sure Docker container is running
if ! docker ps | grep -q "fake-ubuntu"; then
    echo "[*] Starting fake-ubuntu Docker container..."
    docker start fake-ubuntu
    sleep 2
fi

echo "[+] Docker container: running"

# Kill any existing bridge server
pkill -f "bridge_server.py" 2>/dev/null
sleep 1

# Start bridge server
cd "$SCRIPT_DIR"
source /home/faizan/cowrie/cowrie-env/bin/activate
python3 bridge_server.py &

BRIDGE_PID=$!
echo "[+] Bridge server started (PID: $BRIDGE_PID)"
echo $BRIDGE_PID > /tmp/bridge_server.pid

sleep 2

# Verify it's listening
if nc -z 127.0.0.1 5050 2>/dev/null; then
    echo "[+] Bridge server listening on 127.0.0.1:5050"
else
    echo "[-] Bridge server failed to start!"
    exit 1
fi
