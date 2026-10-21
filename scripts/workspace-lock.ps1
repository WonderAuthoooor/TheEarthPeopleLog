param(
    [Parameter(Mandatory=$true)][ValidateSet('Acquire','Status','Release')][string]$Action,
    [string]$Owner,
    [string]$Summary,
    [string]$Token
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$coordDir = Join-Path $projectRoot '.coordination'
$lockPath = Join-Path $coordDir 'workspace.lock.json'
$utf8 = New-Object System.Text.UTF8Encoding($false)
if ($Action -eq 'Acquire') {
    if ([string]::IsNullOrWhiteSpace($Owner)) { throw 'Owner is required.' }
    [System.IO.Directory]::CreateDirectory($coordDir) | Out-Null
    $record = [ordered]@{
        owner = $Owner
        token = [guid]::NewGuid().ToString()
        acquired_at = [DateTimeOffset]::UtcNow.ToString('o')
        summary = $Summary
    }
    try {
        $stream = [System.IO.File]::Open($lockPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
    } catch {
        throw "Lock acquisition failed. Do not overwrite another session's lock. $($_.Exception.Message)"
    }
    try {
        $bytes = $utf8.GetBytes(($record | ConvertTo-Json))
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush()
    } finally { $stream.Dispose() }
    $record | ConvertTo-Json
    exit 0
}
if (-not (Test-Path -LiteralPath $lockPath)) {
    if ($Action -eq 'Release') { throw 'No lock exists; nothing released.' }
    '{"locked":false}'
    exit 0
}
$record = Get-Content -Raw -Encoding UTF8 -LiteralPath $lockPath | ConvertFrom-Json
if ($Action -eq 'Status') { $record | ConvertTo-Json; exit 0 }
if ([string]::IsNullOrWhiteSpace($Token) -or $Token -cne $record.token) {
    throw 'Token mismatch; lock was not released.'
}
Remove-Item -LiteralPath $lockPath
'{"released":true}'
