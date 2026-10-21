$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$pythonCandidate = $env:EARTHLOG_PYTHON
if (-not $pythonCandidate) {
    $pythonCandidate = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
}
if (-not (Test-Path -LiteralPath $pythonCandidate)) { throw 'Set EARTHLOG_PYTHON to an existing Python executable.' }
New-Item -ItemType Directory -Force '.runtime/wheels' | Out-Null
& $pythonCandidate -m pip download --only-binary=:all: --no-deps --dest .runtime/wheels -r requirements-pipeline.txt --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { throw 'Dependency download failed.' }
& $pythonCandidate -c "from pathlib import Path; import zipfile; target=Path('.runtime/python'); target.mkdir(parents=True,exist_ok=True); [zipfile.ZipFile(p).extractall(target) for p in Path('.runtime/wheels').glob('*.whl')]; print('Project dependencies ready')"
if ($LASTEXITCODE -ne 0) { throw 'Dependency extraction failed.' }
& $pythonCandidate -X utf8 -m pipeline doctor
exit $LASTEXITCODE
