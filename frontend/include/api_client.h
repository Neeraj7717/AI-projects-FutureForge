#pragma once

#include "common.h"
#include <cpprest/http_client.h>
#include <cpprest/json.h>
#include <string>
#include <vector>
#include <optional>

namespace TaskManager {

class ApiClient {
public:
    ApiClient(const std::string& base_url);
    
    // Authentication
    LoginResponse login(const std::string& username, const std::string& password);
    bool logout();
    
    // Task operations
    std::vector<Task> getTasks();
    std::optional<Task> getTaskById(int task_id);
    bool createTask(const Task& task);
    bool updateTask(const Task& task);
    bool deleteTask(int task_id);
    
    // Comments and history
    bool addComment(int task_id, const std::string& comment);
    std::vector<TaskComment> getTaskComments(int task_id);
    std::vector<TaskHistory> getTaskHistory(int task_id);
    
    // User operations
    std::vector<User> getUsers();
    
    // Utility
    void setAuthToken(const std::string& token);
    bool isAuthenticated() const;
    User getCurrentUser() const;
    
private:
    web::http::client::http_client client_;
    std::string auth_token_;
    User current_user_;
    bool authenticated_;
    
    web::http::http_request createRequest(web::http::method method, const std::string& path);
    web::json::value parseResponse(const web::http::http_response& response);
    Task jsonToTask(const web::json::value& json);
    User jsonToUser(const web::json::value& json);
    TaskComment jsonToComment(const web::json::value& json);
    TaskHistory jsonToHistory(const web::json::value& json);
};

} // namespace TaskManager
