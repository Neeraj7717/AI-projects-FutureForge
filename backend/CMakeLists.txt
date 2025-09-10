add_library(backend_lib
    src/database.cpp
    src/auth_service.cpp
    src/task_service.cpp
    src/api_server.cpp
    src/utils.cpp
)

target_include_directories(backend_lib PUBLIC
    ${CMAKE_SOURCE_DIR}/include
    ${CMAKE_SOURCE_DIR}/backend/include
)

target_link_libraries(backend_lib
    cpprestsdk::cpprest
    SQLite::SQLite3
    spdlog::spdlog
    nlohmann_json::nlohmann_json
    OpenSSL::SSL
    OpenSSL::Crypto
)
