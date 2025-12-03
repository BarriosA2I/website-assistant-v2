# ============================================================================
# BARRIOS A2I WEBSITE ASSISTANT v2.0 — QUICK START (Windows)
# ============================================================================
# One-command setup for local development on Windows
# ============================================================================

$ErrorActionPreference = "Stop"

Write-Host "🚀 Barrios A2I Website Assistant v2.0 — Quick Start" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# Check for required commands
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Python is required but not installed." -ForegroundColor Red
    exit 1
}
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Node.js is required but not installed." -ForegroundColor Red
    exit 1
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Host "❌ npm is required but not installed." -ForegroundColor Red
    exit 1
}

# Check for .env file
if (-not (Test-Path .env)) {
    Write-Host "📝 Creating .env from .env.example..." -ForegroundColor Yellow
    Copy-Item .env.example .env
    Write-Host "⚠️  Please edit .env and add your API keys before running!" -ForegroundColor Yellow
    Write-Host "   Required: ANTHROPIC_API_KEY"
    Write-Host "   Optional: OPENAI_API_KEY, TRINITY_API_URL"
}

# Backend setup
Write-Host ""
Write-Host "📦 Setting up Backend..." -ForegroundColor Green
Set-Location backend

if (-not (Test-Path "venv")) {
    Write-Host "   Creating virtual environment..."
    python -m venv venv
}

Write-Host "   Activating virtual environment..."
.\venv\Scripts\Activate.ps1

Write-Host "   Installing dependencies..."
pip install -q -r requirements.txt

Write-Host "   ✅ Backend ready!" -ForegroundColor Green

# Frontend setup
Write-Host ""
Write-Host "📦 Setting up Frontend..." -ForegroundColor Green
Set-Location ..\frontend

if (-not (Test-Path "node_modules")) {
    Write-Host "   Installing dependencies..."
    npm install --silent
}

Write-Host "   ✅ Frontend ready!" -ForegroundColor Green

# Start services
Write-Host ""
Write-Host "🎯 Starting services..." -ForegroundColor Cyan
Write-Host ""

# Start backend in new window
Set-Location ..\backend
Start-Process powershell -ArgumentList "-NoExit", "-Command", ".\venv\Scripts\Activate.ps1; python -m api.server"

# Wait for backend
Start-Sleep -Seconds 3

# Start frontend in new window  
Set-Location ..\frontend
Start-Process powershell -ArgumentList "-NoExit", "-Command", "npm run dev"

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "✅ Website Assistant v2.0 is running!" -ForegroundColor Green
Write-Host ""
Write-Host "   🌐 Frontend: http://localhost:3000" -ForegroundColor White
Write-Host "   🔧 Backend:  http://localhost:8000" -ForegroundColor White
Write-Host "   📊 Health:   http://localhost:8000/health" -ForegroundColor White
Write-Host ""
Write-Host "   Close the PowerShell windows to stop services" -ForegroundColor Yellow
Write-Host "==================================================" -ForegroundColor Cyan

Set-Location ..
