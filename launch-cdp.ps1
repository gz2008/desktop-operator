param(
    [string]$Url = "https://github.com",
    [int]$Port = 9223,
    [string]$Profile = "",
    [string]$BrowserPath = "",
    [switch]$Headless
)

$here = $PSScriptRoot
if (-not $Profile) {
    $Profile = Join-Path $here "cdp-profile"
}

$opArgs = @(
    "browser.launch_cdp",
    "port=$Port",
    "profile=$Profile",
    "url=$Url",
    "headless=$($Headless.IsPresent.ToString().ToLower())"
)
if ($BrowserPath) {
    $opArgs += "browser_path=$BrowserPath"
}

& (Join-Path $here "op.ps1") @opArgs
