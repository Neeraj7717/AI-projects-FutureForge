@echo off
echo Setting up Task Manager Dependencies...

REM Check if vcpkg exists
if not exist vcpkg (
    echo Installing vcpkg...
    git clone https://github.com/Microsoft/vcpkg.git
    cd vcpkg
    call bootstrap-vcpkg.bat
    cd ..
) else (
    echo vcpkg already exists, updating...
    cd vcpkg
    git pull
    cd ..
)

echo.
echo Installing required packages with vcpkg...

REM Install packages
vcpkg\vcpkg install cpprestsdk:x64-windows
vcpkg\vcpkg install sqlite3:x64-windows
vcpkg\vcpkg install spdlog:x64-windows
vcpkg\vcpkg install nlohmann-json:x64-windows
vcpkg\vcpkg install openssl:x64-windows

echo.
echo Downloading Dear ImGui...

REM Download Dear ImGui
if not exist third_party\imgui (
    mkdir third_party\imgui
    cd third_party\imgui
    git clone https://github.com/ocornut/imgui.git .
    cd ..\..
)

echo.
echo Dependencies setup complete!
echo.
echo To build the project, run:
echo   build.bat
echo.
echo Or manually:
echo   mkdir build
echo   cd build
echo   cmake .. -DCMAKE_TOOLCHAIN_FILE=..\vcpkg\scripts\buildsystems\vcpkg.cmake
echo   cmake --build . --config Release

pause
