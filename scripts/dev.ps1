# ============================================================================
# WEBSITE ASSISTANT v3 - DEVELOPMENT ENVIRONMENT SCRIPT (Windows)
# ============================================================================
# Run this script to start the full development environment
# Usage: .\scripts\dev.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  WEBSITE ASSISTANT v3 - DEV MODE" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is running
$docker = Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue
if (-not $docker) {
    Write-Host "Docker Desktop is not running. Starting..." -ForegroundColor Yellow
    Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    Write-Host "Waiting for Docker to start (30 seconds)..." -ForegroundColor Yellow
    Start-Sleep -Seconds 30
}

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir

Write-Host "Project root: $RootDir" -ForegroundColor Gray

# Start infrastructure with Docker Compose (if docker-compose.yml exists)
$ComposeFile = Join-Path $RootDir "docker-compose.yml"
if (Test-Path $ComposeFile) {
    Write-Host "Starting infrastructure (Postgres, Redis, RabbitMQ)..." -ForegroundColor Green
    docker-compose -f $ComposeFile up -d postgres redis rabbitmq
    Write-Host "Waiting for services to be ready..." -ForegroundColor Yellow
    Start-Sleep -Seconds 5
}

# Initialize database
$SqlFile = Join-Path $RootDir "backend\sql\init.sql"
if (Test-Path $SqlFile) {
    Write-Host "Database init script found at: $SqlFile" -ForegroundColor Gray
    Write-Host "Run manually: psql -U postgres -d website_assistant < backend/sql/init.sql" -ForegroundColor Yellow
}

# Start Backend
Write-Host ""
Write-Host "Starting Backend (FastAPI)..." -ForegroundColor Green
$BackendDir = Join-Path $RootDir "backend"
$BackendEnv = Join-Path $BackendDir ".env"

if (-not (Test-Path $BackendEnv)) {
    $BackendEnvExample = Join-Path $BackendDir ".env.example"
    if (Test-Path $BackendEnvExample) {
        Copy-Item $BackendEnvExample $BackendEnv
        Write-Host "Created .env from .env.example" -ForegroundColor Yellow
    }
}

# Activate virtual environment and start server
$VenvActivate = Join-Path $BackendDir "venv\Scripts\Activate.ps1"
if (Test-Path $VenvActivate) {
    Write-Host "Starting backend server on port 8000..." -ForegroundColor Cyan
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$BackendDir'; & '$VenvActivate'; `$env:PYTHONPATH='.'; uvicorn api.server:app --reload --host 0.0.0.0 --port 8000"
} else {
    Write-Host "Virtual environment not found. Run: python -m venv venv" -ForegroundColor Red
}

# Start Frontend
Write-Host ""
Write-Host "Starting Frontend (Next.js)..." -ForegroundColor Green
$FrontendDir = Join-Path $RootDir "frontend"

if (Test-Path $FrontendDir) {
    Write-Host "Starting frontend server on port 3000..." -ForegroundColor Cyan
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$FrontendDir'; npm run dev"
} else {
    Write-Host "Frontend directory not found at: $FrontendDir" -ForegroundColor Red
}

# Summary
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  DEVELOPMENT ENVIRONMENT READY" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Services:" -ForegroundColor White
Write-Host "  Frontend:  http://localhost:3000" -ForegroundColor Green
Write-Host "  Backend:   http://localhost:8000" -ForegroundColor Green
Write-Host "  API Docs:  http://localhost:8000/docs" -ForegroundColor Green
Write-Host ""
Write-Host "Admin Dashboard:" -ForegroundColor White
Write-Host "  streamlit run admin/dashboard.py" -ForegroundColor Yellow
Write-Host ""
Write-Host "Logs:" -ForegroundColor White
Write-Host "  Check the opened PowerShell windows for server logs" -ForegroundColor Gray
Write-Host ""
