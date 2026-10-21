$ErrorActionPreference = 'Stop'
$threeDRepo = Split-Path -Parent $PSScriptRoot
$threeDVersionText = Get-Content -LiteralPath (Join-Path $threeDRepo 'avatar3d/__init__.py') -Raw -Encoding UTF8
$threeDVersion = [regex]::Match($threeDVersionText, '__version__ = "([^"]+)"').Groups[1].Value
$threeDExe = Join-Path $threeDRepo "dist/avatar3d/$threeDVersion/EarthPeopleLogAvatar3D/EarthPeopleLogAvatar3D.exe"
if (-not (Test-Path -LiteralPath $threeDExe)) { throw 'Build the 3D app first.' }
$threeDShell = New-Object -ComObject WScript.Shell
$threeDShortcut = $threeDShell.CreateShortcut((Join-Path $threeDRepo '地球三维角色工坊.lnk'))
$threeDShortcut.TargetPath = $threeDExe
$threeDShortcut.Arguments = '--workspace "' + (Join-Path $threeDRepo '.avatar3d') + '" --runtime "' + (Join-Path $threeDRepo '.runtime/avatar3d/runtime.json') + '"'
$threeDShortcut.IconLocation = $threeDExe + ',0'
$threeDShortcut.WorkingDirectory = $threeDRepo
$threeDShortcut.Description = '三维模型／骨骼动作与透明素材；正式C模型待制作'
$threeDShortcut.Save()
Write-Output (Join-Path $threeDRepo '地球三维角色工坊.lnk')
