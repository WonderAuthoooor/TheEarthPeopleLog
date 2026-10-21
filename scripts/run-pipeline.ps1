param([Parameter(ValueFromRemainingArguments=$true)][string[]]$PipelineArgs)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$pythonCandidate = $env:EARTHLOG_PYTHON
if (-not $pythonCandidate) {
    $bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $bundledPython) { $pythonCandidate = $bundledPython }
}
if (-not $pythonCandidate) {
    $pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($pythonCommand -and $pythonCommand.Source -notlike '*WindowsApps*') { $pythonCandidate = $pythonCommand.Source }
}
if (-not $pythonCandidate) { throw 'Python 3.12+ is required. Set EARTHLOG_PYTHON to its executable.' }
& $pythonCandidate -X utf8 -m pipeline @PipelineArgs
exit $LASTEXITCODE
