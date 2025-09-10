@echo off
echo Building Task Manager Application...

REM Create build directory
if not exist build mkdir build
cd build

REM Configure with CMake
cmake .. -DCMAKE_BUILD_TYPE=Release

REM Build the project
cmake --build . --config Release

if %ERRORLEVEL% EQU 0 (
    echo.
    echo Build successful!
    echo.
    echo To run the application:
    echo   cd build
    echo   .\Release\TaskManager.exe          (Console version)
    echo   .\Release\TaskManagerGUI.exe       (GUI version - if available)
    echo   .\Release\TestClient.exe           (API test client)
    echo.
    echo Default login credentials:
    echo   Super User: admin/admin123
    echo   Manager: manager1/manager123
    echo   Employee: employee1/emp123
    echo.
    echo The console version provides a full interactive interface
    echo with all task management features!
) else (
    echo.
    echo Build failed! Please check the error messages above.
)

pause
