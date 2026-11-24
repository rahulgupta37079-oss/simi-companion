# Registers Floating Simi Companion to auto-start silently when Windows boots (no console window)
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonExe = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $PythonExe) {
    $PythonExe = (Get-Command python.exe).Source
}

$ScriptPath = Join-Path $ProjectDir "run_simi.py"
$Cmd = "`"$PythonExe`" `"$ScriptPath`""

New-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" `
    -Name "SimiWellnessCompanion" `
    -Value $Cmd `
    -PropertyType String `
    -Force | Out-Null

Write-Host "Simi floating companion is now registered to auto-start on Windows login!" -ForegroundColor Green
Write-Host "Command: $Cmd"
