Set-Location "$PSScriptRoot\..\core-prediction-engine"
$env:PYTHONPATH = "."
.\.venv\Scripts\pip install -r requirements-dev.txt -q --only-binary asyncpg,pydantic-core
.\.venv\Scripts\python.exe -m pytest tests -q
