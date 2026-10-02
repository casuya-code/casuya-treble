# Creates the casuyawin database on your local PostgreSQL (default superuser: postgres).
param(
  [string]$HostName = "localhost",
  [int]$Port = 5432,
  [string]$AdminUser = "postgres",
  [string]$DbName = "casuyawin"
)

$envFile = Join-Path $PSScriptRoot "..\.env"
if (-not (Test-Path $envFile)) {
  Write-Error "Missing .env — copy .env.example and set POSTGRES_PASSWORD."
  exit 1
}

$passwordLine = Get-Content $envFile | Where-Object { $_ -match "^POSTGRES_PASSWORD=" } | Select-Object -First 1
if (-not $passwordLine) {
  Write-Error ".env must contain POSTGRES_PASSWORD="
  exit 1
}
$password = ($passwordLine -split "=", 2)[1]

$engineRoot = Join-Path $PSScriptRoot "..\core-prediction-engine"
$python = Join-Path $engineRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
  Write-Error "Run core-prediction-engine venv setup first, or use pgAdmin: CREATE DATABASE casuyawin;"
  exit 1
}

$code = @"
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
conn = psycopg2.connect(host='$HostName', port=$Port, user='$AdminUser', password=r'''$password''', dbname='postgres')
conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
cur = conn.cursor()
cur.execute("SELECT 1 FROM pg_database WHERE datname = '$DbName'")
if cur.fetchone():
    print('Database $DbName already exists.')
else:
    cur.execute('CREATE DATABASE $DbName')
    print('Created database $DbName.')
cur.close(); conn.close()
"@

& $python -c $code
