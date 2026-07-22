@echo off
REM Repo-root launcher: resolves Python 3.13 (avoids the Anaconda 3.10 on PATH)
REM and forwards all args to the orchestrator.  Usage:  run doctor | run run | run kpi ...
REM User-agnostic resolution order: current user's per-user Python 3.13, then the
REM `py` launcher (3.13 -> 3.12), then a bare `python` on PATH.
setlocal
set "PYTHONIOENCODING=utf-8"
set "PY="
set "LOCALPY=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if exist "%LOCALPY%" set "PY=%LOCALPY%"
if not defined PY py -3.13 --version >nul 2>&1 && set "PY=py -3.13"
if not defined PY py -3.12 --version >nul 2>&1 && set "PY=py -3.12"
if not defined PY set "PY=python"
%PY% "%~dp0src\orchestrator.py" %*
