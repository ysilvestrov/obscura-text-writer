param([int]$Port=8765,[string]$DataDir='')
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
$pythonPath=Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    Write-Error 'Немає .venv. Створіть середовище Python та встановіть пакет: pip install -e ".[web]". Див. docs/prototype-runbook.md.'
    exit 1
}
if (-not $DataDir) { $DataDir=Join-Path $projectRoot 'data' }
& $pythonPath -m storygen.server --data-dir $DataDir --env-file (Join-Path $projectRoot '.env') --port $Port --open-browser
exit $LASTEXITCODE
