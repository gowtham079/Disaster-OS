@echo off
setlocal

echo ==============================================
echo Multi-Agent Disaster Management - Quick Start
echo ==============================================
echo.

set "ROOT_DIR=%~dp0"

echo [1/3] Starting backend API...
start "Backend API (FastAPI)" cmd /k "cd /d "%ROOT_DIR%Multi-Agent-System" && python app.py"

echo [2/3] Starting UI dashboard...
start "UI Dashboard (React)" cmd /k "cd /d "%ROOT_DIR%multiagent project" && npm start"

echo [3/3] Starting core simulator...
start "Core Simulator (CLI Metrics)" cmd /k "cd /d "%ROOT_DIR%" && python main.py --start --scenarios 3 --seed 42"

echo.
echo Launched all services in separate terminals.
echo - UI:      http://localhost:3000
echo - Backend: http://localhost:8000
echo.
echo If any window shows dependency errors, install once:
echo - cd "%ROOT_DIR%Multi-Agent-System" ^&^& python -m pip install -r requirements.txt
echo - cd "%ROOT_DIR%multiagent project" ^&^& npm install
echo.
pause

