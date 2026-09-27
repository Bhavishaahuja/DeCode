@echo off
setlocal

cd /d "%~dp0"

set "HOST_SHELL=Command Prompt"
for /f "usebackq delims=" %%S in (`powershell -NoProfile -Command "$child = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $PID); $cmd = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $child.ParentProcessId); $parent = Get-Process -Id $cmd.ParentProcessId -ErrorAction SilentlyContinue; if ($parent.ProcessName -match '^(powershell|pwsh)$') { 'PowerShell' } else { 'Command Prompt' }"`) do set "HOST_SHELL=%%S"

echo Starting DeCode from %HOST_SHELL%...
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: DeCode virtual environment was not found.
    echo Run the setup instructions first.
    exit /b 1
)

if not exist ".env" (
    echo ERROR: .env was not found.
    echo Run the setup instructions first.
    exit /b 1
)

echo Building DeCode data...
".venv\Scripts\python.exe" -m data.build
if errorlevel 1 (
    echo.
    echo ERROR: Data build failed. Services were not started.
    exit /b 1
)

echo.
echo Starting Tools API on port 8001...
start "DeCode Tools" cmd /k ""%CD%\.venv\Scripts\python.exe" -m uvicorn tools.app:app --port 8001"

echo Starting Agents API on port 8000...
start "DeCode Agents" cmd /k ""%CD%\.venv\Scripts\python.exe" -m uvicorn agents.server:app --port 8000"

echo Starting Web app on port 5173...
start "DeCode Web" cmd /k ""%CD%\.venv\Scripts\python.exe" -m http.server 5173 --directory web"

echo.
echo Opening DeCode...
start "" "http://localhost:5173"

echo.
echo DeCode startup complete.
endlocal
