param(
    [int]$Port = 8086,
    [string]$BindAddress = "127.0.0.1",
    [string]$DatabaseHost = "127.0.0.1",
    [int]$DatabasePort = 5433,
    [switch]$Development,
    [switch]$SkipInstall
)
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    if (!(Get-Command uv -ErrorAction SilentlyContinue)) { throw "Instale uv: https://docs.astral.sh/uv/getting-started/installation/" }
    if (!(Test-Path -LiteralPath '.env')) { throw "Copie .env.example a .env y configure sus claves, base de datos y administrador." }
    $env:POSTGRES_SERVER = $DatabaseHost
    $env:POSTGRES_PORT = [string]$DatabasePort
    $env:REPORT_EXECUTION_MODE = "background"
    $env:PORT = [string]$Port
    if (!$SkipInstall) {
        if ($Development) { uv sync --frozen --all-extras } else { uv sync --frozen --no-dev }
        if ($LASTEXITCODE -ne 0) { throw "No se pudieron instalar las dependencias." }
    }
    uv run --frozen --no-sync alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw "No se pudieron aplicar las migraciones." }
    uv run --frozen --no-sync python scripts/bootstrap.py --from-env
    if ($LASTEXITCODE -ne 0) { throw "No se pudo preparar el administrador." }
    Write-Host "API: http://${BindAddress}:${Port} | Documentación: http://${BindAddress}:${Port}/api/v1/docs"
    if ($Development) { uv run --frozen --no-sync uvicorn app.main:app --host $BindAddress --port $Port --reload }
    else { uv run --frozen --no-sync uvicorn app.main:app --host $BindAddress --port $Port }
    if ($LASTEXITCODE -ne 0) { throw "La API se detuvo con un error." }
} finally { Pop-Location }
