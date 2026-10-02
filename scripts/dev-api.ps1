param(
  [switch]$Restart
)

Set-Location "$PSScriptRoot\..\core-prediction-engine"
$env:PYTHONPATH = "."
$port = if ($env:CASUYA_API_PORT) { [int]$env:CASUYA_API_PORT } else { 8000 }

function Stop-ApiOnPort {
  param([int]$Port)
  $listeners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
  foreach ($conn in $listeners) {
    Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
  }
  Start-Sleep -Seconds 1
}

if (-not $Restart) {
  try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:$port/health" -TimeoutSec 2
    if ($health.status -eq "ok") {
      Write-Host "API already running at http://127.0.0.1:$port (docs: /docs)" -ForegroundColor Green
      Write-Host "Restart with new code:  .\scripts\dev-api.ps1 -Restart" -ForegroundColor Yellow
      exit 0
    }
  } catch {
    # not running — start below
  }
} else {
  Write-Host "Stopping API on port $port ..." -ForegroundColor Yellow
  Stop-ApiOnPort -Port $port
}

if (-not (Test-Path ".venv")) {
  python -m venv .venv
}
.\.venv\Scripts\pip install -r requirements.txt --only-binary asyncpg,pydantic-core -q

$listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
if ($listener) {
  $ownerPid = @($listener.OwningProcess)[0]
  Write-Host "Port $port is in use (PID $ownerPid). Close it or run:" -ForegroundColor Yellow
  Write-Host '  $env:CASUYA_API_PORT=8001; .\scripts\dev-api.ps1 -Restart' -ForegroundColor Cyan
  exit 1
}

Write-Host "Starting API on http://127.0.0.1:$port ..." -ForegroundColor Cyan
.\.venv\Scripts\python.exe -m uvicorn gateway.main:app --reload --host 127.0.0.1 --port $port
