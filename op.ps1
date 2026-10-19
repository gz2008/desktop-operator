param(
    [string]$Command = "health",
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$Pairs
)

$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
& $py (Join-Path $PSScriptRoot "dop.py") $Command @Pairs
