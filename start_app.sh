#!/bin/bash

# Kill any existing processes (rough cleanup)
pkill -f "uvicorn"
pkill -f "python -m http.server"

echo "🚀 Initializing GIGACHAD AI System..."

# Activate Virtual Environment (Critical for dependencies)
source venv/bin/activate

# Install Dependencies (including pandas/openpyxl)
echo "📦 Installing/Update Server Dependencies..."
cd server
pip install -r requirements.txt > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "❌ Failed to install dependencies."
    exit 1
fi

# Start Backend
echo "🔥 Starting Backend Server (Port 8000)..."
python3 -u -m uvicorn main:app --host 0.0.0.0 --port 8000 > backend.log 2>&1 &
BACKEND_PID=$!

# Wait for backend to start
echo "⏳ Waiting for backend..."
sleep 3

# Start Frontend
echo "💻 Starting Client (Port 3000)..."
cd ../client
python3 -m http.server 3000 > frontend.log 2>&1 &
FRONTEND_PID=$!

echo "✅ System Online!"
echo "   Backend: http://localhost:8000"
echo "   Frontend: http://localhost:3000"
echo "   Database: server/candidates.xlsx"
echo ""
echo "Press CTRL+C to stop servers."

# Trap SIGINT to kill processes
trap "kill $BACKEND_PID $FRONTEND_PID; exit" INT

wait
