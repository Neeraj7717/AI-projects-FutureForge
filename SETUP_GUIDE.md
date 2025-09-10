# Task Manager - Complete Setup Guide

This guide will walk you through setting up the Task Manager C++ desktop application from scratch.

## Prerequisites

### Required Software
- **Windows 10/11** (64-bit)
- **Visual Studio 2019/2022** with C++ development tools
- **Git** (for cloning repositories)
- **CMake 3.16+**

### Optional but Recommended
- **vcpkg** (for dependency management)
- **Postman** (for API testing)

## Quick Start (Automated Setup)

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd TaskManager
   ```

2. **Run the setup script**:
   ```bash
   setup_dependencies.bat
   ```

3. **Build the project**:
   ```bash
   build.bat
   ```

4. **Run the application**:
   ```bash
   cd build
   .\Release\TaskManager.exe
   ```

## Manual Setup (Step by Step)

### Step 1: Install Visual Studio

1. Download Visual Studio 2022 Community (free) from Microsoft
2. During installation, select:
   - Desktop development with C++
   - Windows 10/11 SDK
   - CMake tools for C++

### Step 2: Install Git

1. Download Git from https://git-scm.com/
2. Install with default settings

### Step 3: Install CMake

1. Download CMake from https://cmake.org/
2. During installation, select "Add CMake to system PATH"

### Step 4: Install vcpkg (Dependency Manager)

1. Open Command Prompt as Administrator
2. Navigate to your desired directory (e.g., C:\)
3. Run:
   ```bash
   git clone https://github.com/Microsoft/vcpkg.git
   cd vcpkg
   .\bootstrap-vcpkg.bat
   ```

### Step 5: Install Required Libraries

Open Command Prompt and run:
```bash
vcpkg install cpprestsdk:x64-windows
vcpkg install sqlite3:x64-windows
vcpkg install spdlog:x64-windows
vcpkg install nlohmann-json:x64-windows
vcpkg install openssl:x64-windows
```

### Step 6: Download Dear ImGui

```bash
mkdir third_party\imgui
cd third_party\imgui
git clone https://github.com/ocornut/imgui.git .
cd ..\..
```

### Step 7: Build the Project

1. Open Command Prompt in the project directory
2. Run:
   ```bash
   mkdir build
   cd build
   cmake .. -DCMAKE_TOOLCHAIN_FILE=..\vcpkg\scripts\buildsystems\vcpkg.cmake
   cmake --build . --config Release
   ```

### Step 8: Run the Application

```bash
cd build
.\Release\TaskManager.exe
```

## Project Structure Explained

```
TaskManager/
├── backend/                 # C++ REST API Server
│   ├── include/            # Header files
│   └── src/               # Implementation files
├── frontend/               # Windows Desktop UI
│   ├── include/           # Header files
│   └── src/               # Implementation files
├── include/               # Shared header files
├── src/                   # Main application files
├── third_party/           # External dependencies
│   └── imgui/            # Dear ImGui UI framework
├── CMakeLists.txt         # Build configuration
├── build.bat             # Build script
├── setup_dependencies.bat # Dependency setup script
└── README.md             # Project documentation
```

## API Endpoints Reference

### Authentication
- `POST /auth/login` - User login
- `POST /auth/logout` - User logout

### Tasks
- `GET /tasks` - Get all tasks (role-based filtering)
- `GET /tasks/{id}` - Get specific task
- `POST /tasks` - Create new task
- `PUT /tasks/{id}` - Update task
- `DELETE /tasks/{id}` - Delete task

### Comments & History
- `POST /tasks/{id}/comments` - Add comment to task
- `GET /tasks/{id}/comments` - Get task comments
- `GET /tasks/{id}/history` - Get task history

### Users
- `GET /users` - Get users (Super User/Manager only)

## Default User Accounts

| Username | Password | Role | Description |
|----------|----------|------|-------------|
| admin | admin123 | Super User | Full access to all features |
| manager1 | manager123 | Manager | Can manage own and employee tasks |
| employee1 | emp123 | Employee | Can only view/edit own tasks |
| employee2 | emp123 | Employee | Can only view/edit own tasks |

## Testing the Application

### 1. Start the Server
```bash
cd build
.\Release\TaskManager.exe
```

### 2. Test with the Test Client
```bash
.\Release\TestClient.exe
```

### 3. Test with Postman/curl

#### Login
```bash
curl -X POST http://localhost:8080/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

#### Get Tasks
```bash
curl -X GET http://localhost:8080/tasks \
  -H "Authorization: Bearer <token>"
```

## Troubleshooting

### Common Build Issues

1. **CMake not found**:
   - Add CMake to your system PATH
   - Or use Visual Studio's built-in CMake

2. **vcpkg packages not found**:
   - Ensure vcpkg is properly installed
   - Check the toolchain file path in CMake command

3. **Visual Studio version issues**:
   - Use Visual Studio 2019 or 2022
   - Ensure C++ development tools are installed

### Runtime Issues

1. **Server won't start**:
   - Check if port 8080 is available
   - Run as Administrator if needed
   - Check firewall settings

2. **Database errors**:
   - Ensure SQLite3 is properly installed
   - Check file permissions in the project directory

3. **UI not displaying**:
   - Ensure DirectX 11 is installed
   - Check graphics drivers

### Debug Mode

To build in debug mode:
```bash
cmake --build . --config Debug
```

## Development

### Adding New Features

1. **Backend Changes**:
   - Add new endpoints in `api_server.cpp`
   - Implement business logic in service classes
   - Update database schema if needed

2. **Frontend Changes**:
   - Modify UI components in `ui_manager.cpp`
   - Add new API client methods in `api_client.cpp`

3. **Database Changes**:
   - Update schema in `database.cpp`
   - Add migration scripts if needed

### Code Style

- Use C++17 features
- Follow RAII principles
- Use smart pointers where appropriate
- Add comprehensive error handling
- Include logging for all operations

## Performance Considerations

- The application uses SQLite for data storage
- API calls are asynchronous for better performance
- UI uses immediate mode rendering (Dear ImGui)
- Consider connection pooling for high-load scenarios

## Security Notes

- Passwords are stored in plain text (for demo purposes)
- In production, use proper password hashing (bcrypt)
- Implement proper JWT token validation
- Add input validation and sanitization
- Use HTTPS in production

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License.

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review the code comments
3. Check the logs for error messages
4. Create an issue in the repository

## Next Steps

After successful setup:
1. Explore the different user roles
2. Test task creation and management
3. Try the filtering and search features
4. Experiment with the API endpoints
5. Customize the UI to your needs
