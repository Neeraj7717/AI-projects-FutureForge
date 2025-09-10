#pragma once

#include "common.h"
#include "database.h"
#include "auth_service.h"
#include "task_service.h"
#include <cpprest/http_listener.h>
#include <cpprest/json.h>
#include <memory>

namespace TaskManager {

class ApiServer {
public:
    ApiServer(const std::string& address, int port);
    ~ApiServer();
    
    bool start();
    void stop();
    
private:
    std::string address_;
    int port_;
    std::unique_ptr<web::http::experimental::listener::http_listener> listener_;
    
    std::unique_ptr<Database> db_;
    std::unique_ptr<AuthService> auth_service_;
    std::unique_ptr<TaskService> task_service_;
    
    // HTTP handlers
    void handle_login(web::http::http_request request);
    void handle_logout(web::http::http_request request);
    void handle_get_tasks(web::http::http_request request);
    void handle_get_task(web::http::http_request request);
    void handle_create_task(web::http::http_request request);
    void handle_update_task(web::http::http_request request);
    void handle_delete_task(web::http::http_request request);
    void handle_add_comment(web::http::http_request request);
    void handle_get_comments(web::http::http_request request);
    void handle_get_history(web::http::http_request request);
    void handle_get_users(web::http::http_request request);
    
    // Utility methods
    std::optional<User> authenticate_request(web::http::http_request request);
    web::json::value taskToJson(const Task& task);
    web::json::value userToJson(const User& user);
    Task jsonToTask(const web::json::value& json);
    web::json::value createErrorResponse(const std::string& message);
    web::json::value createSuccessResponse(const std::string& message, const web::json::value& data = web::json::value::null());
};

} // namespace TaskManager
