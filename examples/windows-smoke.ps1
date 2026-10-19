$here = Split-Path -Parent $PSScriptRoot
$op = Join-Path $here "op.ps1"

& $op win.list
