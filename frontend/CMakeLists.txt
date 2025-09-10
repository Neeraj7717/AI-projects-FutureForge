add_library(frontend_lib
    src/main.cpp
    src/ui_manager.cpp
    src/api_client.cpp
    src/task_manager_ui.cpp
)

target_include_directories(frontend_lib PUBLIC
    ${CMAKE_SOURCE_DIR}/include
    ${CMAKE_SOURCE_DIR}/frontend/include
)

target_link_libraries(frontend_lib
    imgui
    cpprestsdk::cpprest
    nlohmann_json::nlohmann_json
    spdlog::spdlog
)

# Platform specific libraries
if(WIN32)
    target_link_libraries(frontend_lib
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
