$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "Starting QATRA database..."
Set-Location (Join-Path $root "infra")
docker compose up -d db

Write-Host "Applying platform migrations..."
Set-Location (Join-Path $root "backend")
uv sync
uv run alembic upgrade head

Write-Host "Start the platform API and engine in separate terminals:"
Write-Host "  cd backend; uv run uvicorn app.main:app --host 127.0.0.1 --port 8000"
Write-Host "  cd ai_engine; uv run uvicorn qatra_ai.service.app:app --port 8100 --env-file ../.env"
Write-Host "  cd frontend; npm run dev"
