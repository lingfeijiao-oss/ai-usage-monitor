$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $Root

if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 "$Root\scripts\monitor_codex.py" @args
}
elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python "$Root\scripts\monitor_codex.py" @args
}
else {
    throw 'Python 3 was not found.'
}
