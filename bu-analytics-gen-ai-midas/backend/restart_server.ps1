# PowerShell script to restart the Midas backend server

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Midas Backend Server Restart Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Navigate to backend directory
$BackendPath = "C:\projects\midasv2\midas\backend"
Set-Location $BackendPath
Write-Host "✓ Changed directory to: $BackendPath" -ForegroundColor Green

# Check if virtual environment exists
if (Test-Path ".\venv\Scripts\Activate.ps1") {
    Write-Host "✓ Virtual environment found" -ForegroundColor Green
    
    # Use virtual environment Python directly
    Write-Host "Using virtual environment Python..." -ForegroundColor Yellow
    Write-Host "✓ Virtual environment Python ready" -ForegroundColor Green
} else {
    Write-Host "⚠ Warning: Virtual environment not found at .\venv\" -ForegroundColor Red
    Write-Host "Please create a virtual environment first or adjust the path." -ForegroundColor Red
    exit 1
}

# Check if main.py exists
if (Test-Path ".\main.py") {
    Write-Host "✓ main.py found" -ForegroundColor Green
} else {
    Write-Host "✗ Error: main.py not found" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Starting Backend Server..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Server will be available at: http://localhost:8000" -ForegroundColor Yellow
Write-Host "API Documentation at: http://localhost:8000/docs" -ForegroundColor Yellow
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

# Start the server using virtual environment Python
try {
    & ".\venv\Scripts\python.exe" -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
} catch {
    Write-Host ""
    Write-Host "✗ Error starting server: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Trying alternative method..." -ForegroundColor Yellow
    & ".\venv\Scripts\uvicorn.exe" main:app --reload --host 0.0.0.0 --port 8000
}


