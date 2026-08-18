$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$resolver = Join-Path $root 'resolve_python.ps1'
$pythonPath = & $resolver
if ($LASTEXITCODE -ne 0 -or -not $pythonPath) {
    throw 'Instala Python 3.11 o superior. No se encontró un intérprete ejecutable.'
}
$venv = Join-Path $root '.venv'
if (-not (Test-Path -LiteralPath $venv)) {
    & $pythonPath -m venv $venv
}
$venvPython = Join-Path $venv 'Scripts\python.exe'
Push-Location $root
try {
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -e ".[dev]"
} finally {
    Pop-Location
}
Write-Host "Entorno V5 listo: $venvPython"
