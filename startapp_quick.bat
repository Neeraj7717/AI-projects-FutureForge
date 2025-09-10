@echo off
echo ========================================
echo    Task Manager - Quick Start
echo ========================================
echo.

REM Check if build directory exists
if not exist "build" (
    echo Build directory not found. Running full setup...
    call startapp.bat
    exit /b
)

REM Navigate to build directory
cd build

REM Check if executables exist
if not exist "Release\TaskManager.exe" (
    echo Executables not found. Running full build...
    cd ..
    call startapp.bat
    exit /b
)

echo Starting Task Manager Application...
echo.
echo Default login credentials:
echo   Super User: admin / admin123
echo   Manager: manager1 / manager123  
echo   Employee: employee1 / emp123
echo.
echo The application will start the backend server automatically.
echo Press Ctrl+C to stop the application.
echo.
pause
echo.
echo Launching Task Manager...
echo.
Release\TaskManager.exe

echo.
echo Application closed.
pause
