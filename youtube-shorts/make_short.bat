@echo off
chcp 65001 >nul
cd /d %~dp0
if not exist .venv (
  py -m venv .venv
  .venv\Scripts\pip install -r requirements.txt
)
if "%~1"=="" (
  echo 使い方: make_short.bat scripts\001_flamingo.yaml
  pause
  exit /b 1
)
.venv\Scripts\python src\make_short.py %*
pause
