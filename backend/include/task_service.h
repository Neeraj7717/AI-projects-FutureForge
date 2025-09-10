#pragma once

#include "common.h"
#include "database.h"
#include "auth_service.h"
#include <vector>
#include <string>

namespace TaskManager {

class TaskService {
public:
    TaskService(Database& db, AuthService& auth);
    
    std::vector<Task> getTasks(const User& user);
    std::optional<Task> getTaskById(int task_id, const User& user);
    bool createTask(const Task& task, const User& user);
    bool updateTask(const Task& task, const User& user);
    bool deleteTask(int task_id, const User& user);
    bool addComment(int task_id, const std::string& comment, const User& user);
    std::vector<TaskComment> getTaskComments(int task_id, const User& user);
    std::vector<TaskHistory> getTaskHistory(int task_id, const User& user);
    
    // Filtering and sorting
    std::vector<Task> filterTasks(const std::vector<Task>& tasks, 
                                 const std::string& priority = "",
                                 const std::string& status = "",
                                 const std::string& assigned_user = "");
    
private:
    Database& db_;
    AuthService& auth_;
    
    void logTaskAction(int task_id, const std::string& action, const User& user, const std::string& comment = "");
};

} // namespace TaskManager
