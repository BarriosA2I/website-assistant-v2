#!/bin/bash
# ============================================================================
# BARRIOS A2I WEBSITE ASSISTANT v2.0 — QUICK START
# ============================================================================
# One-command setup for local development
# ============================================================================

set -e

echo "🚀 Barrios A2I Website Assistant v2.0 — Quick Start"
echo "=================================================="

# Check for required commands
command -v python3 >/dev/null 2>&1 || { echo "❌ Python 3 is required but not installed."; exit 1; }
command -v node >/dev/null 2>&1 || { echo "❌ Node.js is required but not installed."; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "❌ npm is required but not installed."; exit 1; }

# Check for .env file
if [ ! -f .env ]; then
    echo "📝 Creating .env from .env.example..."
    cp .env.example .env
    echo "⚠️  Please edit .env and add your API keys before running!"
    echo "   Required: ANTHROPIC_API_KEY"
    echo "   Optional: OPENAI_API_KEY, TRINITY_API_URL"
fi

# Backend setup
echo ""
echo "📦 Setting up Backend..."
cd backend

if [ ! -d "venv" ]; then
    echo "   Creating virtual environment..."
    python3 -m venv venv
fi

echo "   Activating virtual environment..."
source venv/bin/activate

echo "   Installing dependencies..."
pip install -q -r requirements.txt

echo "   ✅ Backend ready!"

# Frontend setup
echo ""
echo "📦 Setting up Frontend..."
cd ../frontend

if [ ! -d "node_modules" ]; then
    echo "   Installing dependencies..."
    npm install --silent
fi

echo "   ✅ Frontend ready!"

# Start services
echo ""
echo "🎯 Starting services..."
echo ""

# Start backend in background
cd ../backend
source venv/bin/activate
echo "   Starting Backend on http://localhost:8000..."
python -m api.server &
BACKEND_PID=$!

# Wait for backend
sleep 3

# Start frontend
cd ../frontend
echo "   Starting Frontend on http://localhost:3000..."
npm run dev &
FRONTEND_PID=$!

echo ""
echo "=================================================="
echo "✅ Website Assistant v2.0 is running!"
echo ""
echo "   🌐 Frontend: http://localhost:3000"
echo "   🔧 Backend:  http://localhost:8000"
echo "   📊 Health:   http://localhost:8000/health"
echo ""
echo "   Press Ctrl+C to stop all services"
echo "=================================================="

# Cleanup on exit
cleanup() {
    echo ""
    echo "Shutting down..."
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    echo "Goodbye! 👋"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Wait for processes
wait
