@echo off
echo ========================================
echo    Task Manager - Available Scripts
echo ========================================
echo.

echo Available scripts:
echo.
echo 1. startapp.bat          - Full setup and start (first time)
echo    ^|  Installs all dependencies, builds, and runs
echo    ^|  Use this for first-time setup
echo.
echo 2. startapp_quick.bat    - Quick start (if already built)
echo    ^|  Skips dependency installation
echo    ^|  Use this for subsequent runs
echo.
echo 3. clean_and_rebuild.bat - Clean everything and rebuild
echo    ^|  Removes all build files and starts fresh
echo    ^|  Use this if you encounter build issues
echo.
echo 4. build.bat             - Build only (manual)
echo    ^|  Just builds the project without running
echo    ^|  Use this for development
echo.
echo 5. setup_dependencies.bat - Install dependencies only
echo    ^|  Just installs vcpkg and C++ libraries
echo    ^|  Use this for manual setup
echo.
echo 6. help.bat              - Show this help
echo    ^|  Displays all available scripts
echo.
echo ========================================
echo    Recommended Usage
echo ========================================
echo.
echo For first time:     startapp.bat
echo For daily use:      startapp_quick.bat
echo If issues occur:    clean_and_rebuild.bat
echo.
echo ========================================
echo    Application Features
echo ========================================
echo.
echo - Console-based task management interface
echo - Role-based access control (Super User, Manager, Employee)
echo - Full CRUD operations for tasks
echo - User management system
echo - REST API backend
echo - Real-time updates
echo.
echo Default login credentials:
echo   Super User: admin / admin123
echo   Manager: manager1 / manager123
echo   Employee: employee1 / emp123
echo.
pause
