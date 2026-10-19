param(
    [Parameter(Mandatory = $true)][string]$Url
)

$here = Split-Path -Parent $PSScriptRoot
$op = Join-Path $here "op.ps1"

& $op browser.capture_response `
    "url=$Url" `
    "click_selector=text=实验报告" `
    "match=gen-experiment-report" `
    "timeout=20000"
