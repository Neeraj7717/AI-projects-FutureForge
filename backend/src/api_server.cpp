#include "api_server.h"
#include <spdlog/spdlog.h>
#include <sstream>

namespace TaskManager {

ApiServer::ApiServer(const std::string& address, int port) 
    : address_(address), port_(port) {
    
    std::stringstream ss;
    ss << "http://" << address_ << ":" << port_;
    listener_ = std::make_unique<web::http::experimental::listener::http_listener>(ss.str());
    
    // Initialize services
    db_ = std::make_unique<Database>("taskmanager.db");
    auth_service_ = std::make_unique<AuthService>(*db_);
    task_service_ = std::make_unique<TaskService>(*db_, *auth_service_);
}

ApiServer::~ApiServer() {
    stop();
}

bool ApiServer::start() {
    if (!db_->initialize()) {
        spdlog::error("Failed to initialize database");
        return false;
    }
    
    // Set up routes
    listener_->support(web::http::methods::POST, [this](web::http::http_request request) {
        auto path = request.relative_uri().path();
        if (path == "/auth/login") {
            handle_login(request);
        } else if (path == "/auth/logout") {
            handle_logout(request);
        } else if (path == "/tasks") {
            handle_create_task(request);
        } else if (path.find("/tasks/") == 0 && path.find("/comments") != std::string::npos) {
            handle_add_comment(request);
        }
    });
    
    listener_->support(web::http::methods::GET, [this](web::http::http_request request) {
        auto path = request.relative_uri().path();
        if (path == "/tasks") {
            handle_get_tasks(request);
        } else if (path.find("/tasks/") == 0) {
            if (path.find("/comments") != std::string::npos) {
                handle_get_comments(request);
            } else if (path.find("/history") != std::string::npos) {
                handle_get_history(request);
            } else {
                handle_get_task(request);
            }
        } else if (path == "/users") {
            handle_get_users(request);
        }
    });
    
    listener_->support(web::http::methods::PUT, [this](web::http::http_request request) {
        auto path = request.relative_uri().path();
        if (path.find("/tasks/") == 0) {
            handle_update_task(request);
        }
    });
    
    listener_->support(web::http::methods::DEL, [this](web::http::http_request request) {
        auto path = request.relative_uri().path();
        if (path.find("/tasks/") == 0) {
            handle_delete_task(request);
        }
    });
    
    try {
        listener_->open().wait();
        spdlog::info("API Server started on {}:{}", address_, port_);
        return true;
    } catch (const std::exception& e) {
        spdlog::error("Failed to start API server: {}", e.what());
        return false;
    }
}

void ApiServer::stop() {
    if (listener_) {
        listener_->close().wait();
    }
}

void ApiServer::handle_login(web::http::http_request request) {
    request.extract_json().then([this, request](web::json::value json) {
        try {
            LoginRequest login_req;
            login_req.username = json.at("username").as_string();
            login_req.password = json.at("password").as_string();
            
            auto response = auth_service_->login(login_req);
            
            web::json::value response_json;
            response_json["success"] = response.success;
            response_json["message"] = web::json::value::string(response.message);
            
            if (response.success) {
                response_json["token"] = web::json::value::string(response.token);
                response_json["user"] = userToJson(response.user);
            }
            
            request.reply(web::http::status_codes::OK, response_json);
        } catch (const std::exception& e) {
            spdlog::error("Login error: {}", e.what());
            request.reply(web::http::status_codes::BadRequest, createErrorResponse("Invalid request"));
        }
    });
}

void ApiServer::handle_logout(web::http::http_request request) {
    auto user = authenticate_request(request);
    if (!user.has_value()) {
        request.reply(web::http::status_codes::Unauthorized, createErrorResponse("Unauthorized"));
        return;
    }
    
    auth_service_->logout(""); // Token would be passed in real implementation
    request.reply(web::http::status_codes::OK, createSuccessResponse("Logged out successfully"));
}

void ApiServer::handle_get_tasks(web::http::http_request request) {
    auto user = authenticate_request(request);
    if (!user.has_value()) {
        request.reply(web::http::status_codes::Unauthorized, createErrorResponse("Unauthorized"));
        return;
    }
    
    auto tasks = task_service_->getTasks(user.value());
    
    web::json::value tasks_json = web::json::value::array();
    for (size_t i = 0; i < tasks.size(); ++i) {
        tasks_json[i] = taskToJson(tasks[i]);
    }
    
    request.reply(web::http::status_codes::OK, createSuccessResponse("Tasks retrieved", tasks_json));
}

void ApiServer::handle_get_task(web::http::http_request request) {
    auto user = authenticate_request(request);
    if (!user.has_value()) {
        request.reply(web::http::status_codes::Unauthorized, createErrorResponse("Unauthorized"));
        return;
    }
    
    auto path = request.relative_uri().path();
    auto task_id = std::stoi(path.substr(path.find_last_of('/') + 1));
    
    auto task = task_service_->getTaskById(task_id, user.value());
    if (!task.has_value()) {
        request.reply(web::http::status_codes::NotFound, createErrorResponse("Task not found"));
        return;
    }
    
    request.reply(web::http::status_codes::OK, createSuccessResponse("Task retrieved", taskToJson(task.value())));
}

void ApiServer::handle_create_task(web::http::http_request request) {
    auto user = authenticate_request(request);
    if (!user.has_value()) {
        request.reply(web::http::status_codes::Unauthorized, createErrorResponse("Unauthorized"));
        return;
    }
    
    request.extract_json().then([this, request, user](web::json::value json) {
        try {
            Task task = jsonToTask(json);
            task.created_by = user->id;
            
            bool success = task_service_->createTask(task, user.value());
            if (success) {
                request.reply(web::http::status_codes::Created, createSuccessResponse("Task created successfully"));
            } else {
                request.reply(web::http::status_codes::BadRequest, createErrorResponse("Failed to create task"));
            }
        } catch (const std::exception& e) {
            spdlog::error("Create task error: {}", e.what());
            request.reply(web::http::status_codes::BadRequest, createErrorResponse("Invalid request"));
        }
    });
}

void ApiServer::handle_update_task(web::http::http_request request) {
    auto user = authenticate_request(request);
    if (!user.has_value()) {
        request.reply(web::http::status_codes::Unauthorized, createErrorResponse("Unauthorized"));
        return;
    }
    
    auto path = request.relative_uri().path();
    auto task_id = std::stoi(path.substr(path.find_last_of('/') + 1));
    
    request.extract_json().then([this, request, user, task_id](web::json::value json) {
        try {
            Task task = jsonToTask(json);
            task.id = task_id;
            
            bool success = task_service_->updateTask(task, user.value());
            if (success) {
                request.reply(web::http::status_codes::OK, createSuccessResponse("Task updated successfully"));
            } else {
                request.reply(web::http::status_codes::BadRequest, createErrorResponse("Failed to update task"));
            }
        } catch (const std::exception& e) {
            spdlog::error("Update task error: {}", e.what());
            request.reply(web::http::status_codes::BadRequest, createErrorResponse("Invalid request"));
        }
    });
}

void ApiServer::handle_delete_task(web::http::http_request request) {
    auto user = authenticate_request(request);
    if (!user.has_value()) {
        request.reply(web::http::status_codes::Unauthorized, createErrorResponse("Unauthorized"));
        return;
    }
    
    auto path = request.relative_uri().path();
    auto task_id = std::stoi(path.substr(path.find_last_of('/') + 1));
    
    bool success = task_service_->deleteTask(task_id, user.value());
    if (success) {
        request.reply(web::http::status_codes::OK, createSuccessResponse("Task deleted successfully"));
    } else {
        request.reply(web::http::status_codes::BadRequest, createErrorResponse("Failed to delete task"));
    }
}

void ApiServer::handle_add_comment(web::http::http_request request) {
    auto user = authenticate_request(request);
    if (!user.has_value()) {
        request.reply(web::http::status_codes::Unauthorized, createErrorResponse("Unauthorized"));
        return;
    }
    
    auto path = request.relative_uri().path();
    auto task_id = std::stoi(path.substr(path.find("/tasks/") + 7, path.find("/comments") - path.find("/tasks/") - 7));
    
    request.extract_json().then([this, request, user, task_id](web::json::value json) {
        try {
            std::string comment = json.at("comment").as_string();
            
            bool success = task_service_->addComment(task_id, comment, user.value());
            if (success) {
                request.reply(web::http::status_codes::OK, createSuccessResponse("Comment added successfully"));
            } else {
                request.reply(web::http::status_codes::BadRequest, createErrorResponse("Failed to add comment"));
            }
        } catch (const std::exception& e) {
            spdlog::error("Add comment error: {}", e.what());
            request.reply(web::http::status_codes::BadRequest, createErrorResponse("Invalid request"));
        }
    });
}

void ApiServer::handle_get_comments(web::http::http_request request) {
    auto user = authenticate_request(request);
    if (!user.has_value()) {
        request.reply(web::http::status_codes::Unauthorized, createErrorResponse("Unauthorized"));
        return;
    }
    
    auto path = request.relative_uri().path();
    auto task_id = std::stoi(path.substr(path.find("/tasks/") + 7, path.find("/comments") - path.find("/tasks/") - 7));
    
    auto comments = task_service_->getTaskComments(task_id, user.value());
    
    web::json::value comments_json = web::json::value::array();
    for (size_t i = 0; i < comments.size(); ++i) {
        web::json::value comment_json;
        comment_json["id"] = comments[i].id;
        comment_json["task_id"] = comments[i].task_id;
        comment_json["user_id"] = comments[i].user_id;
        comment_json["comment"] = web::json::value::string(comments[i].comment);
        comment_json["created_at"] = web::json::value::string(comments[i].created_at);
        comments_json[i] = comment_json;
    }
    
    request.reply(web::http::status_codes::OK, createSuccessResponse("Comments retrieved", comments_json));
}

void ApiServer::handle_get_history(web::http::http_request request) {
    auto user = authenticate_request(request);
    if (!user.has_value()) {
        request.reply(web::http::status_codes::Unauthorized, createErrorResponse("Unauthorized"));
        return;
    }
    
    auto path = request.relative_uri().path();
    auto task_id = std::stoi(path.substr(path.find("/tasks/") + 7, path.find("/history") - path.find("/tasks/") - 7));
    
    auto history = task_service_->getTaskHistory(task_id, user.value());
    
    web::json::value history_json = web::json::value::array();
    for (size_t i = 0; i < history.size(); ++i) {
        web::json::value h_json;
        h_json["id"] = history[i].id;
        h_json["task_id"] = history[i].task_id;
        h_json["action"] = web::json::value::string(history[i].action);
        h_json["user_id"] = history[i].user_id;
        h_json["comment"] = web::json::value::string(history[i].comment);
        h_json["created_at"] = web::json::value::string(history[i].created_at);
        history_json[i] = h_json;
    }
    
    request.reply(web::http::status_codes::OK, createSuccessResponse("History retrieved", history_json));
}

void ApiServer::handle_get_users(web::http::http_request request) {
    auto user = authenticate_request(request);
    if (!user.has_value()) {
        request.reply(web::http::status_codes::Unauthorized, createErrorResponse("Unauthorized"));
        return;
    }
    
    if (user->role != UserRole::SUPER_USER && user->role != UserRole::MANAGER) {
        request.reply(web::http::status_codes::Forbidden, createErrorResponse("Insufficient permissions"));
        return;
    }
    
    std::vector<User> users;
    if (user->role == UserRole::SUPER_USER) {
        users = db_->getAllUsers();
    } else {
        users = db_->getUsersByManager(user->id);
    }
    
    web::json::value users_json = web::json::value::array();
    for (size_t i = 0; i < users.size(); ++i) {
        users_json[i] = userToJson(users[i]);
    }
    
    request.reply(web::http::status_codes::OK, createSuccessResponse("Users retrieved", users_json));
}

std::optional<User> ApiServer::authenticate_request(web::http::http_request request) {
    auto headers = request.headers();
    auto auth_header = headers.find("Authorization");
    
    if (auth_header == headers.end()) {
        return std::nullopt;
    }
    
    std::string token = auth_header->second;
    if (token.find("Bearer ") == 0) {
        token = token.substr(7);
    }
    
    return auth_service_->validateToken(token);
}

web::json::value ApiServer::taskToJson(const Task& task) {
    web::json::value json;
    json["id"] = task.id;
    json["title"] = web::json::value::string(task.title);
    json["description"] = web::json::value::string(task.description);
    json["priority"] = web::json::value::string(priorityToString(task.priority));
    json["status"] = web::json::value::string(statusToString(task.status));
    json["assigned_user_id"] = task.assigned_user_id;
    json["created_by"] = task.created_by;
    json["due_date"] = web::json::value::string(task.due_date);
    json["created_at"] = web::json::value::string(task.created_at);
    json["updated_at"] = web::json::value::string(task.updated_at);
    return json;
}

web::json::value ApiServer::userToJson(const User& user) {
    web::json::value json;
    json["id"] = user.id;
    json["username"] = web::json::value::string(user.username);
    json["role"] = web::json::value::string(roleToString(user.role));
    if (user.manager_id.has_value()) {
        json["manager_id"] = user.manager_id.value();
    }
    json["created_at"] = web::json::value::string(user.created_at);
    json["updated_at"] = web::json::value::string(user.updated_at);
    return json;
}

Task ApiServer::jsonToTask(const web::json::value& json) {
    Task task;
    task.title = json.at("title").as_string();
    task.description = json.at("description").as_string();
    task.priority = stringToPriority(json.at("priority").as_string());
    task.status = stringToStatus(json.at("status").as_string());
    task.assigned_user_id = json.at("assigned_user_id").as_integer();
    task.due_date = json.at("due_date").as_string();
    return task;
}

web::json::value ApiServer::createErrorResponse(const std::string& message) {
    web::json::value response;
    response["success"] = false;
    response["message"] = web::json::value::string(message);
    return response;
}

web::json::value ApiServer::createSuccessResponse(const std::string& message, const web::json::value& data) {
    web::json::value response;
    response["success"] = true;
    response["message"] = web::json::value::string(message);
    if (!data.is_null()) {
        response["data"] = data;
    }
    return response;
}

} // namespace TaskManager
