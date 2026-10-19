$here = Split-Path -Parent $PSScriptRoot
$op = Join-Path $here "op.ps1"

& $op system.info
& $op browser.goto "url=https://example.com"
& $op browser.text
