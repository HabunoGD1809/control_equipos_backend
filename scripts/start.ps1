$ErrorActionPreference = "Stop"
$EnvDir = ".CtrlEqEnv"

Write-Host ">> Iniciando configuracion con uv..." -ForegroundColor Cyan

if (!(Get-Command "uv" -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: 'uv' no esta instalado." -ForegroundColor Red
    Write-Host "Para instalarlo ejecuta:" -ForegroundColor Yellow
    Write-Host "  powershell -ExecutionPolicy ByPass -c `"irm https://astral.sh/uv/install.ps1 | iex`"" -ForegroundColor White
    exit 1
}

$env:UV_PROJECT_ENVIRONMENT = $EnvDir

Write-Host ">> Sincronizando dependencias..." -ForegroundColor Cyan

try {
    uv sync --all-extras
    Write-Host "`n[OK] Entorno virtual sincronizado y listo." -ForegroundColor Green
    Write-Host "Para activar el entorno ejecuta:" -ForegroundColor Yellow
    Write-Host "  .\$EnvDir\Scripts\Activate.ps1" -ForegroundColor White
}
catch {
    Write-Host "`n[ERROR] Fallo durante la sincronizacion de uv." -ForegroundColor Red
    exit 1
}
