# Runs every check required before work is called done (see AGENTS.md).
# Usage, from anywhere:  .\scripts\check.ps1
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$python = ".\.venv\Scripts\python.exe"

$steps = [ordered]@{
    "Ruff lint"          = @("-m", "ruff", "check", ".")
    "Ruff format"        = @("-m", "ruff", "format", "--check", ".")
    "Django checks"      = @("manage.py", "check")
    "Missing migrations" = @("manage.py", "makemigrations", "--check", "--dry-run")
    # --noinput: a test database left by an interrupted run is replaced
    # instead of stopping at Django's "delete it?" prompt.
    "Tests"              = @("-m", "coverage", "run", "manage.py", "test", "--noinput")
    "Coverage report"    = @("-m", "coverage", "report")
}

foreach ($name in $steps.Keys) {
    Write-Host "==> $name" -ForegroundColor Cyan
    $stepArgs = $steps[$name]
    & $python @stepArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAILED: $name" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}
Write-Host "All checks passed." -ForegroundColor Green
