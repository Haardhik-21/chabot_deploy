@echo off
echo Starting Healthcare AI Assistant...
echo.

echo Starting Backend Server...
start "Backend" cmd /k "cd /d backend && python -m uvicorn main:app --reload --port 8000"

timeout /t 3 /nobreak > nul

echo Starting Frontend Server...
start "Frontend" cmd /k "cd /d frontend && npm start"

echo.
echo Both servers are starting...
echo Backend: http://localhost:8000
echo Frontend: http://localhost:3000
echo.
echo Press any key to exit...
pause > nul
