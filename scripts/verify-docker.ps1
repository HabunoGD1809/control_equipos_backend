param([switch]$KeepStack)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $root
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Docker no está instalado.' }
docker info --format '{{.OSType}}' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Activa el motor Linux en Docker Desktop antes de ejecutar esta prueba.' }
$manifestText = & (Join-Path $root '.venv\Scripts\python.exe') scripts/prepare_docker_verification.py
if ($LASTEXITCODE -ne 0) { throw 'No se pudo preparar el entorno aislado.' }
$manifest = $manifestText | ConvertFrom-Json
if ($manifest.project -notmatch '^control-equipos-test-[a-f0-9]{12}$') { throw 'Identidad de proyecto inválida.' }
$directory = [IO.Path]::GetFullPath($manifest.directory)
if (-not $directory.StartsWith((Join-Path $root 'verification') + [IO.Path]::DirectorySeparatorChar)) { throw 'Destino fuera de verification.' }
$composeArgs = @('compose', '--env-file', $manifest.env_file, '-p', $manifest.project, '-f', 'docker-compose.yml', '-f', 'docker-compose.verification.yml')
function Invoke-Stack {
    param([string[]]$Arguments)
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & docker @composeArgs @Arguments 2>&1 | ForEach-Object { $_.ToString() } | Tee-Object -FilePath (Join-Path $directory 'commands.log') -Append
    } finally { $ErrorActionPreference = $previousPreference }
    if ($LASTEXITCODE -ne 0) { throw "Falló Docker Compose: $($Arguments[0]). Revisa el registro de la prueba." }
}
$started = $false
try {
    Invoke-Stack -Arguments @('config', '--quiet')
    $started = $true
    Write-Host 'Construyendo y arrancando un proyecto nuevo, sin tocar las bases existentes...'
    Invoke-Stack -Arguments @('up', '--build', '-d', '--wait', '--wait-timeout', '900')
    Invoke-Stack -Arguments @('exec', '-T', 'backend', '/home/app/.venv/bin/python', 'scripts/verify_docker_stack.py', '--phase', 'full')
    Invoke-Stack -Arguments @('stop', 'worker')
    Invoke-Stack -Arguments @('exec', '-T', 'backend', '/home/app/.venv/bin/python', 'scripts/verify_docker_stack.py', '--phase', 'queue')
    Invoke-Stack -Arguments @('restart', 'redis')
    Invoke-Stack -Arguments @('start', 'worker')
    Invoke-Stack -Arguments @('exec', '-T', 'backend', '/home/app/.venv/bin/python', 'scripts/verify_docker_stack.py', '--phase', 'resume')
    Invoke-Stack -Arguments @('stop', 'redis')
    Invoke-Stack -Arguments @('exec', '-T', 'backend', '/home/app/.venv/bin/python', 'scripts/verify_docker_stack.py', '--phase', 'outage')
    Invoke-Stack -Arguments @('start', 'redis')
    Invoke-Stack -Arguments @('exec', '-T', 'backend', '/home/app/.venv/bin/python', 'scripts/verify_docker_stack.py', '--phase', 'resume')
    Invoke-Stack -Arguments @('cp', 'backend:/home/app/backups/docker-verification.json', (Join-Path $directory 'results.json'))
    Write-Host "Verificación completada. Evidencia: $directory\results.json"
} finally {
    if ($started) {
        & docker @composeArgs logs --no-color --tail 100 *> (Join-Path $directory 'stack.log')
        # This exact generated project owns all removed containers and volumes.
        if (-not $KeepStack) { & docker @composeArgs down --volumes --remove-orphans }
        else { Write-Host "Entorno conservado: $($manifest.project). El manifest identifica cómo cerrarlo." }
    }
}
