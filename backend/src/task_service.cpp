#include "task_service.h"
#include <spdlog/spdlog.h>
#include <algorithm>

namespace TaskManager {

TaskService::TaskService(Database& db, AuthService& auth) : db_(db), auth_(auth) {
}

std::vector<Task> TaskService::getTasks(const User& user) {
    std::vector<Task> tasks;
    
    if (user.role == UserRole::SUPER_USER) {
        tasks = db_.getAllTasks();
    } else if (user.role == UserRole::MANAGER) {
        tasks = db_.getTasksByManager(user.id);
    } else if (user.role == UserRole::EMPLOYEE) {
        tasks = db_.getTasksByUser(user.id);
    }
    
    return tasks;
}

std::optional<Task> TaskService::getTaskById(int task_id, const User& user) {
    auto task = db_.getTaskById(task_id);
    if (!task.has_value()) {
        return std::nullopt;
    }
    
    // Check permissions
    if (user.role == UserRole::SUPER_USER) {
        return task;
    } else if (user.role == UserRole::MANAGER) {
        // Manager can see tasks they created or assigned to their employees
        if (task->created_by == user.id || task->assigned_user_id == user.id) {
            return task;
        }
        // Check if assigned to one of their employees
        auto employees = db_.getUsersByManager(user.id);
        for (const auto& emp : employees) {
            if (emp.id == task->assigned_user_id) {
                return task;
            }
        }
    } else if (user.role == UserRole::EMPLOYEE) {
        if (task->assigned_user_id == user.id) {
            return task;
        }
    }
    
    return std::nullopt;
}

bool TaskService::createTask(const Task& task, const User& user) {
    // Check permissions
    if (user.role == UserRole::EMPLOYEE) {
        spdlog::error("Employee {} attempted to create task", user.username);
        return false;
    }
    
    if (user.role == UserRole::MANAGER) {
        // Manager can only assign tasks to themselves or their employees
        if (task.assigned_user_id != user.id) {
            auto employees = db_.getUsersByManager(user.id);
            bool can_assign = false;
            for (const auto& emp : employees) {
                if (emp.id == task.assigned_user_id) {
                    can_assign = true;
                    break;
                }
            }
            if (!can_assign) {
                spdlog::error("Manager {} attempted to assign task to unauthorized user", user.username);
                return false;
            }
        }
    }
    
    bool success = db_.createTask(task);
    if (success) {
        logTaskAction(task.id, "Created", user, "Task created");
        spdlog::info("Task '{}' created by user {}", task.title, user.username);
    }
    
    return success;
}

bool TaskService::updateTask(const Task& task, const User& user) {
    auto existing_task = db_.getTaskById(task.id);
    if (!existing_task.has_value()) {
        return false;
    }
    
    // Check permissions
    if (user.role == UserRole::EMPLOYEE) {
        if (task.assigned_user_id != user.id) {
            spdlog::error("Employee {} attempted to update task not assigned to them", user.username);
            return false;
        }
    } else if (user.role == UserRole::MANAGER) {
        // Manager can update tasks they created or assigned to their employees
        if (task.created_by != user.id && task.assigned_user_id != user.id) {
            auto employees = db_.getUsersByManager(user.id);
            bool can_update = false;
            for (const auto& emp : employees) {
                if (emp.id == task.assigned_user_id) {
                    can_update = true;
                    break;
                }
            }
            if (!can_update) {
                spdlog::error("Manager {} attempted to update unauthorized task", user.username);
                return false;
            }
        }
    }
    
    bool success = db_.updateTask(task);
    if (success) {
        logTaskAction(task.id, "Updated", user, "Task updated");
        spdlog::info("Task '{}' updated by user {}", task.title, user.username);
    }
    
    return success;
}

bool TaskService::deleteTask(int task_id, const User& user) {
    auto task = db_.getTaskById(task_id);
    if (!task.has_value()) {
        return false;
    }
    
    // Check permissions
    if (user.role == UserRole::EMPLOYEE) {
        spdlog::error("Employee {} attempted to delete task", user.username);
        return false;
    }
    
    if (user.role == UserRole::MANAGER) {
        if (task->created_by != user.id) {
            spdlog::error("Manager {} attempted to delete task not created by them", user.username);
            return false;
        }
    }
    
    bool success = db_.deleteTask(task_id);
    if (success) {
        logTaskAction(task_id, "Deleted", user, "Task deleted");
        spdlog::info("Task '{}' deleted by user {}", task->title, user.username);
    }
    
    return success;
}

bool TaskService::addComment(int task_id, const std::string& comment, const User& user) {
    auto task = getTaskById(task_id, user);
    if (!task.has_value()) {
        return false;
    }
    
    TaskComment task_comment;
    task_comment.task_id = task_id;
    task_comment.user_id = user.id;
    task_comment.comment = comment;
    
    bool success = db_.addTaskComment(task_comment);
    if (success) {
        logTaskAction(task_id, "Comment Added", user, comment);
        spdlog::info("Comment added to task {} by user {}", task_id, user.username);
    }
    
    return success;
}

std::vector<TaskComment> TaskService::getTaskComments(int task_id, const User& user) {
    auto task = getTaskById(task_id, user);
    if (!task.has_value()) {
        return {};
    }
    
    return db_.getTaskComments(task_id);
}

std::vector<TaskHistory> TaskService::getTaskHistory(int task_id, const User& user) {
    auto task = getTaskById(task_id, user);
    if (!task.has_value()) {
        return {};
    }
    
    return db_.getTaskHistory(task_id);
}

std::vector<Task> TaskService::filterTasks(const std::vector<Task>& tasks, 
                                          const std::string& priority,
                                          const std::string& status,
                                          const std::string& assigned_user) {
    std::vector<Task> filtered_tasks = tasks;
    
    if (!priority.empty()) {
        auto it = std::remove_if(filtered_tasks.begin(), filtered_tasks.end(),
            [&priority](const Task& task) {
                return priorityToString(task.priority) != priority;
            });
        filtered_tasks.erase(it, filtered_tasks.end());
    }
    
    if (!status.empty()) {
        auto it = std::remove_if(filtered_tasks.begin(), filtered_tasks.end(),
            [&status](const Task& task) {
                return statusToString(task.status) != status;
            });
        filtered_tasks.erase(it, filtered_tasks.end());
    }
    
    if (!assigned_user.empty()) {
        auto it = std::remove_if(filtered_tasks.begin(), filtered_tasks.end(),
            [&assigned_user](const Task& task) {
                // This would need user lookup in a real implementation
                return std::to_string(task.assigned_user_id) != assigned_user;
            });
        filtered_tasks.erase(it, filtered_tasks.end());
    }
    
    return filtered_tasks;
}

void TaskService::logTaskAction(int task_id, const std::string& action, const User& user, const std::string& comment) {
    TaskHistory history;
    history.task_id = task_id;
    history.action = action;
    history.user_id = user.id;
    history.comment = comment;
    
    db_.addTaskHistory(history);
}

} // namespace TaskManager
