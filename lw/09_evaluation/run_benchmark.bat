@echo off
REM ----------------------------------------------------------------------
REM Phase 2 benchmark runner — Concordance Engine vs 722-claim dataset
REM
REM Double-click this file from Windows Explorer, OR run from PowerShell:
REM     .\run_benchmark.bat
REM
REM What it does:
REM   1. checks Python is on PATH
REM   2. installs sympy / scipy / numpy if missing
REM   3. runs run_benchmark.py with this directory as CWD
REM   4. leaves the window open so you can read the summary
REM
REM Outputs land in this folder:
REM   benchmark_results.jsonl     (one record per claim)
REM   benchmark_summary.json      (aggregate metrics)
REM ----------------------------------------------------------------------

setlocal
cd /d "%~dp0"

echo [1/4] Checking Python...
where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python is not on PATH. Install Python 3.10+ from https://python.org
    pause
    exit /b 2
)
python --version

echo.
echo [2/4] Ensuring required packages (sympy, scipy, numpy) are installed...
python -c "import sympy, scipy, numpy" 2>nul
if errorlevel 1 (
    echo Installing dependencies...
    python -m pip install --quiet sympy scipy numpy
    if errorlevel 1 (
        echo ERROR: pip install failed.
        pause
        exit /b 3
    )
)

echo.
echo [3/4] Running benchmark...
echo (this should take ~30-60 seconds; the T5.3 complexity claims add ~10-20s)
echo.
python run_benchmark.py
set RC=%ERRORLEVEL%

echo.
echo [4/4] Done. Exit code: %RC%
echo.
echo Outputs:
echo   benchmark_results.jsonl
echo   benchmark_summary.json
echo.
echo Now open RESULTS.md and fill in the numbers from benchmark_summary.json.
pause
exit /b %RC%
