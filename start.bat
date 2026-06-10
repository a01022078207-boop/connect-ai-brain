@echo off
chcp 65001 >nul
title Creator Agent
cd /d "%~dp0"

set PY=
where py >nul 2>nul && set PY=py
if not defined PY where python >nul 2>nul && set PY=python
if not defined PY (
  echo.
  echo  [!] Python is not installed.
  echo      https://www.python.org/downloads/ - install and CHECK "Add Python to PATH"
  echo.
  pause
  exit /b 1
)

%PY% agent.py
echo.
pause
