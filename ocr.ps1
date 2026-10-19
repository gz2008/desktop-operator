param(
    [Parameter(Mandatory = $true)][string]$Path
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding = [System.Text.UTF8Encoding]::new()
Add-Type -AssemblyName System.Runtime.WindowsRuntime

$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Storage.StorageFile, Windows.Foundation, ContentType = WindowsRuntime]

$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq "AsTask" -and
    $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq "IAsyncOperation``1"
})[0]

function Await($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    $netTask.Result
}

$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($Path)) ([Windows.Storage.StorageFile])
$stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if ($null -eq $engine) {
    throw "No OCR language pack is available for the current user."
}
$result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])

$lines = @()
foreach ($line in $result.Lines) {
    $words = @()
    foreach ($word in $line.Words) {
        $r = $word.BoundingRect
        $words += [pscustomobject]@{
            text = $word.Text
            x = [math]::Round($r.X, 1)
            y = [math]::Round($r.Y, 1)
            w = [math]::Round($r.Width, 1)
            h = [math]::Round($r.Height, 1)
        }
    }
    $minX = ($words | Measure-Object -Property x -Minimum).Minimum
    $minY = ($words | Measure-Object -Property y -Minimum).Minimum
    $maxX = ($words | Measure-Object -Property x -Maximum).Maximum
    $maxY = ($words | Measure-Object -Property y -Maximum).Maximum
    $maxW = ($words | Measure-Object -Property w -Maximum).Maximum
    $maxH = ($words | Measure-Object -Property h -Maximum).Maximum
    $lines += [pscustomobject]@{
        text = $line.Text
        x = [math]::Round($minX, 1)
        y = [math]::Round($minY, 1)
        w = [math]::Round(($maxX + $maxW) - $minX, 1)
        h = [math]::Round($maxH, 1)
        words = $words
    }
}

[pscustomobject]@{
    width = $decoder.PixelWidth
    height = $decoder.PixelHeight
    text = ($lines | ForEach-Object { $_.text }) -join "`n"
    lines = $lines
} | ConvertTo-Json -Depth 5 -Compress
