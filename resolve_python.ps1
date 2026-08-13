$ErrorActionPreference = 'SilentlyContinue'

function Test-PythonExecutable([string] $candidate) {
    if (-not $candidate) { return $null }
    $result = & $candidate -c 'import sys; print(sys.executable)' 2>$null
    if ($LASTEXITCODE -eq 0 -and $result) { return ($result | Select-Object -First 1).Trim() }
    return $null
}

$pyLaunchers = @(Get-Command py.exe -All -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source)
foreach ($launcher in $pyLaunchers) {
    foreach ($minor in @('3.11', '3.12', '3.13', '3.14')) {
        $resolved = & $launcher -$minor -c 'import sys; print(sys.executable)' 2>$null
        if ($LASTEXITCODE -eq 0 -and $resolved) {
            Write-Output (($resolved | Select-Object -First 1).Trim())
            exit 0
        }
    }
}

$pythonCommands = @(Get-Command python.exe -All -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source)
foreach ($candidate in $pythonCommands) {
    $resolved = Test-PythonExecutable $candidate
    if ($resolved) { Write-Output $resolved; exit 0 }
}

exit 1
