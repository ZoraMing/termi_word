param(
    [string]$PackageRoot = ""
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot

if (-not $PackageRoot) {
    $PackageRoot = Join-Path $ProjectRoot "output"
}

# 优先使用 .venv 虚拟环境，若不存在则回退到系统环境变量中的 python
$Python = Join-Path $ProjectRoot ".venv/Scripts/python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    $SysPython = Get-Command python -ErrorAction SilentlyContinue
    if ($SysPython) {
        $Python = $SysPython.Source
    } else {
        throw "Python executable not found!"
    }
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

Write-Host "Using Python executable: $Python"

& $Python -m nuitka `
    --standalone `
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
    throw "Executable build failed: $BuildExe not found"
}

Write-Host "Build completed: $DistDir"
Write-Host "Executable: $BuildExe"

# 自动打包压缩为 ZIP
$ZipPath = Join-Path $OutputDir "termi_word_windows.zip"
if (Test-Path -LiteralPath $ZipPath) {
    Remove-Item -Force -LiteralPath $ZipPath
}
Write-Host "Compressing into ZIP archive: $ZipPath ..."
Compress-Archive -Path "$DistDir\*" -DestinationPath $ZipPath -Force
Write-Host "ZIP compression completed: $ZipPath"



