#!/bin/bash

# ==============================================================================
# AIVA Server Launcher
# ==============================================================================

PORT=5002
HOST="0.0.0.0"

# Load .env file if exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

echo "=================================================="
echo "         AIVA Server Launcher"
echo "=================================================="
echo ""

# ย้ายไปยังโฟลเดอร์ที่ไฟล์นี้อยู่
cd "$(dirname "$0")"
echo "Working directory: $(pwd)"
echo ""

# ตรวจสอบ Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python3 not found!"
    exit 1
fi

# ตรวจสอบ dependencies
echo "[1] Checking dependencies..."
python3 -c "import flask" 2>/dev/null || {
    echo "[WARN] Flask not installed. Installing..."
    pip3 install -r requirements.txt
}

# Kill process บน port เดิม (ถ้ามี)
echo "[2] Checking port $PORT..."
lsof -ti:$PORT | xargs kill -9 2>/dev/null && echo "Killed existing process on port $PORT"

# รัน Server
echo "[3] Starting AIVA Server on http://$HOST:$PORT"
echo ""

# Production mode
if [ "$1" == "--production" ] || [ "$1" == "-p" ]; then
    echo "Mode: PRODUCTION (using gunicorn)"
    pip3 install gunicorn -q 2>/dev/null
    gunicorn -w 4 -b $HOST:$PORT app:app
else
    echo "Mode: DEVELOPMENT"
    echo ""
    python3 app.py &
    SERVER_PID=$!

    # รอ server พร้อม
    sleep 3

    # เปิด browser (macOS)
    if [[ "$OSTYPE" == "darwin"* ]]; then
        open "http://127.0.0.1:$PORT"
    # Linux
    elif command -v xdg-open &> /dev/null; then
        xdg-open "http://127.0.0.1:$PORT"
    fi

    echo "=================================================="
    echo "  Server running: http://127.0.0.1:$PORT"
    echo "  PID: $SERVER_PID"
    echo "  Stop: Ctrl+C or kill $SERVER_PID"
    echo "=================================================="

    wait $SERVER_PID
fi
