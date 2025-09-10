cmake_minimum_required(VERSION 3.16)
project(TaskManager)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find packages
find_package(OpenSSL REQUIRED)
find_package(Threads REQUIRED)
find_package(SQLite3 REQUIRED)
find_package(spdlog REQUIRED)
find_package(nlohmann_json REQUIRED)

# Find cpprestsdk
find_package(cpprestsdk REQUIRED)

# Include directories
include_directories(include)
include_directories(third_party)

# Add subdirectories
add_subdirectory(third_party)
add_subdirectory(backend)

# Main executable (Console version)
add_executable(TaskManager
    src/main_console.cpp
    src/common.cpp
    backend/src/database.cpp
    backend/src/auth_service.cpp
    backend/src/task_service.cpp
    backend/src/api_server.cpp
    backend/src/utils.cpp
    frontend/src/api_client.cpp
    frontend/src/ui_manager.cpp
)

# GUI executable (if ImGui is available)
add_executable(TaskManagerGUI
    src/main.cpp
    src/common.cpp
    backend/src/database.cpp
    backend/src/auth_service.cpp
    backend/src/task_service.cpp
    backend/src/api_server.cpp
    backend/src/utils.cpp
    frontend/src/api_client.cpp
    frontend/src/ui_manager.cpp
)

# Test client executable
add_executable(TestClient
    test_client.cpp
)

target_include_directories(TestClient PRIVATE
    ${CMAKE_SOURCE_DIR}/include
)

target_link_libraries(TestClient
    cpprestsdk::cpprest
    spdlog::spdlog
    nlohmann_json::nlohmann_json
)

target_include_directories(TaskManager PRIVATE
    ${CMAKE_SOURCE_DIR}/include
    ${CMAKE_SOURCE_DIR}/backend/include
    ${CMAKE_SOURCE_DIR}/frontend/include
    ${CMAKE_SOURCE_DIR}/third_party/imgui
    ${CMAKE_SOURCE_DIR}/third_party/imgui/backends
)

target_link_libraries(TaskManager
    cpprestsdk::cpprest
    SQLite::SQLite3
    spdlog::spdlog
    nlohmann_json::nlohmann_json
    OpenSSL::SSL
    OpenSSL::Crypto
    Threads::Threads
)

# Platform specific libraries
if(WIN32)
    target_link_libraries(TaskManager
        d3d11
        dxgi
        d3dcompiler
        opengl32
        gdi32
        user32
        kernel32
        shell32
        ole32
        oleaut32
        uuid
        comdlg32
        advapi32
        ws2_32
        winmm
        imm32
    )
endif()
