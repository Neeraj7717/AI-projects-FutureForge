@echo off
REM API Server Startup Script for Windows
REM 
REM This script provides a simple way to start the API server
REM with proper error handling and logging.

echo 🚀 Starting API Server...
echo 📁 Working directory: %CD%
echo ⏰ Started at: %date% %time%
echo.

REM Check if package.json exists
if not exist "package.json" (
    echo ❌ Error: package.json not found in current directory
    echo Please run this script from the project root directory
    pause
    exit /b 1
)

REM Check if node_modules exists
if not exist "node_modules" (
    echo 📦 Installing dependencies...
    npm install
    if errorlevel 1 (
        echo ❌ Failed to install dependencies
        pause
        exit /b 1
    )
)

echo 🔧 Starting server...
echo 🌐 Server will be available at: http://localhost:3000
echo 📖 API Documentation: http://localhost:3000/api/health
echo 📝 Logs will be written to: combined.log and error.log
echo.
echo Press Ctrl+C to stop the server
echo.

REM Start the server
node server.js

REM If we get here, the server has exited
if errorlevel 1 (
    echo ❌ Server exited with error
    pause
    exit /b 1
) 