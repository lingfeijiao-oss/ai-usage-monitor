$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $Root

if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 "$Root\src\ui\desktop_app.py" @args
}
elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python "$Root\src\ui\desktop_app.py" @args
}
else {
    throw 'Python 3 was not found.'
}
