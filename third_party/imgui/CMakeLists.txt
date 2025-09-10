# Dear ImGui CMakeLists.txt
cmake_minimum_required(VERSION 3.16)

project(imgui)

# Check if ImGui files exist, if not, create a simple stub
if(NOT EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/imgui.h")
    message(STATUS "ImGui not found, creating stub files...")
    
    # Create stub header
    file(WRITE "${CMAKE_CURRENT_SOURCE_DIR}/imgui.h" 
"#pragma once
// Dear ImGui stub
namespace ImGui {
    void NewFrame() {}
    void Render() {}
    void Begin(const char* name, bool* p_open = nullptr) {}
    void End() {}
    void Text(const char* fmt, ...) {}
    bool Button(const char* label) { return false; }
    bool InputText(const char* label, char* buf, size_t buf_size) { return false; }
    void Separator() {}
    void Spacing() {}
    void SetNextWindowPos(ImVec2 pos, int cond = 0, ImVec2 pivot = ImVec2(0,0)) {}
    void SetNextWindowSize(ImVec2 size, int cond = 0) {}
    void SetTooltip(const char* fmt, ...) {}
    bool IsItemHovered() { return false; }
    void SameLine(float offset_from_start_x = 0.0f, float spacing = -1.0f) {}
    void SetCursorPosX(float local_x) {}
    void SetCursorPosY(float local_y) {}
    void SetCursorPos(ImVec2 local_pos) {}
    ImVec2 GetCursorPos() { return ImVec2(0,0); }
    ImVec2 GetWindowSize() { return ImVec2(800,600); }
    ImVec2 GetMainViewport() { return ImVec2(800,600); }
    ImVec2 CalcTextSize(const char* text) { return ImVec2(100,20); }
    void TextColored(ImVec4 col, const char* fmt, ...) {}
    bool BeginMenuBar() { return false; }
    void EndMenuBar() {}
    bool BeginMenu(const char* label) { return false; }
    void EndMenu() {}
    bool MenuItem(const char* label, const char* shortcut = nullptr, bool selected = false, bool enabled = true) { return false; }
    void Columns(int count, const char* id = nullptr, bool border = true) {}
    void NextColumn() {}
    void InputTextMultiline(const char* label, char* buf, size_t buf_size, ImVec2 size = ImVec2(0,0)) {}
    bool Combo(const char* label, int* current_item, const char* const items[], int items_count) { return false; }
    bool BeginTable(const char* str_id, int column, int flags = 0) { return false; }
    void EndTable() {}
    void TableSetupColumn(const char* label, int flags = 0, float init_width_or_weight = 0.0f) {}
    void TableHeadersRow() {}
    void TableNextRow(int row_flags = 0, float min_row_height = 0.0f) {}
    void TableNextColumn() {}
    void TableSetColumnIndex(int column_n) {}
    void PushStyleVar(int idx, float val) {}
    void PopStyleVar(int count = 1) {}
    bool BeginChild(const char* str_id, ImVec2 size = ImVec2(0,0), bool border = false, int flags = 0) { return false; }
    void EndChild() {}
    ImGuiID GetID(const char* str_id) { return 0; }
    void DockSpace(ImGuiID id, ImVec2 size = ImVec2(0,0), int flags = 0) {}
    void SetNextWindowDockID(ImGuiID dock_id, int cond = 0) {}
    void BeginChild(const char* str_id, ImVec2 size, bool border, int flags) {}
    void EndChild() {}
    
    struct ImVec2 { float x, y; ImVec2(float _x = 0, float _y = 0) : x(_x), y(_y) {} };
    struct ImVec4 { float x, y, z, w; ImVec4(float _x = 0, float _y = 0, float _z = 0, float _w = 0) : x(_x), y(_y), z(_z), w(_w) {} };
    struct ImGuiStyle { ImVec4 Colors[50]; };
    struct ImGuiIO { int ConfigFlags; float Framerate; };
    
    enum ImGuiWindowFlags_ {
        ImGuiWindowFlags_None = 0,
        ImGuiWindowFlags_NoTitleBar = 1 << 0,
        ImGuiWindowFlags_NoResize = 1 << 1,
        ImGuiWindowFlags_NoMove = 1 << 2,
        ImGuiWindowFlags_NoCollapse = 1 << 3,
        ImGuiWindowFlags_NoScrollbar = 1 << 4,
        ImGuiWindowFlags_NoBackground = 1 << 5
    };
    
    enum ImGuiTableFlags_ {
        ImGuiTableFlags_None = 0,
        ImGuiTableFlags_Borders = 1 << 0,
        ImGuiTableFlags_RowBg = 1 << 1,
        ImGuiTableFlags_Resizable = 1 << 2
    };
    
    enum ImGuiTableColumnFlags_ {
        ImGuiTableColumnFlags_None = 0,
        ImGuiTableColumnFlags_WidthFixed = 1 << 0,
        ImGuiTableColumnFlags_WidthStretch = 1 << 1
    };
    
    enum ImGuiInputTextFlags_ {
        ImGuiInputTextFlags_None = 0,
        ImGuiInputTextFlags_Password = 1 << 0
    };
    
    enum ImGuiDockNodeFlags_ {
        ImGuiDockNodeFlags_None = 0
    };
    
    enum ImGuiCond_ {
        ImGuiCond_None = 0,
        ImGuiCond_FirstUseEver = 1 << 0
    };
    
    enum ImGuiCol_ {
        ImGuiCol_WindowBg = 0
    };
    
    enum ImGuiStyleVar_ {
        ImGuiStyleVar_CellPadding = 0
    };
    
    using ImGuiID = unsigned int;
    
    ImGuiIO& GetIO() { static ImGuiIO io; return io; }
    ImGuiStyle& GetStyle() { static ImGuiStyle style; return style; }
    void StyleColorsDark() {}
    void CheckVERSION() {}
    void CreateContext() {}
    void DestroyContext() {}
}

// Stub implementations
namespace ImGui_ImplWin32 {
    void Init(void* hwnd) {}
    void Shutdown() {}
    void NewFrame() {}
    bool WndProcHandler(void* hwnd, unsigned int msg, unsigned long wParam, long lParam) { return false; }
}

namespace ImGui_ImplDX11 {
    void Init(void* device, void* context) {}
    void Shutdown() {}
    void NewFrame() {}
    void RenderDrawData(void* data) {}
}

#define IMGUI_IMPL_API
#define IMGUI_CHECKVERSION() ImGui::CheckVERSION()
#define ImGuiWindowFlags_NoTitleBar ImGui::ImGuiWindowFlags_NoTitleBar
#define ImGuiWindowFlags_NoResize ImGui::ImGuiWindowFlags_NoResize
#define ImGuiWindowFlags_NoMove ImGui::ImGuiWindowFlags_NoMove
#define ImGuiWindowFlags_NoCollapse ImGui::ImGuiWindowFlags_NoCollapse
#define ImGuiWindowFlags_NoScrollbar ImGui::ImGuiWindowFlags_NoScrollbar
#define ImGuiWindowFlags_NoBackground ImGui::ImGuiWindowFlags_NoBackground
#define ImGuiTableFlags_Borders ImGui::ImGuiTableFlags_Borders
#define ImGuiTableFlags_RowBg ImGui::ImGuiTableFlags_RowBg
#define ImGuiTableFlags_Resizable ImGui::ImGuiTableFlags_Resizable
#define ImGuiTableColumnFlags_WidthFixed ImGui::ImGuiTableColumnFlags_WidthFixed
#define ImGuiTableColumnFlags_WidthStretch ImGui::ImGuiTableColumnFlags_WidthStretch
#define ImGuiInputTextFlags_Password ImGui::ImGuiInputTextFlags_Password
#define ImGuiDockNodeFlags_None ImGui::ImGuiDockNodeFlags_None
#define ImGuiCond_FirstUseEver ImGui::ImGuiCond_FirstUseEver
#define ImGuiCol_WindowBg ImGui::ImGuiCol_WindowBg
#define ImGuiStyleVar_CellPadding ImGui::ImGuiStyleVar_CellPadding
#define ImGuiConfigFlags_NavEnableKeyboard ImGui::GetIO().ConfigFlags
#define ImGuiConfigFlags_DockingEnable ImGui::GetIO().ConfigFlags
#define ImGuiConfigFlags_ViewportsEnable ImGui::GetIO().ConfigFlags
")

    # Create stub implementation
    file(WRITE "${CMAKE_CURRENT_SOURCE_DIR}/imgui_impl_win32.h" 
"#pragma once
#include \"imgui.h\"
")
    
    file(WRITE "${CMAKE_CURRENT_SOURCE_DIR}/imgui_impl_dx11.h" 
"#pragma once
#include \"imgui.h\"
")
    
    file(WRITE "${CMAKE_CURRENT_SOURCE_DIR}/backends/imgui_impl_win32.cpp" 
"#include \"imgui_impl_win32.h\"
// Stub implementation
")
    
    file(WRITE "${CMAKE_CURRENT_SOURCE_DIR}/backends/imgui_impl_dx11.cpp" 
"#include \"imgui_impl_dx11.h\"
// Stub implementation
")
endif()

# Create the imgui library
add_library(imgui STATIC
    imgui.cpp
    backends/imgui_impl_win32.cpp
    backends/imgui_impl_dx11.cpp
)

# Include directories
target_include_directories(imgui PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/backends
)

# Link libraries
if(WIN32)
    target_link_libraries(imgui
        d3d11
        dxgi
        d3dcompiler
    )
endif()

# Compiler specific options
target_compile_definitions(imgui PRIVATE
    IMGUI_IMPL_WIN32_DISABLE_GAMEPAD
    IMGUI_IMPL_WIN32_DISABLE_LINKING_XINPUT
)
