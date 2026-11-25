# Runs every check required before work is called done (see AGENTS.md).
#
# Usage, from anywhere:
#   .\scripts\check.ps1                 Full check: run before every commit.
#   .\scripts\check.ps1 -Quick          Same checks and the whole test suite,
#                                       without coverage: run after each change.
#   .\scripts\check.ps1 -Quick -Tests apps.songs apps.lineups
#                                       Only these apps' tests, while working
#                                       on them. Never enough on its own to
#                                       call work done.
#   -Workers N                          Parallel test processes (default 4).
param(
    [switch]$Quick,
    [string[]]$Tests = @(),
    [int]$Workers = 4
)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$python = ".\.venv\Scripts\python.exe"
# One maths thread per test process: numpy's OpenBLAS otherwise sets aside
# memory for every CPU core in each of the parallel processes, which can run
# Windows out of memory when the C: drive is nearly full.
$env:OPENBLAS_NUM_THREADS = "1"
$env:OMP_NUM_THREADS = "1"

# --noinput: a test database left by an interrupted run is replaced instead
# of stopping at Django's "delete it?" prompt.
$testArgs = @("manage.py", "test", "--noinput", "--parallel", "$Workers") + $Tests

$steps = [ordered]@{
    "Ruff lint"          = @("-m", "ruff", "check", ".")
    "Ruff format"        = @("-m", "ruff", "format", "--check", ".")
    "Django checks"      = @("manage.py", "check")
    "Missing migrations" = @("manage.py", "makemigrations", "--check", "--dry-run")
}
if ($Quick) {
    $steps["Tests"] = $testArgs
} else {
    $steps["Clear old coverage"] = @("-m", "coverage", "erase")
    $steps["Tests"] = @("-m", "coverage", "run") + $testArgs
    $steps["Combine coverage"] = @("-m", "coverage", "combine", "--quiet")
    $steps["Coverage report"] = @("-m", "coverage", "report")
}

$started = Get-Date
foreach ($name in $steps.Keys) {
    Write-Host "==> $name" -ForegroundColor Cyan
    $stepArgs = $steps[$name]
    & $python @stepArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAILED: $name" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}
$seconds = [int]((Get-Date) - $started).TotalSeconds
if ($Quick) {
    Write-Host "Quick checks passed in ${seconds}s. Run the full check before committing." -ForegroundColor Yellow
} else {
    Write-Host "All checks passed in ${seconds}s." -ForegroundColor Green
}
