param(
    [Parameter(Mandatory = $true)]
    [string]$Version,
    [string]$Root,
    [string]$OutputRoot
)

$ErrorActionPreference = "Stop"
$scriptRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($Root)) { $Root = $scriptRoot }
if ([string]::IsNullOrWhiteSpace($OutputRoot)) { $OutputRoot = Join-Path $scriptRoot "release" }
$reports = Join-Path $Root "data\v5\reports"
$wheelhouse = Join-Path $Root "wheelhouse"

function Get-LatestReport([string]$pattern) {
    $path = Get-ChildItem -LiteralPath $reports -Filter $pattern -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($null -eq $path) { throw "Falta reporte: $pattern" }
    return $path
}

function Read-ApprovedReport([string]$pattern) {
    $path = Get-LatestReport $pattern
    $json = Get-Content -LiteralPath $path.FullName -Raw | ConvertFrom-Json
    if (-not [bool]$json.release_ready) { throw "Puerta no aprobada: $($path.Name)" }
    return $path
}

try {
    $fixtureReport = Read-ApprovedReport "fixtures_*.json"
    $soakReport = Read-ApprovedReport "soak_*.json"
    $physicalReport = Read-ApprovedReport "physical_release_*.json"
    $rehearsalReport = Read-ApprovedReport "rehearsal_*.json"
    $snapshot = Join-Path $Root "data\v5\manifests\v4_protected_files.json"
    if (-not (Test-Path -LiteralPath $snapshot)) { throw "Falta snapshot V4" }
    if (-not (Test-Path -LiteralPath $wheelhouse)) { throw "Falta wheelhouse offline: $wheelhouse" }
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 2
}

$packageName = "inspeccion_visual_v5_$Version"
$staging = Join-Path $OutputRoot $packageName
$zipPath = Join-Path $OutputRoot "$packageName.zip"
if (Test-Path -LiteralPath $staging -or Test-Path -LiteralPath $zipPath) {
    Write-Error "El destino ya existe; elige otra version para evitar sobrescritura."
    exit 2
}

New-Item -ItemType Directory -Path $staging -Force | Out-Null
$include = @(
    "src\inspection_v5",
    "config\v5",
    "data\v5\models",
    "data\v5\references",
    "data\v5\manifests",
    "assets\Logo_TuRobotics_Colorizado.png",
    "docs\OPERACION_DEMO_V5.md",
    "docs\V5_BATERIA_FISICA.md",
    "docs\V5_RELEASE.md",
    "ABRIR_DEMO_V5.bat",
    "ABRIR_DEMO_V5.vbs",
    "CAMBIAR_CAMARA_V5.bat",
    "RESTaurar_V4.bat",
    "README_V5.md",
    "requirements-lock.txt",
    "requirements-demo-lock.txt",
    "pyproject.toml"
)
foreach ($relative in $include) {
    $source = Join-Path $Root $relative
    if (-not (Test-Path -LiteralPath $source)) { throw "Falta artefacto: $relative" }
    $destination = Join-Path $staging $relative
    $parent = Split-Path -Parent $destination
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    Copy-Item -LiteralPath $source -Destination $destination -Recurse -Force
}
Copy-Item -LiteralPath $wheelhouse -Destination (Join-Path $staging "wheelhouse") -Recurse -Force

$gateFiles = @($fixtureReport.FullName, $soakReport.FullName, $physicalReport.FullName, $rehearsalReport.FullName)
Copy-Item -LiteralPath $gateFiles -Destination (Join-Path $staging "data\v5\reports") -Force
$manifestLines = Get-ChildItem -LiteralPath $staging -Recurse -File |
    Sort-Object FullName |
    ForEach-Object {
        $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant()
        $relative = $_.FullName.Substring($staging.Length + 1).Replace("\", "/")
        "$hash  $relative"
    }
$manifestLines | Set-Content -LiteralPath (Join-Path $staging "MANIFEST_SHA256.txt") -Encoding UTF8
Compress-Archive -LiteralPath $staging -DestinationPath $zipPath -CompressionLevel Optimal
Write-Host "Paquete creado: $zipPath"
exit 0
