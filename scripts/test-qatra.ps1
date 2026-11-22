$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot

Set-Location (Join-Path $root "ai_engine")
uv run pytest

Set-Location (Join-Path $root "backend")
$env:QATRA_DATABASE_URL = "postgresql+psycopg://qatra:qatra_dev_password@localhost:5433/qatra_test"
uv run pytest
uv run ruff check app migrations tests

Set-Location (Join-Path $root "frontend")
npm run lint
npm run build
