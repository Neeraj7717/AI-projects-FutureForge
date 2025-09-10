#include <iostream>
#include <thread>
#include <chrono>
#include <spdlog/spdlog.h>
#include <string>
#include <vector>
#include <memory>

#include "frontend/include/api_client.h"
#include "backend/include/api_server.h"
#include "backend/include/database.h"
#include "backend/include/auth_service.h"
#include "backend/include/task_service.h"
#include "utils.h"

class ConsoleUI {
private:
    std::unique_ptr<TaskManager::ApiClient> api_client_;
    std::vector<TaskManager::Task> tasks_;
    TaskManager::User current_user_;
    bool authenticated_;

public:
    ConsoleUI() : api_client_(std::make_unique<TaskManager::ApiClient>("http://localhost:8080")), authenticated_(false) {}

    void run() {
        std::cout << "=== Task Manager Console Application ===" << std::endl;
        std::cout << "Starting backend server..." << std::endl;
        
        // Start backend in separate thread
        std::thread backend_thread([this]() {
            try {
                TaskManager::Database db("taskmanager.db");
                if (!db.initialize()) {
                    spdlog::error("Failed to initialize database");
                    return;
                }
                
                TaskManager::AuthService auth_service(db);
                TaskManager::TaskService task_service(db, auth_service);
                TaskManager::ApiServer server("localhost", 8080);
                
                if (!server.start()) {
                    spdlog::error("Failed to start API server");
                    return;
                }
                
                spdlog::info("Backend server started on http://localhost:8080");
                
                while (true) {
                    std::this_thread::sleep_for(std::chrono::seconds(1));
                }
            } catch (const std::exception& e) {
                spdlog::error("Backend error: {}", e.what());
            }
        });
        
        backend_thread.detach();
        
        // Wait for backend to start
        std::this_thread::sleep_for(std::chrono::seconds(2));
        
        // Main UI loop
        while (true) {
            if (!authenticated_) {
                showLoginMenu();
            } else {
                showMainMenu();
            }
        }
    }

private:
    void showLoginMenu() {
        std::cout << "\n=== Login ===" << std::endl;
        std::cout << "Default credentials:" << std::endl;
        std::cout << "  Super User: admin / admin123" << std::endl;
        std::cout << "  Manager: manager1 / manager123" << std::endl;
        std::cout << "  Employee: employee1 / emp123" << std::endl;
        
        std::string username, password;
        std::cout << "\nUsername: ";
        std::getline(std::cin, username);
        std::cout << "Password: ";
        std::getline(std::cin, password);
        
        auto response = api_client_->login(username, password);
        if (response.success) {
            current_user_ = response.user;
            authenticated_ = true;
            std::cout << "\nLogin successful! Welcome, " << current_user_.username << std::endl;
            refreshTasks();
        } else {
            std::cout << "\nLogin failed: " << response.message << std::endl;
        }
    }

    void showMainMenu() {
        std::cout << "\n=== Main Menu ===" << std::endl;
        std::cout << "Logged in as: " << current_user_.username 
                  << " (" << TaskManager::roleToString(current_user_.role) << ")" << std::endl;
        std::cout << "\n1. View Tasks" << std::endl;
        std::cout << "2. Create Task" << std::endl;
        std::cout << "3. Edit Task" << std::endl;
        std::cout << "4. Delete Task" << std::endl;
        std::cout << "5. View Users" << std::endl;
        std::cout << "6. Refresh Tasks" << std::endl;
        std::cout << "7. Logout" << std::endl;
        std::cout << "0. Exit" << std::endl;
        
        int choice;
        std::cout << "\nEnter your choice: ";
        std::cin >> choice;
        std::cin.ignore(); // Clear newline
        
        switch (choice) {
            case 1: viewTasks(); break;
            case 2: createTask(); break;
            case 3: editTask(); break;
            case 4: deleteTask(); break;
            case 5: viewUsers(); break;
            case 6: refreshTasks(); break;
            case 7: logout(); break;
            case 0: exit(0); break;
            default: std::cout << "Invalid choice!" << std::endl;
        }
    }

    void viewTasks() {
        std::cout << "\n=== Tasks ===" << std::endl;
        if (tasks_.empty()) {
            std::cout << "No tasks found." << std::endl;
            return;
        }
        
        for (const auto& task : tasks_) {
            std::cout << "\nID: " << task.id << std::endl;
            std::cout << "Title: " << task.title << std::endl;
            std::cout << "Description: " << task.description << std::endl;
            std::cout << "Priority: " << TaskManager::priorityToString(task.priority) << std::endl;
            std::cout << "Status: " << TaskManager::statusToString(task.status) << std::endl;
            std::cout << "Due Date: " << task.due_date << std::endl;
            std::cout << "Assigned to User ID: " << task.assigned_user_id << std::endl;
            std::cout << "---" << std::endl;
        }
    }

    void createTask() {
        if (current_user_.role == TaskManager::UserRole::EMPLOYEE) {
            std::cout << "Employees cannot create tasks." << std::endl;
            return;
        }
        
        std::cout << "\n=== Create Task ===" << std::endl;
        TaskManager::Task task;
        
        std::cout << "Title: ";
        std::getline(std::cin, task.title);
        
        std::cout << "Description: ";
        std::getline(std::cin, task.description);
        
        std::cout << "Priority (0=Low, 1=Medium, 2=High, 3=Urgent): ";
        int priority;
        std::cin >> priority;
        task.priority = static_cast<TaskManager::TaskPriority>(priority);
        
        std::cout << "Status (0=Pending, 1=In Progress, 2=Completed, 3=Cancelled): ";
        int status;
        std::cin >> status;
        task.status = static_cast<TaskManager::TaskStatus>(status);
        
        std::cout << "Due Date (YYYY-MM-DD): ";
        std::cin >> task.due_date;
        
        if (current_user_.role == TaskManager::UserRole::SUPER_USER || 
            current_user_.role == TaskManager::UserRole::MANAGER) {
            std::cout << "Assigned User ID: ";
            std::cin >> task.assigned_user_id;
        } else {
            task.assigned_user_id = current_user_.id;
        }
        
        task.created_by = current_user_.id;
        
        if (api_client_->createTask(task)) {
            std::cout << "Task created successfully!" << std::endl;
            refreshTasks();
        } else {
            std::cout << "Failed to create task." << std::endl;
        }
    }

    void editTask() {
        std::cout << "\n=== Edit Task ===" << std::endl;
        std::cout << "Enter task ID to edit: ";
        int task_id;
        std::cin >> task_id;
        std::cin.ignore();
        
        auto task = api_client_->getTaskById(task_id);
        if (!task.has_value()) {
            std::cout << "Task not found or access denied." << std::endl;
            return;
        }
        
        TaskManager::Task edit_task = task.value();
        
        std::cout << "Current title: " << edit_task.title << std::endl;
        std::cout << "New title (or press Enter to keep current): ";
        std::string new_title;
        std::getline(std::cin, new_title);
        if (!new_title.empty()) edit_task.title = new_title;
        
        std::cout << "Current description: " << edit_task.description << std::endl;
        std::cout << "New description (or press Enter to keep current): ";
        std::string new_desc;
        std::getline(std::cin, new_desc);
        if (!new_desc.empty()) edit_task.description = new_desc;
        
        std::cout << "Current priority: " << TaskManager::priorityToString(edit_task.priority) << std::endl;
        std::cout << "New priority (0=Low, 1=Medium, 2=High, 3=Urgent, or -1 to keep current): ";
        int priority;
        std::cin >> priority;
        if (priority >= 0) edit_task.priority = static_cast<TaskManager::TaskPriority>(priority);
        
        std::cout << "Current status: " << TaskManager::statusToString(edit_task.status) << std::endl;
        std::cout << "New status (0=Pending, 1=In Progress, 2=Completed, 3=Cancelled, or -1 to keep current): ";
        int status;
        std::cin >> status;
        if (status >= 0) edit_task.status = static_cast<TaskManager::TaskStatus>(status);
        
        if (api_client_->updateTask(edit_task)) {
            std::cout << "Task updated successfully!" << std::endl;
            refreshTasks();
        } else {
            std::cout << "Failed to update task." << std::endl;
        }
    }

    void deleteTask() {
        if (current_user_.role == TaskManager::UserRole::EMPLOYEE) {
            std::cout << "Employees cannot delete tasks." << std::endl;
            return;
        }
        
        std::cout << "\n=== Delete Task ===" << std::endl;
        std::cout << "Enter task ID to delete: ";
        int task_id;
        std::cin >> task_id;
        std::cin.ignore();
        
        std::cout << "Are you sure? (y/N): ";
        char confirm;
        std::cin >> confirm;
        std::cin.ignore();
        
        if (confirm == 'y' || confirm == 'Y') {
            if (api_client_->deleteTask(task_id)) {
                std::cout << "Task deleted successfully!" << std::endl;
                refreshTasks();
            } else {
                std::cout << "Failed to delete task." << std::endl;
            }
        }
    }

    void viewUsers() {
        if (current_user_.role == TaskManager::UserRole::EMPLOYEE) {
            std::cout << "Employees cannot view user management." << std::endl;
            return;
        }
        
        std::cout << "\n=== Users ===" << std::endl;
        auto users = api_client_->getUsers();
        if (users.empty()) {
            std::cout << "No users found." << std::endl;
            return;
        }
        
        for (const auto& user : users) {
            std::cout << "\nID: " << user.id << std::endl;
            std::cout << "Username: " << user.username << std::endl;
            std::cout << "Role: " << TaskManager::roleToString(user.role) << std::endl;
            if (user.manager_id.has_value()) {
                std::cout << "Manager ID: " << user.manager_id.value() << std::endl;
            }
            std::cout << "---" << std::endl;
        }
    }

    void refreshTasks() {
        tasks_ = api_client_->getTasks();
        std::cout << "Tasks refreshed. Found " << tasks_.size() << " tasks." << std::endl;
    }

    void logout() {
        api_client_->logout();
        authenticated_ = false;
        tasks_.clear();
        std::cout << "Logged out successfully." << std::endl;
    }
};

int main() {
    // Setup logging
    TaskManager::setupLogging();
    spdlog::info("Starting Task Manager Console Application");
    
    try {
        ConsoleUI ui;
        ui.run();
    } catch (const std::exception& e) {
        spdlog::error("Application error: {}", e.what());
        return 1;
    }
    
    return 0;
}
