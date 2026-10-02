param([switch]$Clean)

Set-Location "$PSScriptRoot\..\apps\dashboard"
$env:NEXT_PUBLIC_API_URL = "http://localhost:8000"

$listeners = Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue
foreach ($conn in $listeners) {
  Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
}
if ($listeners) {
  Start-Sleep -Seconds 1
}
if (-not (Test-Path "node_modules")) {
  npm install
}
if ($Clean -and (Test-Path ".next")) {
  Remove-Item -Recurse -Force ".next"
  Write-Host "Removed stale .next build cache."
}
npm run dev
