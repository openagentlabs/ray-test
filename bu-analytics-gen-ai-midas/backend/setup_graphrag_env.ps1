# Setup script for GraphRAG Python 3.12 environment

Write-Host "Setting up GraphRAG environment with Python 3.12..." -ForegroundColor Green

# Your actual Python 3.12 path
$python312 = "C:\Users\saiyam268728\OneDrive - EXLService.com (I) Pvt. Ltd\Documents\MIDAS-Saiyam\KnowledgeRepo_To_KG\venv\Scripts\python.exe"

if (-not (Test-Path $python312)) {
    Write-Host "Python 3.12 not found at $python312" -ForegroundColor Red
    Write-Host "Please verify the Python 3.12 installation path" -ForegroundColor Yellow
    exit 1
}

Write-Host "Found Python 3.12 at $python312" -ForegroundColor Green

# Verify it's Python 3.12
$version = & $python312 --version
Write-Host "Version: $version" -ForegroundColor Cyan

# Install graphrag in the Python 3.12 environment
Write-Host "Installing graphrag package..." -ForegroundColor Green
& $python312 -m pip install graphrag

Write-Host "Setup complete!" -ForegroundColor Green
Write-Host "GraphRAG is now ready to use with your application" -ForegroundColor Green