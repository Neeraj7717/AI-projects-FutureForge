@echo off
echo ========================================
echo    Task Manager Application Launcher
echo ========================================
echo.

REM Check if running as administrator
net session >nul 2>&1
if %errorLevel% == 0 (
    echo Running with administrator privileges...
) else (
    echo WARNING: Not running as administrator. Some operations may fail.
    echo If you encounter issues, please run this script as administrator.
    echo.
)

REM Set error handling
setlocal enabledelayedexpansion

REM Check if vcpkg exists
if not exist "vcpkg" (
    echo Installing vcpkg package manager...
    echo.
    
    REM Clone vcpkg
    git clone https://github.com/Microsoft/vcpkg.git
    if !errorLevel! neq 0 (
        echo ERROR: Failed to clone vcpkg. Please check your internet connection.
        pause
        exit /b 1
    )
    
    REM Bootstrap vcpkg
    cd vcpkg
    call bootstrap-vcpkg.bat
    if !errorLevel! neq 0 (
        echo ERROR: Failed to bootstrap vcpkg.
        pause
        exit /b 1
    )
    cd ..
    
    echo vcpkg installed successfully!
    echo.
) else (
    echo vcpkg already exists, skipping installation...
    echo.
)

REM Check if dependencies are installed
echo Checking dependencies...
if not exist "vcpkg\installed\x64-windows" (
    echo Installing C++ dependencies...
    echo This may take several minutes on first run...
    echo.
    
    REM Install dependencies
    vcpkg\vcpkg.exe install cpprestsdk:x64-windows sqlite3:x64-windows spdlog:x64-windows nlohmann-json:x64-windows --triplet x64-windows
    if !errorLevel! neq 0 (
        echo ERROR: Failed to install dependencies.
        echo Please check your Visual Studio installation and try again.
        pause
        exit /b 1
    )
    
    echo Dependencies installed successfully!
    echo.
) else (
    echo Dependencies already installed, skipping...
    echo.
)

REM Check if CMake exists
where cmake >nul 2>&1
if %errorLevel% neq 0 (
    echo ERROR: CMake not found in PATH.
    echo Please install CMake and add it to your system PATH.
    echo Download from: https://cmake.org/download/
    pause
    exit /b 1
)

REM Check if Visual Studio Build Tools exist
where cl >nul 2>&1
if %errorLevel% neq 0 (
    echo ERROR: Visual Studio Build Tools not found.
    echo Please install Visual Studio Build Tools 2022 with C++ workload.
    echo Download from: https://visualstudio.microsoft.com/downloads/
    pause
    exit /b 1
)

REM Create build directory
if not exist "build" (
    echo Creating build directory...
    mkdir build
)

REM Navigate to build directory
cd build

REM Configure CMake
echo Configuring project with CMake...
cmake .. -DCMAKE_BUILD_TYPE=Release -DCMAKE_TOOLCHAIN_FILE=../vcpkg/scripts/buildsystems/vcpkg.cmake
if !errorLevel! neq 0 (
    echo ERROR: CMake configuration failed.
    echo Please check the error messages above.
    pause
    exit /b 1
)

REM Build the project
echo Building project...
echo This may take a few minutes...
cmake --build . --config Release
if !errorLevel! neq 0 (
    echo ERROR: Build failed.
    echo Please check the error messages above.
    pause
    exit /b 1
)

echo.
echo ========================================
echo    Build Successful!
echo ========================================
echo.

REM Check if executables exist
if exist "Release\TaskManager.exe" (
    echo Task Manager Console Application: READY
) else (
    echo WARNING: TaskManager.exe not found
)

if exist "Release\TaskManagerGUI.exe" (
    echo Task Manager GUI Application: READY
) else (
    echo Task Manager GUI Application: Not available (ImGui not properly configured)
)

if exist "Release\TestClient.exe" (
    echo API Test Client: READY
) else (
    echo WARNING: TestClient.exe not found
)

echo.
echo ========================================
echo    Starting Application...
echo ========================================
echo.

REM Start the application
if exist "Release\TaskManager.exe" (
    echo Starting Task Manager Console Application...
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
) else (
    echo ERROR: TaskManager.exe not found. Cannot start application.
    pause
    exit /b 1
)

echo.
echo Application closed.
pause
