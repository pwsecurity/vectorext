@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ##########################################
echo # VECTOR NEURAL BRIDGE BUILDER           #
echo ##########################################
echo.

:: 1. Locating .NET Compiler
echo [1/3] Locating system compiler (csc.exe)...
set "CSC="
set "DOTNET_PATH=C:\Windows\Microsoft.NET\Framework64\v4.0.30319"
if exist "!DOTNET_PATH!\csc.exe" (
    set "CSC=!DOTNET_PATH!\csc.exe"
) else (
    set "DOTNET_PATH=C:\Windows\Microsoft.NET\Framework\v4.0.30319"
    if exist "!DOTNET_PATH!\csc.exe" (
        set "CSC=!DOTNET_PATH!\csc.exe"
    )
)

if "!CSC!"=="" (
    echo [ERROR]: .NET Framework 4.5+ not found. Compilation aborted.
    pause
    exit /b 1
)
echo Found: !CSC!

echo.
echo ==========================================
echo = SPECIAL: OPTION [P] - NEURAL PURGE    =
echo = Use this if you get error on restart! =
echo ==========================================
set /p opt="Build EXE (Enter) or Purge Old Versions (P)? "
if /i "!opt!"=="P" (
    echo [PURGE]: Terminating all Vector processes...
    taskkill /F /IM VectorDeviceManager.exe /T >nul 2>&1
    taskkill /F /IM vector_bridge.exe /T >nul 2>&1
    echo [PURGE]: Wiping legacy data...
    rd /s /q "%LOCALAPPDATA%\VectorAI" >nul 2>&1
    echo [SUCCESS]: System cleaned. Now run Build again normally.
    pause
    exit /b 0
)

:: 2. Compiling
echo [2/3] Compiling VectorDeviceManager.exe (Any CPU)...
"!CSC!" /out:VectorDeviceManager.exe /target:winexe /platform:anycpu VectorDeviceManager.cs /reference:System.Windows.Forms.dll,System.Drawing.dll,System.Management.dll /nologo

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR]: Compilation failed. Check your security settings.
    pause
    exit /b 1
)

:: 3. Verification
echo [3/3] Engineering complete.
echo.
echo ##########################################
echo # SUCCESS: VectorDeviceManager.exe ready #
echo ##########################################
echo.
echo You can now run VectorDeviceManager.exe as Administrator.
pause
