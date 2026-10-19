param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$venv = Join-Path $here ".venv"
$venvPy = Join-Path $venv "Scripts\python.exe"

$version = & $Python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
Write-Host "Using Python $version"
if ([version]$version -lt [version]"3.11") {
    throw "Python 3.11+ is required."
}
if ([version]$version -ge [version]"3.14") {
    Write-Warning "Python $version detected. Python 3.12 is recommended for the most reliable COM/UIA behavior."
}

if (-not (Test-Path -LiteralPath $venvPy)) {
    & $Python -m venv $venv
}

& $venvPy -m pip install --upgrade pip --quiet
& $venvPy -m pip install -r (Join-Path $here "requirements.txt")

$edge = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if (-not (Test-Path -LiteralPath $edge)) {
    $edge = "C:\Program Files\Microsoft\Edge\Application\msedge.exe"
}
if (-not (Test-Path -LiteralPath $edge)) {
    Write-Warning "Microsoft Edge was not found. Browser commands require Edge or a CDP endpoint."
}

Write-Host ""
Write-Host "Installed. Smoke test:"
& (Join-Path $here "op.ps1") system.info
Write-Host ""
Write-Host "Next:"
Write-Host "  .\op.ps1 browser.goto `"url=https://example.com`" `"headed=true`""
