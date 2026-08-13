$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path $root '.venv\Scripts\python.exe'
if (Test-Path -LiteralPath $venvPython) { $pythonPath = $venvPython }
else {
    $pythonPath = & (Join-Path $root 'resolve_python.ps1')
    if ($LASTEXITCODE -ne 0 -or -not $pythonPath) { throw 'Python 3.11 o superior no esta disponible.' }
}
$env:PYTHONPATH = Join-Path $root 'src'
& $pythonPath -m inspection_v4.app diagnostic --root $root
exit $LASTEXITCODE
