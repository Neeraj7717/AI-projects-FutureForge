#pragma once

#include "common.h"
#include "api_client.h"
#include <imgui.h>
#include <imgui_impl_win32.h>
#include <imgui_impl_dx11.h>
#include <d3d11.h>
#include <tchar.h>
#include <memory>
#include <vector>
#include <string>

namespace TaskManager {

class UIManager {
public:
    UIManager();
    ~UIManager();
    
    bool initialize(HWND hwnd);
    void shutdown();
    void render();
    void handleMessage(UINT msg, WPARAM wParam, LPARAM lParam);
    
    // UI State
    void showLoginWindow();
    void showMainWindow();
    void showTaskDialog(const Task& task = Task{});
    void showUserManagement();
    void showTaskHistory(int task_id);
    void showTaskComments(int task_id);
    
    // Event handlers
    void onLogin(const std::string& username, const std::string& password);
    void onLogout();
    void onTaskSelected(int task_id);
    void onTaskCreated(const Task& task);
    void onTaskUpdated(const Task& task);
    void onTaskDeleted(int task_id);
    
private:
    // ImGui state
    bool show_login_window_;
    bool show_main_window_;
    bool show_task_dialog_;
    bool show_user_management_;
    bool show_task_history_;
    bool show_task_comments_;
    
    // UI data
    std::string username_input_;
    std::string password_input_;
    std::string error_message_;
    std::string success_message_;
    
    // Task management
    std::vector<Task> tasks_;
    std::vector<User> users_;
    Task selected_task_;
    Task editing_task_;
    int selected_task_id_;
    
    // Filtering and sorting
    std::string filter_priority_;
    std::string filter_status_;
    std::string filter_user_;
    std::string search_text_;
    
    // API client
    std::unique_ptr<ApiClient> api_client_;
    
    // UI rendering methods
    void renderLoginWindow();
    void renderMainWindow();
    void renderTaskList();
    void renderTaskDialog();
    void renderUserManagement();
    void renderTaskHistory();
    void renderTaskComments();
    void renderMenuBar();
    void renderStatusBar();
    
    // Helper methods
    void refreshTasks();
    void refreshUsers();
    void applyFilters();
    std::string getPriorityColor(TaskPriority priority);
    std::string getStatusColor(TaskStatus status);
    void showError(const std::string& message);
    void showSuccess(const std::string& message);
};

} // namespace TaskManager
