# Task Manager - C++ Desktop Application

A comprehensive Windows desktop task management application built with C++ featuring role-based access control, REST API backend, and both console and GUI interfaces.

## Features

### Core Features
- **Multi-User Login System**: Secure authentication with username/password
- **Role-Based Access Control**: 
  - Super User: Can view and manage all tasks for all users
  - Manager: Can view and manage tasks for themselves and their assigned employees
  - Employee: Can view and update only their own tasks
- **Task CRUD Operations**: Create, read, update, delete tasks with permission validation
- **Task Filtering & Sorting**: Filter by priority, status, assigned user, or due date using LINQ
- **Async Operations**: Non-blocking API calls for better performance
- **Event Handling**: Task notifications and status updates
- **Exception Handling**: Comprehensive error handling throughout the application
- **Logging**: Structured logging using spdlog for all operations
- **Clean Architecture**: MVVM pattern with separation of concerns

### Advanced Features
- **Task History & Comments**: Full audit trail and collaboration features
- **Permission Checks**: Granular permission validation for all operations
- **Dashboard Statistics**: Task completion rates and overdue task tracking
- **Search & Filter**: Advanced filtering capabilities
- **Role-Based UI**: Dynamic interface based on user permissions

## Architecture

### Backend (C++ REST API Server)
- **Database Layer**: SQLite with custom ORM-like wrapper
- **Authentication Service**: JWT-based authentication with role management
- **Task Service**: Business logic for task operations with permission checks
- **API Server**: RESTful API using cpprestsdk
- **Logging**: Structured logging with spdlog

### Frontend (Windows Desktop UI)
- **Console Interface**: Interactive console-based UI for easy navigation
- **GUI Interface**: Dear ImGui for modern, immediate-mode GUI (optional)
- **API Client**: HTTP client for backend communication
- **UI Manager**: Centralized UI state and rendering management
- **Role-Based UI**: Dynamic interface based on user permissions

## Project Structure

```
TaskManager/
├── backend/
│   ├── include/
│   │   ├── api_server.h
│   │   ├── auth_service.h
│   │   ├── database.h
│   │   ├── task_service.h
│   │   └── utils.h
│   └── src/
│       ├── api_server.cpp
│       ├── auth_service.cpp
│       ├── database.cpp
│       ├── task_service.cpp
│       └── utils.cpp
├── frontend/
│   ├── include/
│   │   ├── api_client.h
│   │   └── ui_manager.h
│   └── src/
│       ├── api_client.cpp
│       └── ui_manager.cpp
├── include/
│   └── common.h
├── src/
│   ├── common.cpp
│   └── main.cpp
├── third_party/
│   └── imgui/
├── CMakeLists.txt
└── README.md
```

## Prerequisites

### Required Software
- **Visual Studio 2019/2022** or **MinGW-w64**
- **CMake 3.16+**
- **Git**

### Required Libraries
- **cpprestsdk** (Microsoft C++ REST SDK)
- **SQLite3**
- **spdlog** (Logging library)
- **nlohmann/json** (JSON library)
- **OpenSSL** (For secure communications)
- **Dear ImGui** (UI framework)

## Installation & Setup

### Quick Start (One-Click Setup)
For the fastest setup, simply run:
```bash
startapp.bat
```
This will automatically:
- Install vcpkg package manager
- Install all C++ dependencies (cpprestsdk, SQLite3, spdlog, nlohmann-json)
- Build the project (both console and GUI versions)
- Start the Task Manager console application

### Alternative: Quick Launch (If Already Built)
If you've already run the full setup once:
```bash
startapp_quick.bat
```

### Available Scripts
- `startapp.bat` - Full setup and start (first time)
- `startapp_quick.bat` - Quick start (if already built)
- `clean_and_rebuild.bat` - Clean everything and rebuild
- `help.bat` - Show all available scripts and features

### Manual Setup

### 1. Clone the Repository
```bash
git clone <repository-url>
cd TaskManager
```

### 2. Install Dependencies

#### Using vcpkg (Recommended)
```bash
# Install vcpkg if not already installed
git clone https://github.com/Microsoft/vcpkg.git
cd vcpkg
./bootstrap-vcpkg.bat  # On Windows
# or
./bootstrap-vcpkg.sh   # On Linux/Mac

# Install required packages
./vcpkg install cpprestsdk sqlite3 spdlog nlohmann-json openssl
```

#### Manual Installation
1. Download and install cpprestsdk
2. Download and install SQLite3
3. Download and install spdlog
4. Download and install nlohmann/json
5. Download and install OpenSSL
6. Download Dear ImGui from https://github.com/ocornut/imgui

### 3. Configure CMake
```bash
mkdir build
cd build
cmake .. -DCMAKE_TOOLCHAIN_FILE=[path-to-vcpkg]/scripts/buildsystems/vcpkg.cmake
```

### 4. Build the Project
```bash
cmake --build . --config Release
```

## Usage

### Starting the Application

#### Option 1: One-Click Start (Recommended)
```bash
startapp.bat
```
This will install dependencies, build, and start the console application.

#### Option 2: Quick Launch (If Already Built)
```bash
startapp_quick.bat
```

#### Option 3: Manual Start

1. **Build the project**:
   ```bash
   build.bat
   ```

2. **Start the application**:
   ```bash
   cd build
   .\Release\TaskManager.exe
   ```

## Application Interface

### Console Application
The main application provides an interactive console interface with:

- **Login Screen**: Enter username and password
- **Main Menu**: Navigate through options with numbered choices
- **Task Management**: View, create, edit, delete tasks
- **User Management**: Manage users (Super User/Manager only)
- **Role-Based Access**: Different features based on user role

### Default Login Credentials
- **Super User**: `admin` / `admin123`
- **Manager**: `manager1` / `manager123`
- **Employee**: `employee1` / `emp123`
- **Employee**: `employee2` / `emp123`

### API Endpoints

#### Authentication
- `POST /auth/login` - User login
- `POST /auth/logout` - User logout

#### Tasks
- `GET /tasks` - Get all tasks (role-based filtering)
- `GET /tasks/{id}` - Get specific task
- `POST /tasks` - Create new task
- `PUT /tasks/{id}` - Update task
- `DELETE /tasks/{id}` - Delete task

#### Comments & History
- `POST /tasks/{id}/comments` - Add comment to task
- `GET /tasks/{id}/comments` - Get task comments
- `GET /tasks/{id}/history` - Get task history

#### Users
- `GET /users` - Get users (Super User/Manager only)

## Role-Based Permissions

### Super User
- View and manage all tasks
- Create, edit, delete any task
- Manage all users
- Access to all features

### Manager
- View and manage own tasks
- View and manage tasks assigned to their employees
- Create tasks for themselves and their employees
- View user management (assigned employees only)

### Employee
- View only their own tasks
- Edit only their own tasks
- Add comments to their tasks
- Cannot create or delete tasks

## Development

### Adding New Features
1. Add new endpoints to `api_server.h/cpp`
2. Implement business logic in appropriate service
3. Update UI components in `ui_manager.h/cpp`
4. Add API client methods in `api_client.h/cpp`

### Database Schema
The application uses SQLite with the following tables:
- `users` - User accounts and roles
- `tasks` - Task information
- `task_history` - Task change history
- `task_comments` - Task comments

### Logging
All operations are logged using spdlog. Logs include:
- User authentication events
- Task CRUD operations
- API requests and responses
- Error conditions

## Testing

### Manual Testing
1. Test login with different user roles
2. Verify role-based task access
3. Test task creation, editing, and deletion
4. Verify permission restrictions
5. Test filtering and search functionality

### API Testing
Use tools like Postman or curl to test API endpoints:
```bash
# Login
curl -X POST http://localhost:8080/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# Get tasks
curl -X GET http://localhost:8080/tasks \
  -H "Authorization: Bearer <token>"
```

## Project Status

### ✅ Completed Features
- **Backend REST API server** with full CRUD operations
- **SQLite database integration** with custom ORM-like wrapper
- **User authentication and role management** with JWT tokens
- **Task CRUD operations** with permission validation
- **Permission-based access control** (Super User, Manager, Employee)
- **Structured logging system** using spdlog
- **API client** for frontend communication
- **Console-based UI** with full interactive functionality
- **One-click installation** scripts (startapp.bat)
- **Interactive task management** interface
- **Role-based UI** with different features per user type
- **Real-time backend integration** via REST API

### ⚠️ Current Limitations
- OpenSSL disabled (no HTTPS encryption)
- Dear ImGui GUI not fully implemented (console UI works perfectly)
- No real-time notifications

### 🔄 Future Enhancements
- Complete Dear ImGui GUI implementation
- Enable HTTPS with OpenSSL
- Real-time notifications
- Task reminders and alerts
- Export functionality (PDF, Excel)
- Advanced reporting and analytics

## Troubleshooting

### Common Issues

1. **Build Errors**:
   - Ensure all dependencies are properly installed
   - Check CMake configuration
   - Verify compiler compatibility

2. **Runtime Errors**:
   - Check database file permissions
   - Verify port 8080 is available
   - Check firewall settings

3. **UI Issues**:
   - Ensure Dear ImGui is properly linked
   - Check DirectX 11 compatibility

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Future Enhancements

- [ ] Real-time notifications
- [ ] Task templates
- [ ] File attachments
- [ ] Advanced reporting
- [ ] Mobile app integration
- [ ] Multi-language support
- [ ] Dark/Light theme toggle
- [ ] Export to PDF/Excel
- [ ] Email notifications
- [ ] Calendar integration
