# AI News Platform - One-click Launcher

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$backendDir  = Join-Path $projectRoot "backend"
$frontend    = Join-Path $projectRoot "frontend\index.html"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  AI News Platform Launcher"             -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Find Python
Write-Host "[1/3] Finding Python..." -ForegroundColor Yellow
$python = $null
foreach ($cmd in @("py", "python", "python3")) {
    try {
        $v = & $cmd --version 2>&1
        $python = $cmd
        Write-Host "  [OK] $v" -ForegroundColor Green
        break
    } catch {}
}
if (-not $python) {
    Write-Host "  [X] Python not found. Please install Python 3.11+" -ForegroundColor Red
    Write-Host "  https://python.org" -ForegroundColor Gray
    Read-Host "Press Enter to exit"
    return
}

# 2. Start backend
Write-Host "[2/3] Starting backend (port 8000)..." -ForegroundColor Yellow

Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$backendDir'; Write-Host 'Backend: http://127.0.0.1:8000' -ForegroundColor Green; Write-Host 'API Docs: http://127.0.0.1:8000/docs' -ForegroundColor Green; Write-Host ''; & '$python' main.py; Write-Host ''; Write-Host 'Backend stopped.' -ForegroundColor Yellow; pause"
)

# 3. Wait for backend + open frontend
Write-Host "[3/3] Waiting for backend..." -ForegroundColor Yellow

$ready = $false
for ($i = 1; $i -le 20; $i++) {
    Start-Sleep -Seconds 2
    try {
        $null = Invoke-WebRequest "http://127.0.0.1:8000/api/health" -UseBasicParsing -TimeoutSec 2
        $ready = $true
        Write-Host "  [OK] Backend ready" -ForegroundColor Green
        break
    } catch {
        Write-Host "  ...waiting ($i/20)" -ForegroundColor Gray
    }
}

if (-not $ready) {
    Write-Host "  [!] Backend timeout, opening frontend anyway" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Opening frontend..." -ForegroundColor Yellow
Start-Process $frontend

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  All done!"                              -ForegroundColor Green
Write-Host "  Backend : http://127.0.0.1:8000"        -ForegroundColor Green
Write-Host "  Frontend: opened in browser"             -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Close this window (backend runs independently)" -ForegroundColor Gray
Read-Host
