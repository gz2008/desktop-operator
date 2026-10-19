param(
    [Parameter(Mandatory = $true)][ValidateSet("set", "get", "list", "remove")][string]$Action,
    [string]$Name
)

$dir = Join-Path $PSScriptRoot "secrets"
New-Item -ItemType Directory -Force -Path $dir | Out-Null

switch ($Action) {
    "set" {
        if (-not $Name) { throw "Name is required for set." }
        $secure = Read-Host -AsSecureString "Secret for $Name"
        $encrypted = $secure | ConvertFrom-SecureString
        Set-Content -LiteralPath (Join-Path $dir "$Name.txt") -Value $encrypted -NoNewline -Encoding ascii
        Write-Output "stored: $Name"
    }
    "get" {
        if (-not $Name) { throw "Name is required for get." }
        $path = Join-Path $dir "$Name.txt"
        if (-not (Test-Path -LiteralPath $path)) { throw "secret not found: $Name" }
        $encrypted = (Get-Content -LiteralPath $path -Raw).Trim()
        $secure = ConvertTo-SecureString $encrypted
        $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
        try {
            [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
        } finally {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
        }
    }
    "list" {
        Get-ChildItem -LiteralPath $dir -Filter "*.txt" | Select-Object -ExpandProperty BaseName
    }
    "remove" {
        if (-not $Name) { throw "Name is required for remove." }
        Remove-Item -LiteralPath (Join-Path $dir "$Name.txt") -Force -ErrorAction Stop
        Write-Output "removed: $Name"
    }
}
