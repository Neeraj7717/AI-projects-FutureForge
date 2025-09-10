#include "ui_manager.h"
#include <spdlog/spdlog.h>
#include <algorithm>
#include <sstream>

namespace TaskManager {

UIManager::UIManager() 
    : show_login_window_(true)
    , show_main_window_(false)
    , show_task_dialog_(false)
    , show_user_management_(false)
    , show_task_history_(false)
    , show_task_comments_(false)
    , selected_task_id_(-1)
    , api_client_(std::make_unique<ApiClient>("http://localhost:8080")) {
}

UIManager::~UIManager() {
    shutdown();
}

bool UIManager::initialize(HWND hwnd) {
    // Setup Dear ImGui context
    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
    ImGuiIO& io = ImGui::GetIO();
    io.ConfigFlags |= ImGuiConfigFlags_NavEnableKeyboard;
    io.ConfigFlags |= ImGuiConfigFlags_DockingEnable;
    io.ConfigFlags |= ImGuiConfigFlags_ViewportsEnable;
    
    // Setup Dear ImGui style
    ImGui::StyleColorsDark();
    
    // Setup Platform/Renderer backends
    if (!ImGui_ImplWin32_Init(hwnd)) {
        spdlog::error("Failed to initialize ImGui Win32");
        return false;
    }
    
    // Initialize D3D11 (simplified - in real implementation, you'd need proper D3D11 setup)
    // For now, we'll assume D3D11 is already initialized
    
    return true;
}

void UIManager::shutdown() {
    ImGui_ImplWin32_Shutdown();
    ImGui::DestroyContext();
}

void UIManager::render() {
    // Start the Dear ImGui frame
    ImGui_ImplWin32_NewFrame();
    ImGui::NewFrame();
    
    if (show_login_window_) {
        renderLoginWindow();
    }
    
    if (show_main_window_) {
        renderMainWindow();
    }
    
    if (show_task_dialog_) {
        renderTaskDialog();
    }
    
    if (show_user_management_) {
        renderUserManagement();
    }
    
    if (show_task_history_) {
        renderTaskHistory();
    }
    
    if (show_task_comments_) {
        renderTaskComments();
    }
    
    // Rendering
    ImGui::Render();
    // In a real implementation, you would call your D3D11 render function here
}

void UIManager::handleMessage(UINT msg, WPARAM wParam, LPARAM lParam) {
    ImGui_ImplWin32_WndProcHandler(nullptr, msg, wParam, lParam);
}

void UIManager::showLoginWindow() {
    show_login_window_ = true;
    show_main_window_ = false;
}

void UIManager::showMainWindow() {
    show_login_window_ = false;
    show_main_window_ = true;
    refreshTasks();
}

void UIManager::showTaskDialog(const Task& task) {
    editing_task_ = task;
    show_task_dialog_ = true;
}

void UIManager::showUserManagement() {
    show_user_management_ = true;
    refreshUsers();
}

void UIManager::showTaskHistory(int task_id) {
    selected_task_id_ = task_id;
    show_task_history_ = true;
}

void UIManager::showTaskComments(int task_id) {
    selected_task_id_ = task_id;
    show_task_comments_ = true;
}

void UIManager::onLogin(const std::string& username, const std::string& password) {
    auto response = api_client_->login(username, password);
    
    if (response.success) {
        showSuccess("Login successful!");
        showMainWindow();
        error_message_.clear();
    } else {
        showError(response.message);
    }
}

void UIManager::onLogout() {
    api_client_->logout();
    showLoginWindow();
    tasks_.clear();
    users_.clear();
}

void UIManager::onTaskSelected(int task_id) {
    selected_task_id_ = task_id;
    auto task = api_client_->getTaskById(task_id);
    if (task.has_value()) {
        selected_task_ = task.value();
    }
}

void UIManager::onTaskCreated(const Task& task) {
    refreshTasks();
    showSuccess("Task created successfully!");
}

void UIManager::onTaskUpdated(const Task& task) {
    refreshTasks();
    showSuccess("Task updated successfully!");
}

void UIManager::onTaskDeleted(int task_id) {
    refreshTasks();
    showSuccess("Task deleted successfully!");
}

void UIManager::renderLoginWindow() {
    // Full screen login window
    ImGui::SetNextWindowPos(ImVec2(0, 0));
    ImGui::SetNextWindowSize(ImGui::GetIO().DisplaySize);
    
    ImGui::Begin("Login", nullptr, 
        ImGuiWindowFlags_NoTitleBar | 
        ImGuiWindowFlags_NoResize | 
        ImGuiWindowFlags_NoMove |
        ImGuiWindowFlags_NoCollapse |
        ImGuiWindowFlags_NoBackground);
    
    // Center the login form
    ImVec2 center = ImGui::GetMainViewport()->GetCenter();
    ImGui::SetNextWindowPos(center, ImGuiCond_Always, ImVec2(0.5f, 0.5f));
    
    ImGui::BeginChild("LoginForm", ImVec2(400, 300), true, ImGuiWindowFlags_NoScrollbar);
    
    // Title
    ImGui::PushFont(nullptr);
    ImGui::SetCursorPosX((ImGui::GetWindowSize().x - ImGui::CalcTextSize("Task Manager").x) * 0.5f);
    ImGui::Text("Task Manager");
    ImGui::PopFont();
    
    ImGui::Separator();
    ImGui::Spacing();
    
    // Login form
    ImGui::Text("Username:");
    ImGui::InputText("##username", &username_input_);
    
    ImGui::Spacing();
    ImGui::Text("Password:");
    ImGui::InputText("##password", &password_input_, ImGuiInputTextFlags_Password);
    
    ImGui::Spacing();
    ImGui::Spacing();
    
    // Login button
    ImGui::SetCursorPosX((ImGui::GetWindowSize().x - 100) * 0.5f);
    if (ImGui::Button("Login", ImVec2(100, 30))) {
        if (!username_input_.empty() && !password_input_.empty()) {
            onLogin(username_input_, password_input_);
        } else {
            showError("Please enter both username and password");
        }
    }
    
    ImGui::Spacing();
    
    // Messages
    if (!error_message_.empty()) {
        ImGui::TextColored(ImVec4(1.0f, 0.3f, 0.3f, 1.0f), "%s", error_message_.c_str());
    }
    
    if (!success_message_.empty()) {
        ImGui::TextColored(ImVec4(0.3f, 1.0f, 0.3f, 1.0f), "%s", success_message_.c_str());
    }
    
    // Demo credentials
    ImGui::Spacing();
    ImGui::Separator();
    ImGui::Text("Demo Credentials:");
    ImGui::Text("Super User: admin / admin123");
    ImGui::Text("Manager: manager1 / manager123");
    ImGui::Text("Employee: employee1 / emp123");
    
    ImGui::EndChild();
    ImGui::End();
}

void UIManager::renderMainWindow() {
    // Main window
    ImGui::SetNextWindowPos(ImVec2(0, 0));
    ImGui::SetNextWindowSize(ImGui::GetIO().DisplaySize);
    
    ImGui::Begin("Task Manager", nullptr, 
        ImGuiWindowFlags_NoTitleBar | 
        ImGuiWindowFlags_NoResize | 
        ImGuiWindowFlags_NoMove |
        ImGuiWindowFlags_NoCollapse |
        ImGuiWindowFlags_NoScrollbar);
    
    // Menu bar
    if (ImGui::BeginMenuBar()) {
        if (ImGui::BeginMenu("File")) {
            if (ImGui::MenuItem("New Task")) {
                showTaskDialog();
            }
            if (ImGui::MenuItem("Refresh")) {
                refreshTasks();
            }
            ImGui::Separator();
            if (ImGui::MenuItem("Logout")) {
                onLogout();
            }
            ImGui::EndMenu();
        }
        
        if (ImGui::BeginMenu("View")) {
            if (ImGui::MenuItem("User Management")) {
                showUserManagement();
            }
            ImGui::EndMenu();
        }
        
        if (ImGui::BeginMenu("Help")) {
            if (ImGui::MenuItem("About")) {
                // Show about dialog
            }
            ImGui::EndMenu();
        }
        
        // User info on the right
        ImGui::SameLine(ImGui::GetWindowWidth() - 300);
        ImGui::Text("Logged in as: %s (%s)", 
            api_client_->getCurrentUser().username.c_str(),
            roleToString(api_client_->getCurrentUser().role).c_str());
        
        ImGui::EndMenuBar();
    }
    
    // Main content area with docking
    ImGuiID dockspace_id = ImGui::GetID("MainDockSpace");
    ImGui::DockSpace(dockspace_id, ImVec2(0.0f, 0.0f), ImGuiDockNodeFlags_None);
    
    // Task list window
    ImGui::SetNextWindowDockID(dockspace_id, ImGuiCond_FirstUseEver);
    ImGui::Begin("Tasks", nullptr, ImGuiWindowFlags_None);
    renderTaskList();
    ImGui::End();
    
    // Status bar
    ImGui::SetNextWindowPos(ImVec2(0, ImGui::GetIO().DisplaySize.y - 30));
    ImGui::SetNextWindowSize(ImVec2(ImGui::GetIO().DisplaySize.x, 30));
    ImGui::Begin("StatusBar", nullptr, 
        ImGuiWindowFlags_NoTitleBar | 
        ImGuiWindowFlags_NoResize | 
        ImGuiWindowFlags_NoMove |
        ImGuiWindowFlags_NoScrollbar);
    
    ImGui::Text("Tasks: %zu | User: %s | Role: %s", 
        tasks_.size(), 
        api_client_->getCurrentUser().username.c_str(),
        roleToString(api_client_->getCurrentUser().role).c_str());
    
    ImGui::End();
    
    ImGui::End();
}

void UIManager::renderMenuBar() {
    if (ImGui::BeginMenuBar()) {
        if (ImGui::BeginMenu("File")) {
            if (ImGui::MenuItem("New Task")) {
                showTaskDialog();
            }
            if (ImGui::MenuItem("Refresh")) {
                refreshTasks();
            }
            ImGui::Separator();
            if (ImGui::MenuItem("Logout")) {
                onLogout();
            }
            ImGui::EndMenu();
        }
        
        if (ImGui::BeginMenu("View")) {
            if (ImGui::MenuItem("User Management")) {
                showUserManagement();
            }
            ImGui::EndMenu();
        }
        
        if (ImGui::BeginMenu("Help")) {
            if (ImGui::MenuItem("About")) {
                // Show about dialog
            }
            ImGui::EndMenu();
        }
        
        // User info on the right
        ImGui::SameLine(ImGui::GetWindowWidth() - 200);
        ImGui::Text("Logged in as: %s (%s)", 
            api_client_->getCurrentUser().username.c_str(),
            roleToString(api_client_->getCurrentUser().role).c_str());
        
        ImGui::EndMenuBar();
    }
}

void UIManager::renderTaskList() {
    // Header with filters and new task button
    ImGui::Text("Task Management");
    ImGui::SameLine(ImGui::GetWindowWidth() - 120);
    if (ImGui::Button("New Task", ImVec2(100, 25))) {
        showTaskDialog();
    }
    
    ImGui::Separator();
    
    // Filters row
    ImGui::Text("Filters:");
    ImGui::SameLine();
    
    const char* priorities[] = {"All", "Low", "Medium", "High", "Urgent"};
    static int priority_selected = 0;
    if (ImGui::Combo("Priority", &priority_selected, priorities, 5)) {
        filter_priority_ = (priority_selected == 0) ? "" : priorities[priority_selected];
        applyFilters();
    }
    
    ImGui::SameLine();
    
    const char* statuses[] = {"All", "Pending", "In Progress", "Completed", "Cancelled"};
    static int status_selected = 0;
    if (ImGui::Combo("Status", &status_selected, statuses, 5)) {
        filter_status_ = (status_selected == 0) ? "" : statuses[status_selected];
        applyFilters();
    }
    
    ImGui::SameLine();
    ImGui::InputText("Search", &search_text_);
    
    ImGui::SameLine();
    if (ImGui::Button("Refresh")) {
        refreshTasks();
    }
    
    ImGui::Separator();
    
    // Task table with better styling
    ImGuiStyle& style = ImGui::GetStyle();
    ImGui::PushStyleVar(ImGuiStyleVar_CellPadding, ImVec2(8, 4));
    
    if (ImGui::BeginTable("Tasks", 7, ImGuiTableFlags_Borders | ImGuiTableFlags_RowBg | ImGuiTableFlags_Resizable)) {
        ImGui::TableSetupColumn("ID", ImGuiTableColumnFlags_WidthFixed, 50);
        ImGui::TableSetupColumn("Title", ImGuiTableColumnFlags_WidthStretch);
        ImGui::TableSetupColumn("Priority", ImGuiTableColumnFlags_WidthFixed, 80);
        ImGui::TableSetupColumn("Status", ImGuiTableColumnFlags_WidthFixed, 100);
        ImGui::TableSetupColumn("Due Date", ImGuiTableColumnFlags_WidthFixed, 100);
        ImGui::TableSetupColumn("Assigned To", ImGuiTableColumnFlags_WidthFixed, 100);
        ImGui::TableSetupColumn("Actions", ImGuiTableColumnFlags_WidthFixed, 200);
        ImGui::TableHeadersRow();
        
        for (const auto& task : tasks_) {
            ImGui::TableNextRow();
            
            // ID
            ImGui::TableNextColumn();
            ImGui::Text("%d", task.id);
            
            // Title
            ImGui::TableNextColumn();
            ImGui::Text("%s", task.title.c_str());
            if (ImGui::IsItemHovered() && !task.description.empty()) {
                ImGui::SetTooltip("%s", task.description.c_str());
            }
            
            // Priority
            ImGui::TableNextColumn();
            ImVec4 priority_color = getPriorityColor(task.priority);
            ImGui::TextColored(priority_color, "%s", priorityToString(task.priority).c_str());
            
            // Status
            ImGui::TableNextColumn();
            ImVec4 status_color = getStatusColor(task.status);
            ImGui::TextColored(status_color, "%s", statusToString(task.status).c_str());
            
            // Due Date
            ImGui::TableNextColumn();
            ImGui::Text("%s", task.due_date.c_str());
            
            // Assigned To
            ImGui::TableNextColumn();
            ImGui::Text("User %d", task.assigned_user_id);
            
            // Actions
            ImGui::TableNextColumn();
            if (ImGui::Button(("Edit##" + std::to_string(task.id)).c_str(), ImVec2(50, 20))) {
                showTaskDialog(task);
            }
            ImGui::SameLine();
            if (ImGui::Button(("Delete##" + std::to_string(task.id)).c_str(), ImVec2(60, 20))) {
                if (api_client_->deleteTask(task.id)) {
                    onTaskDeleted(task.id);
                } else {
                    showError("Failed to delete task");
                }
            }
            ImGui::SameLine();
            if (ImGui::Button(("History##" + std::to_string(task.id)).c_str(), ImVec2(70, 20))) {
                showTaskHistory(task.id);
            }
        }
        
        ImGui::EndTable();
    }
    
    ImGui::PopStyleVar();
}

void UIManager::renderTaskDialog() {
    ImGui::SetNextWindowSize(ImVec2(600, 500), ImGuiCond_FirstUseEver);
    ImGui::SetNextWindowPos(ImGui::GetMainViewport()->GetCenter(), ImGuiCond_FirstUseEver, ImVec2(0.5f, 0.5f));
    
    std::string title = (editing_task_.id == 0) ? "Create New Task" : "Edit Task";
    ImGui::Begin(title.c_str(), &show_task_dialog_);
    
    // Title
    ImGui::Text("Title:");
    ImGui::InputText("##title", &editing_task_.title);
    
    ImGui::Spacing();
    
    // Description
    ImGui::Text("Description:");
    ImGui::InputTextMultiline("##description", &editing_task_.description, ImVec2(0, 100));
    
    ImGui::Spacing();
    
    // Priority and Status in same row
    ImGui::Columns(2, "PriorityStatus", false);
    
    // Priority selection
    ImGui::Text("Priority:");
    const char* priorities[] = {"Low", "Medium", "High", "Urgent"};
    int priority_index = static_cast<int>(editing_task_.priority);
    if (ImGui::Combo("##priority", &priority_index, priorities, 4)) {
        editing_task_.priority = static_cast<TaskPriority>(priority_index);
    }
    
    ImGui::NextColumn();
    
    // Status selection
    ImGui::Text("Status:");
    const char* statuses[] = {"Pending", "In Progress", "Completed", "Cancelled"};
    int status_index = static_cast<int>(editing_task_.status);
    if (ImGui::Combo("##status", &status_index, statuses, 4)) {
        editing_task_.status = static_cast<TaskStatus>(status_index);
    }
    
    ImGui::Columns(1);
    ImGui::Spacing();
    
    // Assigned user selection
    if (api_client_->getCurrentUser().role == UserRole::SUPER_USER || 
        api_client_->getCurrentUser().role == UserRole::MANAGER) {
        
        refreshUsers();
        ImGui::Text("Assigned User:");
        
        const char* user_items[users_.size()];
        int user_selected = 0;
        
        for (size_t i = 0; i < users_.size(); ++i) {
            user_items[i] = users_[i].username.c_str();
            if (users_[i].id == editing_task_.assigned_user_id) {
                user_selected = i;
            }
        }
        
        if (ImGui::Combo("##assigned_user", &user_selected, user_items, users_.size())) {
            editing_task_.assigned_user_id = users_[user_selected].id;
        }
    } else {
        // Employee can only see their own tasks
        editing_task_.assigned_user_id = api_client_->getCurrentUser().id;
        ImGui::Text("Assigned to: %s", api_client_->getCurrentUser().username.c_str());
    }
    
    ImGui::Spacing();
    
    // Due Date
    ImGui::Text("Due Date (YYYY-MM-DD):");
    ImGui::InputText("##due_date", &editing_task_.due_date);
    
    ImGui::Spacing();
    ImGui::Separator();
    ImGui::Spacing();
    
    // Buttons
    ImGui::SetCursorPosX(ImGui::GetWindowSize().x - 200);
    
    if (ImGui::Button("Cancel", ImVec2(80, 30))) {
        show_task_dialog_ = false;
    }
    
    ImGui::SameLine();
    
    std::string save_text = (editing_task_.id == 0) ? "Create" : "Save";
    if (ImGui::Button(save_text.c_str(), ImVec2(80, 30))) {
        bool success = false;
        if (editing_task_.id == 0) {
            // New task
            editing_task_.created_by = api_client_->getCurrentUser().id;
            success = api_client_->createTask(editing_task_);
            if (success) {
                onTaskCreated(editing_task_);
            }
        } else {
            // Update existing task
            success = api_client_->updateTask(editing_task_);
            if (success) {
                onTaskUpdated(editing_task_);
            }
        }
        
        if (success) {
            show_task_dialog_ = false;
        } else {
            showError("Failed to save task");
        }
    }
    
    ImGui::End();
}

void UIManager::renderUserManagement() {
    ImGui::SetNextWindowSize(ImVec2(600, 400), ImGuiCond_FirstUseEver);
    ImGui::SetNextWindowPos(ImGui::GetMainViewport()->GetCenter(), ImGuiCond_FirstUseEver, ImVec2(0.5f, 0.5f));
    
    ImGui::Begin("User Management", &show_user_management_);
    
    if (ImGui::BeginTable("Users", 4, ImGuiTableFlags_Borders | ImGuiTableFlags_RowBg)) {
        ImGui::TableSetupColumn("ID");
        ImGui::TableSetupColumn("Username");
        ImGui::TableSetupColumn("Role");
        ImGui::TableSetupColumn("Manager");
        ImGui::TableHeadersRow();
        
        for (const auto& user : users_) {
            ImGui::TableNextRow();
            
            ImGui::TableNextColumn();
            ImGui::Text("%d", user.id);
            
            ImGui::TableNextColumn();
            ImGui::Text("%s", user.username.c_str());
            
            ImGui::TableNextColumn();
            ImGui::Text("%s", roleToString(user.role).c_str());
            
            ImGui::TableNextColumn();
            if (user.manager_id.has_value()) {
                // Find manager name
                auto manager = std::find_if(users_.begin(), users_.end(),
                    [&user](const User& u) { return u.id == user.manager_id.value(); });
                if (manager != users_.end()) {
                    ImGui::Text("%s", manager->username.c_str());
                } else {
                    ImGui::Text("Unknown");
                }
            } else {
                ImGui::Text("None");
            }
        }
        
        ImGui::EndTable();
    }
    
    if (ImGui::Button("Close")) {
        show_user_management_ = false;
    }
    
    ImGui::End();
}

void UIManager::renderTaskHistory() {
    ImGui::SetNextWindowSize(ImVec2(600, 400), ImGuiCond_FirstUseEver);
    ImGui::SetNextWindowPos(ImGui::GetMainViewport()->GetCenter(), ImGuiCond_FirstUseEver, ImVec2(0.5f, 0.5f));
    
    ImGui::Begin("Task History", &show_task_history_);
    
    auto history = api_client_->getTaskHistory(selected_task_id_);
    
    if (ImGui::BeginTable("History", 4, ImGuiTableFlags_Borders | ImGuiTableFlags_RowBg)) {
        ImGui::TableSetupColumn("Action");
        ImGui::TableSetupColumn("User");
        ImGui::TableSetupColumn("Comment");
        ImGui::TableSetupColumn("Date");
        ImGui::TableHeadersRow();
        
        for (const auto& h : history) {
            ImGui::TableNextRow();
            
            ImGui::TableNextColumn();
            ImGui::Text("%s", h.action.c_str());
            
            ImGui::TableNextColumn();
            ImGui::Text("%d", h.user_id);
            
            ImGui::TableNextColumn();
            ImGui::Text("%s", h.comment.c_str());
            
            ImGui::TableNextColumn();
            ImGui::Text("%s", h.created_at.c_str());
        }
        
        ImGui::EndTable();
    }
    
    if (ImGui::Button("Close")) {
        show_task_history_ = false;
    }
    
    ImGui::End();
}

void UIManager::renderTaskComments() {
    ImGui::SetNextWindowSize(ImVec2(600, 400), ImGuiCond_FirstUseEver);
    ImGui::SetNextWindowPos(ImGui::GetMainViewport()->GetCenter(), ImGuiCond_FirstUseEver, ImVec2(0.5f, 0.5f));
    
    ImGui::Begin("Task Comments", &show_task_comments_);
    
    auto comments = api_client_->getTaskComments(selected_task_id_);
    
    for (const auto& comment : comments) {
        ImGui::Text("User %d: %s", comment.user_id, comment.comment.c_str());
        ImGui::Text("Posted: %s", comment.created_at.c_str());
        ImGui::Separator();
    }
    
    static std::string new_comment;
    ImGui::InputTextMultiline("New Comment", &new_comment, ImVec2(0, 100));
    
    if (ImGui::Button("Add Comment")) {
        if (!new_comment.empty()) {
            if (api_client_->addComment(selected_task_id_, new_comment)) {
                new_comment.clear();
                showSuccess("Comment added successfully!");
            } else {
                showError("Failed to add comment");
            }
        }
    }
    
    ImGui::SameLine();
    if (ImGui::Button("Close")) {
        show_task_comments_ = false;
    }
    
    ImGui::End();
}

void UIManager::renderStatusBar() {
    ImGui::BeginChild("StatusBar", ImVec2(0, 30), true);
    ImGui::Text("Tasks: %zu | User: %s", tasks_.size(), api_client_->getCurrentUser().username.c_str());
    ImGui::EndChild();
}

void UIManager::refreshTasks() {
    tasks_ = api_client_->getTasks();
}

void UIManager::refreshUsers() {
    users_ = api_client_->getUsers();
}

void UIManager::applyFilters() {
    // This would filter the tasks_ vector based on current filters
    // For now, we'll just refresh from the server
    refreshTasks();
}

ImVec4 UIManager::getPriorityColor(TaskPriority priority) {
    switch (priority) {
        case TaskPriority::LOW: return ImVec4(0.0f, 1.0f, 0.0f, 1.0f); // Green
        case TaskPriority::MEDIUM: return ImVec4(1.0f, 1.0f, 0.0f, 1.0f); // Yellow
        case TaskPriority::HIGH: return ImVec4(1.0f, 0.5f, 0.0f, 1.0f); // Orange
        case TaskPriority::URGENT: return ImVec4(1.0f, 0.0f, 0.0f, 1.0f); // Red
        default: return ImVec4(1.0f, 1.0f, 1.0f, 1.0f); // White
    }
}

ImVec4 UIManager::getStatusColor(TaskStatus status) {
    switch (status) {
        case TaskStatus::PENDING: return ImVec4(1.0f, 1.0f, 0.0f, 1.0f); // Yellow
        case TaskStatus::IN_PROGRESS: return ImVec4(0.0f, 0.5f, 1.0f, 1.0f); // Blue
        case TaskStatus::COMPLETED: return ImVec4(0.0f, 1.0f, 0.0f, 1.0f); // Green
        case TaskStatus::CANCELLED: return ImVec4(1.0f, 0.0f, 0.0f, 1.0f); // Red
        default: return ImVec4(1.0f, 1.0f, 1.0f, 1.0f); // White
    }
}

void UIManager::showError(const std::string& message) {
    error_message_ = message;
    success_message_.clear();
}

void UIManager::showSuccess(const std::string& message) {
    success_message_ = message;
    error_message_.clear();
}

} // namespace TaskManager
