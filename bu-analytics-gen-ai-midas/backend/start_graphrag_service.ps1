param(
    [string]$Python312Path = $env:GRAPHRAG_PYTHON_PATH,
    [int]$Port = 8001,
    [switch]$SkipInstall
)

function Test-Python312 {
    param([string]$PathToPython)
    if (-not $PathToPython) { return $false }
    try {
        $versionOutput = & $PathToPython --version 2>&1
        return ($versionOutput -match "3\.12")
    }
    catch {
        return $false
    }
}

function Resolve-Python312Path {
    param([string]$PreferredPath)

    if ($PreferredPath -and (Test-Python312 $PreferredPath)) {
        return $PreferredPath
    }

    $username = $env:USERNAME
    $candidates = @(
        "C:\Users\saiyam268728\OneDrive - EXLService.com (I) Pvt. Ltd\Documents\MIDAS-Saiyam\KnowledgeRepo_To_KG\venv\Scripts\python.exe",
        "C:\Python312\python.exe",
        "C:\Users\$username\AppData\Local\Programs\Python\Python312\python.exe",
        "python3.12",
        "python"
    )

    foreach ($candidate in $candidates) {
        if (Test-Python312 $candidate) {
            return $candidate
        }
    }

    return $null
}

$python312Path = Resolve-Python312Path $Python312Path
if (-not $python312Path) {
    Write-Host "ERROR: Python 3.12 interpreter not found." -ForegroundColor Red
    Write-Host "Set GRAPHRAG_PYTHON_PATH or pass -Python312Path to this script." -ForegroundColor Yellow
    exit 1
}

$backendDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $backendDir

$env:GRAPHRAG_SERVICE_PORT = "$Port"
$versionOutput = & $python312Path --version 2>&1

if (-not $SkipInstall) {
    Write-Host "Checking GraphRAG service dependencies..." -ForegroundColor Cyan
    $requirementsFile = Join-Path $backendDir "graphrag_service\requirements.txt"

    if (Test-Path $requirementsFile) {
        Write-Host "Installing/updating dependencies from requirements.txt..." -ForegroundColor Cyan
        & $python312Path -m pip install -q -r $requirementsFile
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] GraphRAG microservice dependencies installed." -ForegroundColor Green
        }
        else {
            Write-Host "WARNING: Dependency installation returned a non-zero exit code." -ForegroundColor Yellow
        }
    }
    else {
        Write-Host "WARNING: requirements.txt not found, installing fallback packages..." -ForegroundColor Yellow
        & $python312Path -m pip install -q fastapi uvicorn python-dotenv httpx graphrag
    }
}

$envFile = Join-Path $backendDir ".env"
if (Test-Path $envFile) {
    Write-Host "[OK] .env file found at: $envFile" -ForegroundColor Green
}
else {
    Write-Host "WARNING: .env file not found at: $envFile" -ForegroundColor Yellow
    Write-Host "LLM_GATEWAY_URL and LLM_GATEWAY_VIRTUAL_KEY must be set in environment variables." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Starting GraphRAG Service on port $env:GRAPHRAG_SERVICE_PORT..." -ForegroundColor Green
Write-Host "Using Python: $python312Path" -ForegroundColor Cyan
Write-Host "Python Version: $versionOutput" -ForegroundColor Cyan
Write-Host ""

& $python312Path -m graphrag_service.start_service

Write-Host ""
Write-Host "GraphRAG service stopped." -ForegroundColor Yellow
