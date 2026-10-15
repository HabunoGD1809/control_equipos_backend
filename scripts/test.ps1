param([string]$DatabaseName = "control_equipos_test", [string]$DatabaseHost = "127.0.0.1", [int]$DatabasePort = 5433)
$ErrorActionPreference = "Stop"
if ($DatabaseName -notmatch 'test') { throw "El nombre de la base aislada debe contener test." }
$savedEnvironment = @{}
foreach ($name in @('POSTGRES_SERVER', 'POSTGRES_PORT', 'POSTGRES_DB', 'REPORT_EXECUTION_MODE', 'UPLOADS_DIRECTORY')) {
    $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    $env:POSTGRES_SERVER = $DatabaseHost
    $env:POSTGRES_PORT = [string]$DatabasePort
    $env:POSTGRES_DB = $DatabaseName
    $env:REPORT_EXECUTION_MODE = "background"
    $env:UPLOADS_DIRECTORY = Join-Path (Get-Location).Path 'verification/uploads'
    uv sync --frozen --all-extras
    if ($LASTEXITCODE -ne 0) { throw "Falló la instalación de dependencias de pruebas." }
    uv run --frozen --no-sync python scripts/create_test_database.py
    if ($LASTEXITCODE -ne 0) { throw "No se pudo preparar la base aislada." }
    uv run --frozen --no-sync alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw "Fallaron las migraciones de pruebas." }
    uv run --frozen --no-sync pytest -q
    if ($LASTEXITCODE -ne 0) { throw "Falló la regresión del backend." }
    uv run --frozen --no-sync python scripts/verify_integration.py --database $DatabaseName --host $DatabaseHost --port $DatabasePort
    if ($LASTEXITCODE -ne 0) { throw "Falló la verificación de los flujos completos." }
} finally {
    foreach ($name in $savedEnvironment.Keys) { [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name], 'Process') }
    Pop-Location
}
