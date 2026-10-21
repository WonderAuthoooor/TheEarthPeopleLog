$ErrorActionPreference = 'Stop'
$studioRoot = Split-Path -Parent $PSScriptRoot
$studioVersionText = Get-Content -LiteralPath (Join-Path $studioRoot 'studio\__init__.py') -Raw -Encoding UTF8
$studioVersion = [regex]::Match($studioVersionText, '__version__ = "([^"]+)"').Groups[1].Value
if (-not $studioVersion) { throw 'Cannot read application version.' }
$studioExe = Join-Path $studioRoot "dist\$studioVersion\EarthPeopleLogStudio\EarthPeopleLogStudio.exe"
if (-not (Test-Path -LiteralPath $studioExe)) { throw 'Build the desktop application first.' }
$studioShell = New-Object -ComObject WScript.Shell
$studioShortcut = $studioShell.CreateShortcut((Join-Path $studioRoot '地球人日志工作室.lnk'))
$studioShortcut.TargetPath = $studioExe
$studioShortcut.Arguments = '--workspace "' + (Join-Path $studioRoot '.studio') + '"'
$studioShortcut.IconLocation = $studioExe + ',0'
$studioShortcut.WorkingDirectory = $studioRoot
$studioShortcut.Description = '地球人日志工作室：项目、素材、文稿与草稿导出'
$studioShortcut.Save()
Write-Output (Join-Path $studioRoot '地球人日志工作室.lnk')
