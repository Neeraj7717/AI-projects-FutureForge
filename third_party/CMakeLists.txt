# Dear ImGui
set(IMGUI_DIR ${CMAKE_CURRENT_SOURCE_DIR}/imgui)
add_subdirectory(${IMGUI_DIR})

# cpprestsdk for HTTP client/server
find_package(cpprestsdk REQUIRED)

# SQLite3
find_package(SQLite3 REQUIRED)

# spdlog for logging
find_package(spdlog REQUIRED)

# nlohmann json
find_package(nlohmann_json REQUIRED)
