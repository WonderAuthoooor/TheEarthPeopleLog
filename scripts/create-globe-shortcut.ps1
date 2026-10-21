$ErrorActionPreference = 'Stop'
$globeRepo = Split-Path -Parent $PSScriptRoot
$globeVersionText = Get-Content -LiteralPath (Join-Path $globeRepo 'globe_app\__init__.py') -Raw -Encoding UTF8
$globeVersion = [regex]::Match($globeVersionText, '__version__ = "([^"]+)"').Groups[1].Value
$globeExe = Join-Path $globeRepo "dist\globe\$globeVersion\EarthPeopleLogGlobe\EarthPeopleLogGlobe.exe"
if (-not (Test-Path -LiteralPath $globeExe)) { throw 'Build the location app first.' }
$globeShell = New-Object -ComObject WScript.Shell
$globeShortcut = $globeShell.CreateShortcut((Join-Path $globeRepo '地球地点动画.lnk'))
$globeShortcut.TargetPath = $globeExe
$globeShortcut.Arguments = '--workspace "' + (Join-Path $globeRepo '.globe') + '"'
$globeShortcut.IconLocation = $globeExe + ',0'
$globeShortcut.WorkingDirectory = $globeRepo
$globeShortcut.Description = '独立城市定位与地球开场／转场，输出MP4'
$globeShortcut.Save()
Write-Output (Join-Path $globeRepo '地球地点动画.lnk')
