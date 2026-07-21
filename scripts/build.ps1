param(
    [string]$PackageRoot = ""
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot

if (-not $PackageRoot) {
    $PackageRoot = Join-Path $ProjectRoot "output"
}

# 使用 .venv 虚拟环境
$Python = Join-Path $ProjectRoot ".venv/Scripts/python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    throw "未找到打包虚拟环境: $Python"
}

$OutputDir = $PackageRoot
$CacheRoot = Join-Path $ProjectRoot "cache"
$LocalAppData = Join-Path $CacheRoot "local-appdata"
$TempDir = Join-Path $ProjectRoot "temp"
New-Item -ItemType Directory -Force -Path $OutputDir, $LocalAppData, $TempDir | Out-Null

$env:LOCALAPPDATA = $LocalAppData
$env:TEMP = $TempDir
$env:TMP = $TempDir
$env:PYTHONPATH = $ProjectRoot

Write-Host "使用打包环境: $Python"

& $Python -m nuitka `
    --standalone `
    --mingw64 `
    --jobs=8 `
    --assume-yes-for-downloads `
    --output-dir="$OutputDir" `
    --output-filename="termi-word" `
    --include-package="termi_word" `
    --include-package="fsrs" `
    --include-package="sqlalchemy" `
    --show-progress `
    --include-data-dir="$ProjectRoot/termi_word/styles=termi_word/styles" `
    --nofollow-import-to=termi_word.tests `
    --nofollow-import-to=pytest `
    --nofollow-import-to=nuitka `
    "$ProjectRoot/termi_word/__main__.py"

$DistDir = Join-Path $OutputDir "__main__.dist"
$BuildExe = Join-Path $DistDir "termi-word.exe"
if (-not (Test-Path -LiteralPath $BuildExe)) {
    throw "未找到编译产物: $BuildExe"
}

Write-Host "打包完成！产物路径: $DistDir"
Write-Host "可执行文件: $BuildExe"

