# Same CLI as evaluate_local.sh. Paths are relative to the caller's directory.
$ErrorActionPreference = 'Stop'
$pythonCommand = if ($env:PYTHON) { $env:PYTHON } else { 'python' }
$forward = @()
for ($i = 0; $i -lt $args.Count; $i++) {
    if ($args[$i] -eq '--python') {
        if ($i + 1 -ge $args.Count) {
            [Console]::Error.WriteLine('--python requires an executable')
            exit 2
        }
        $i++
        $pythonCommand = [string]$args[$i]
    } else {
        $forward += [string]$args[$i]
    }
}
try {
    & $pythonCommand (Join-Path $PSScriptRoot '..\eval.py') @forward
    exit $LASTEXITCODE
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 2
}
