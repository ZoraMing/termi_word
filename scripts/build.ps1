param(
    [string]$Python = "",
    [string]$PackageRoot = "E:/termi_word_package"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
if (-not $Python) {
    if ($env:VIRTUAL_ENV -or $env:CONDA_PREFIX) {
        $Python = "python"
    } else {
        $VenvPython = Join-Path $ProjectRoot ".venv_build/Scripts/python.exe"
        $Python = if (Test-Path -LiteralPath $VenvPython) { $VenvPython } else { "python" }
    }
}

$PackageRoot = [System.IO.Path]::GetFullPath($PackageRoot)
$OutputDir = Join-Path $PackageRoot "output"
$CacheRoot = Join-Path $PackageRoot "cache"
$LocalAppData = Join-Path $CacheRoot "local-appdata"
$TempDir = Join-Path $PackageRoot "temp"
New-Item -ItemType Directory -Force -Path $OutputDir, $LocalAppData, $TempDir | Out-Null

$env:LOCALAPPDATA = $LocalAppData
$env:TEMP = $TempDir
$env:TMP = $TempDir

& $Python -m nuitka `
    --standalone `
    --assume-yes-for-downloads `
    --output-dir="$OutputDir" `
    --output-filename="termi-word" `
    --include-package="termi_word" `
    --include-data-dir="$ProjectRoot/termi_word/styles=termi_word/styles" `
    --mingw64 `
    --lto=yes `
    --nofollow-import-to=pytest `
    --nofollow-import-to=openai `
    --nofollow-import-to=pydantic `
    --nofollow-import-to=httpx `
    --nofollow-import-to=requests `
    --nofollow-import-to=urllib3 `
    --nofollow-import-to=anyio `
    "$ProjectRoot/termi_word/__main__.py"

$DistDir = Get-ChildItem -LiteralPath $OutputDir -Directory -Filter "*.dist" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if (-not $DistDir) {
    throw "Nuitka dist directory not found in $OutputDir"
}

$ImportsDir = Join-Path $DistDir.FullName "data/imports"
New-Item -ItemType Directory -Force -Path $ImportsDir | Out-Null

$SourceDataDir = Join-Path $ProjectRoot "data"
if (Test-Path -LiteralPath $SourceDataDir) {
    Get-ChildItem -LiteralPath $SourceDataDir -Filter "*.csv" -File |
        Copy-Item -Destination $ImportsDir -Force
}

Write-Host "Built: $($DistDir.FullName)"
Write-Host "External import directory: $ImportsDir"
Write-Host "Package workspace: $PackageRoot"
