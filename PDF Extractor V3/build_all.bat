@echo off
REM ============================================================
REM  build_all.bat — Full portable build for PDF Extractor V3
REM  Run this from the "PDF Extractor V3" directory.
REM
REM  Prerequisites (one-time):
REM    pip install pyinstaller
REM    cd frontend && npm install && cd ..
REM    cd electron && npm install && cd ..
REM
REM  Output:
REM    electron\dist\PDF-Extractor-V3-Setup-3.0.0.exe   (installer)
REM    electron\dist\PDF-Extractor-V3-Portable-3.0.0.exe (portable single-file)
REM ============================================================

setlocal EnableDelayedExpansion

echo.
echo ============================================================
echo   PDF Extractor V3 - Full Portable Build
echo ============================================================

REM ── Step 1: Build React frontend ─────────────────────────────
echo.
echo [1/4] Building React frontend...
cd frontend
call npm run build
if !errorlevel! neq 0 ( echo ERROR: Frontend build failed && exit /b 1 )
cd ..
echo   Frontend built to electron\renderer\

REM ── Step 2: Build Python backend with PyInstaller ────────────
echo.
echo [2/4] Building Python backend (PyInstaller)...
python build_backend.py
if !errorlevel! neq 0 ( echo ERROR: Backend build failed && exit /b 1 )
echo   Backend exe built to electron\resources\backend\

REM ── Step 3: Build Electron app with electron-builder ─────────
echo.
echo [3/4] Packaging with electron-builder...
REM Skip code-signing so electron-builder does NOT download/extract the
REM winCodeSign package (its macOS symlinks fail to extract on Windows
REM without elevated "Create symbolic links" privilege).
set CSC_IDENTITY_AUTO_DISCOVERY=false
cd electron
call npm run dist

if !errorlevel! neq 0 ( echo ERROR: Electron build failed && exit /b 1 )
cd ..
echo   Packaged to electron\dist\

REM ── Step 4: Summary ──────────────────────────────────────────
echo.
echo ============================================================
echo   BUILD COMPLETE
echo ============================================================
echo.
echo   Installer : electron\dist\PDF-Extractor-V3-Setup-3.0.0.exe
echo   Portable  : electron\dist\PDF-Extractor-V3-Portable-3.0.0.exe
echo.
echo   IMPORTANT: Before distributing, copy your credentials into
echo   the app's data folder (created on first launch):
echo     %%APPDATA%%\PDF Extractor V3\backend\config.json
echo     %%APPDATA%%\PDF Extractor V3\backend\box_jwt_config.json
echo.

endlocal
