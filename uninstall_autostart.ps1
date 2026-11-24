Remove-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "SimiWellnessCompanion" -ErrorAction SilentlyContinue
Write-Host "Removed Simi from Windows auto-start." -ForegroundColor Yellow
