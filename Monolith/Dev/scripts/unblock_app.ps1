# Unblock Overcontrol files recursively
# This removes the "Mark of the Web" which often triggers Smart App Control

$distPath = Join-Path $PSScriptRoot "..\dist\Overcontrol"

if (Test-Path $distPath) {
    Write-Host "Unblocking files in: $distPath" -ForegroundColor Cyan
    Get-ChildItem -Path $distPath -Recurse | Unblock-File
    Write-Host "Successfully unblocked all files." -ForegroundColor Green
} else {
    Write-Host "Distribution folder not found at: $distPath" -ForegroundColor Yellow
    Write-Host "Please build the application first using 'python scripts\build_exe.py'."
}
