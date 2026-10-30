@echo off
chcp 65001 >nul
title Cheongyang Plus - Starter
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (
 set "PY=py -3"
) else (
 set "PY=python"
)
if not exist ".venv\Scripts\python.exe" (
  %PY% -m venv .venv
  if errorlevel 1 (echo Python 3.11+ must be installed. & pause & exit /b 1)
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (echo Package install failed. Check your internet connection. & pause & exit /b 1)
start "Cheongyang Plus Server" ".venv\Scripts\python.exe" run.py
powershell -NoProfile -Command "$ErrorActionPreference='SilentlyContinue';for($i=0;$i -lt 20;$i++){try{$r=Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8787/health' -TimeoutSec 2;if($r.StatusCode -eq 200){exit 0}}catch{};Start-Sleep -Seconds 1};exit 1"
if errorlevel 1 (
 echo Server did not start. Check the Cheongyang Plus Server window.
 pause
 exit /b 1
)
start "" "http://127.0.0.1:8787/admin/login"
echo Customer website: http://127.0.0.1:8787/
echo Administration: http://127.0.0.1:8787/admin/login
exit /b 0
