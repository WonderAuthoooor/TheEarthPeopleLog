$ErrorActionPreference = 'Stop'
$avatarRepo = Split-Path -Parent $PSScriptRoot
$avatarVersionText = Get-Content -LiteralPath (Join-Path $avatarRepo 'avatar_app/__init__.py') -Raw -Encoding UTF8
$avatarVersion = [regex]::Match($avatarVersionText, '__version__ = "([^"]+)"').Groups[1].Value
$avatarExe = Join-Path $avatarRepo "dist/avatar/$avatarVersion/EarthPeopleLogAvatar/EarthPeopleLogAvatar.exe"
if (-not (Test-Path -LiteralPath $avatarExe)) { throw 'Build the avatar app first.' }
$avatarShell = New-Object -ComObject WScript.Shell
$avatarShortcut = $avatarShell.CreateShortcut((Join-Path $avatarRepo '地球角色工坊.lnk'))
$avatarShortcut.TargetPath = $avatarExe
$avatarShortcut.Arguments = '--workspace "' + (Join-Path $avatarRepo '.avatar') + '"'
$avatarShortcut.IconLocation = $avatarExe + ',0'
$avatarShortcut.WorkingDirectory = $avatarRepo
$avatarShortcut.Description = '独立虚拟角色分层试验版；透明MOV素材导出'
$avatarShortcut.Save()
Write-Output (Join-Path $avatarRepo '地球角色工坊.lnk')
