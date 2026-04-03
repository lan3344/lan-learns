param(
    [string]$msg = "(no content)",
    [string]$tag = "EMERGENCY"
)
$d = Get-Date -Format "yyyy-MM-dd"
$t = Get-Date -Format "HH:mm:ss"
$diary = "C:\Users\yyds\WorkBuddy\Claw\.workbuddy\memory\$d.md"
$dir = Split-Path $diary
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
if (-not (Test-Path $diary)) { Set-Content -Path $diary -Value "# $d`n" -Encoding UTF8 }
$entry = "`n## $t [$tag]`n`n$msg`n"
Add-Content -Path $diary -Value $entry -Encoding UTF8
$lines = (Get-Content $diary -Encoding UTF8).Count
Write-Host "[OK] Written: $diary ($lines lines)"
if ($lines -gt 600) { Write-Host "[WARN] Over 600 lines - compact recommended" }
