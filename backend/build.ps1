param(
    [string]$Python = "python",
    [string]$Version = "1.0.0"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

if (-not (Test-Path "..\frontend\dist\index.html")) {
    Write-Error "frontend/dist 未找到，请先在 frontend 目录执行 npm run build"
}

$today = Get-Date -Format "yyyyMMdd"
$outputName = "ScreenCapture_{0}_{1}" -f $Version, $today

Write-Host "Packaging as $outputName"

$pythonExe = (Get-Command $Python).Source

& $pythonExe -m pip install -r requirements.txt

$pyinstallerArgs = @(
    "app.py",
    "--name", $outputName,
    "--onefile",
    "--noconsole",
    "--add-data", "..\frontend\dist;frontend\dist",
    "--icon", "favicon.ico"
)

& $pythonExe -m PyInstaller @($pyinstallerArgs)

Write-Host "Build finished: dist\$outputName.exe"
