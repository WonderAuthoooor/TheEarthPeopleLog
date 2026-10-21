$ErrorActionPreference = 'Stop'
$avatarSetupRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $avatarSetupRoot
$avatarPython = $env:EARTHLOG_PYTHON
if (-not $avatarPython) { $avatarPython = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' }
if (-not (Test-Path -LiteralPath $avatarPython)) { throw 'Set EARTHLOG_PYTHON to an existing Python executable.' }
New-Item -ItemType Directory -Force '.runtime/avatar-live-wheels' | Out-Null
& $avatarPython -m pip download --only-binary=:all: --no-deps --dest .runtime/avatar-live-wheels -r requirements-avatar-live.txt --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { throw 'Tracking dependency download failed.' }
# Environment override is scoped to this Python child; global TEMP / Python remain unchanged.
@'
import subprocess,sys,os
from pathlib import Path
temp=Path('.runtime/avatar-pip-tmp').resolve();temp.mkdir(parents=True,exist_ok=True)
env=os.environ.copy();env['TEMP']=str(temp);env['TMP']=str(temp)
subprocess.run([sys.executable,'-m','pip','install','--no-index','--no-deps','--upgrade',
    '--target','.runtime/avatar-live-python','--find-links','.runtime/avatar-live-wheels',
    '-r','requirements-avatar-live.txt','--disable-pip-version-check'],env=env,check=True)
import hashlib,json,urllib.request
folder=Path('avatar_app/assets/tracking')
source=json.loads((folder/'models-source.json').read_text(encoding='utf-8'))
for item in source['models']:
    path=folder/item['file']
    if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest()==item['sha256']:
        continue
    if path.exists():
        raise RuntimeError('Model hash mismatch; inspect existing file before replacing: '+str(path))
    with urllib.request.urlopen(item['url'],timeout=60) as response:data=response.read()
    if hashlib.sha256(data).hexdigest()!=item['sha256']:raise RuntimeError('Downloaded model hash mismatch')
    path.write_bytes(data)
print('Local tracking dependencies and pinned models ready. Camera has not been opened.')
'@ | & $avatarPython -X utf8 -
if ($LASTEXITCODE -ne 0) { throw 'Tracking setup failed.' }
