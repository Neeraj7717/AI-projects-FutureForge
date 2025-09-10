#pragma once

#include <string>
#include <vector>
#include <memory>
#include <chrono>
#include <optional>

namespace TaskManager {

enum class UserRole {
    SUPER_USER,
    MANAGER,
    EMPLOYEE
};

enum class TaskPriority {
    LOW,
    MEDIUM,
    HIGH,
    URGENT
};

enum class TaskStatus {
    PENDING,
    IN_PROGRESS,
    COMPLETED,
    CANCELLED
};

struct User {
    int id;
    std::string username;
    std::string password_hash;
    UserRole role;
    std::optional<int> manager_id;
    std::string created_at;
    std::string updated_at;
};

struct Task {
    int id;
    std::string title;
    std::string description;
    TaskPriority priority;
    TaskStatus status;
    int assigned_user_id;
    int created_by;
    std::string due_date;
    std::string created_at;
    std::string updated_at;
};

struct TaskComment {
    int id;
    int task_id;
    int user_id;
    std::string comment;
    std::string created_at;
};

struct TaskHistory {
    int id;
    int task_id;
    std::string action;
    int user_id;
    std::string comment;
    std::string created_at;
};

struct LoginRequest {
    std::string username;
    std::string password;
};

struct LoginResponse {
    bool success;
    std::string token;
    User user;
    std::string message;
};

struct ApiResponse {
    bool success;
    std::string message;
    std::string data;
};

// Utility functions
std::string roleToString(UserRole role);
UserRole stringToRole(const std::string& role);
std::string priorityToString(TaskPriority priority);
TaskPriority stringToPriority(const std::string& priority);
std::string statusToString(TaskStatus status);
TaskStatus stringToStatus(const std::string& status);

} // namespace TaskManager
