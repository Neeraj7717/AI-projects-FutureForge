@echo off
echo ========================================
echo    Task Manager - Clean & Rebuild
echo ========================================
echo.

echo This will clean all build files and rebuild everything from scratch.
echo.
set /p confirm="Are you sure? (y/N): "
if /i not "%confirm%"=="y" (
    echo Operation cancelled.
    pause
    exit /b
)

echo.
echo Cleaning build directory...
if exist "build" (
    rmdir /s /q "build"
    echo Build directory cleaned.
) else (
    echo No build directory found.
)

echo.
echo Cleaning vcpkg packages...
if exist "vcpkg\installed" (
    rmdir /s /q "vcpkg\installed"
    echo vcpkg packages cleaned.
) else (
    echo No vcpkg packages found.
)

echo.
echo Cleaning database...
if exist "taskmanager.db" (
    del "taskmanager.db"
    echo Database cleaned.
) else (
    echo No database found.
)

echo.
echo All clean! Now running full setup...
echo.
call startapp.bat
