@echo off
REM ============================================================================
REM  dev_electron.bat  —  Dev-test the Electron desktop app (PDF Extractor V3)
REM ----------------------------------------------------------------------------
REM  Use this (NOT start_v3.py) to test Electron-only features such as the
REM  one-click "Sign in to ICA" browser-assisted login. A plain browser has no
REM  window.electronAPI, so that button is disabled there.
REM
REM  What it does:
REM    1. Builds the frontend (Vite) into frontend/dist
REM    2. Copies the build into electron/renderer (what main.js loads in dev is
REM       frontend/dist, but we keep renderer in sync for packaged parity)
REM    3. Launches Electron, which auto-spawns the Python backend (python main.py)
REM
REM  Requirements: npm, python on PATH (same as start_v3.py).
REM ============================================================================
setlocal
set "ROOT=%~dp0"
set "FRONTEND=%ROOT%frontend"
set "ELECTRON=%ROOT%electron"

echo(
echo ============================================================
echo   PDF Extractor V3  -  Electron Dev Test
echo ============================================================
echo(

echo [1/3] Building frontend (Vite)...
pushd "%FRONTEND%"
call npm run build
if errorlevel 1 (
  echo(
  echo   Frontend build FAILED. Aborting.
  popd
  exit /b 1
)
popd

echo(
echo [2/3] Syncing build into electron\renderer ...
if not exist "%ELECTRON%\renderer" mkdir "%ELECTRON%\renderer"
robocopy "%FRONTEND%\dist" "%ELECTRON%\renderer" /MIR /NFL /NDL /NJH /NJS /NP >nul
REM robocopy exit codes 0-7 are success; anything >=8 is a real error.
if errorlevel 8 (
  echo   robocopy reported an error copying the build.
  exit /b 1
)

echo(
echo [3/3] Launching Electron (backend auto-spawns)...
echo   Close the app window to stop.
echo(
pushd "%ELECTRON%"
call npm start
popd

endlocal
