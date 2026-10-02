# Recreate venv when "Unable to copy venvlauncher.exe" (usually API still running).
Set-Location "$PSScriptRoot\..\core-prediction-engine"

Get-Process -Name python, uvicorn -ErrorAction SilentlyContinue | Where-Object {
  $_.Path -like "*casuya-win*"
} | Stop-Process -Force -ErrorAction SilentlyContinue

Start-Sleep -Seconds 2

if (Test-Path ".venv") {
  Remove-Item -Recurse -Force ".venv"
}

python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt --only-binary asyncpg,pydantic-core

Write-Host "Done. Start API with: ..\scripts\dev-api.ps1" -ForegroundColor Green
