#include "api_client.h"
#include <spdlog/spdlog.h>

namespace TaskManager {

ApiClient::ApiClient(const std::string& base_url) 
    : client_(base_url), authenticated_(false) {
}

LoginResponse ApiClient::login(const std::string& username, const std::string& password) {
    LoginResponse response;
    
    try {
        auto request = createRequest(web::http::methods::POST, "/auth/login");
        
        web::json::value login_data;
        login_data["username"] = web::json::value::string(username);
        login_data["password"] = web::json::value::string(password);
        request.set_body(login_data);
        
        auto response_task = client_.request(request).then([&](web::http::http_response http_response) {
            return parseResponse(http_response);
        });
        
        auto json_response = response_task.get();
        
        response.success = json_response["success"].as_bool();
        response.message = json_response["message"].as_string();
        
        if (response.success) {
            response.token = json_response["token"].as_string();
            response.user = jsonToUser(json_response["user"]);
            
            setAuthToken(response.token);
            current_user_ = response.user;
            authenticated_ = true;
        }
        
    } catch (const std::exception& e) {
        spdlog::error("Login error: {}", e.what());
        response.success = false;
        response.message = "Connection error";
    }
    
    return response;
}

bool ApiClient::logout() {
    if (!authenticated_) {
        return true;
    }
    
    try {
        auto request = createRequest(web::http::methods::POST, "/auth/logout");
        auto response_task = client_.request(request).then([&](web::http::http_response http_response) {
            return parseResponse(http_response);
        });
        
        auto json_response = response_task.get();
        bool success = json_response["success"].as_bool();
        
        if (success) {
            authenticated_ = false;
            auth_token_.clear();
        }
        
        return success;
        
    } catch (const std::exception& e) {
        spdlog::error("Logout error: {}", e.what());
        return false;
    }
}

std::vector<Task> ApiClient::getTasks() {
    std::vector<Task> tasks;
    
    if (!authenticated_) {
        return tasks;
    }
    
    try {
        auto request = createRequest(web::http::methods::GET, "/tasks");
        auto response_task = client_.request(request).then([&](web::http::http_response http_response) {
            return parseResponse(http_response);
        });
        
        auto json_response = response_task.get();
        
        if (json_response["success"].as_bool()) {
            auto tasks_array = json_response["data"].as_array();
            for (const auto& task_json : tasks_array) {
                tasks.push_back(jsonToTask(task_json));
            }
        }
        
    } catch (const std::exception& e) {
        spdlog::error("Get tasks error: {}", e.what());
    }
    
    return tasks;
}

std::optional<Task> ApiClient::getTaskById(int task_id) {
    if (!authenticated_) {
        return std::nullopt;
    }
    
    try {
        auto request = createRequest(web::http::methods::GET, "/tasks/" + std::to_string(task_id));
        auto response_task = client_.request(request).then([&](web::http::http_response http_response) {
            return parseResponse(http_response);
        });
        
        auto json_response = response_task.get();
        
        if (json_response["success"].as_bool()) {
            return jsonToTask(json_response["data"]);
        }
        
    } catch (const std::exception& e) {
        spdlog::error("Get task error: {}", e.what());
    }
    
    return std::nullopt;
}

bool ApiClient::createTask(const Task& task) {
    if (!authenticated_) {
        return false;
    }
    
    try {
        auto request = createRequest(web::http::methods::POST, "/tasks");
        
        web::json::value task_data;
        task_data["title"] = web::json::value::string(task.title);
        task_data["description"] = web::json::value::string(task.description);
        task_data["priority"] = web::json::value::string(priorityToString(task.priority));
        task_data["status"] = web::json::value::string(statusToString(task.status));
        task_data["assigned_user_id"] = task.assigned_user_id;
        task_data["due_date"] = web::json::value::string(task.due_date);
        
        request.set_body(task_data);
        
        auto response_task = client_.request(request).then([&](web::http::http_response http_response) {
            return parseResponse(http_response);
        });
        
        auto json_response = response_task.get();
        return json_response["success"].as_bool();
        
    } catch (const std::exception& e) {
        spdlog::error("Create task error: {}", e.what());
        return false;
    }
}

bool ApiClient::updateTask(const Task& task) {
    if (!authenticated_) {
        return false;
    }
    
    try {
        auto request = createRequest(web::http::methods::PUT, "/tasks/" + std::to_string(task.id));
        
        web::json::value task_data;
        task_data["title"] = web::json::value::string(task.title);
        task_data["description"] = web::json::value::string(task.description);
        task_data["priority"] = web::json::value::string(priorityToString(task.priority));
        task_data["status"] = web::json::value::string(statusToString(task.status));
        task_data["assigned_user_id"] = task.assigned_user_id;
        task_data["due_date"] = web::json::value::string(task.due_date);
        
        request.set_body(task_data);
        
        auto response_task = client_.request(request).then([&](web::http::http_response http_response) {
            return parseResponse(http_response);
        });
        
        auto json_response = response_task.get();
        return json_response["success"].as_bool();
        
    } catch (const std::exception& e) {
        spdlog::error("Update task error: {}", e.what());
        return false;
    }
}

bool ApiClient::deleteTask(int task_id) {
    if (!authenticated_) {
        return false;
    }
    
    try {
        auto request = createRequest(web::http::methods::DEL, "/tasks/" + std::to_string(task_id));
        
        auto response_task = client_.request(request).then([&](web::http::http_response http_response) {
            return parseResponse(http_response);
        });
        
        auto json_response = response_task.get();
        return json_response["success"].as_bool();
        
    } catch (const std::exception& e) {
        spdlog::error("Delete task error: {}", e.what());
        return false;
    }
}

bool ApiClient::addComment(int task_id, const std::string& comment) {
    if (!authenticated_) {
        return false;
    }
    
    try {
        auto request = createRequest(web::http::methods::POST, "/tasks/" + std::to_string(task_id) + "/comments");
        
        web::json::value comment_data;
        comment_data["comment"] = web::json::value::string(comment);
        
        request.set_body(comment_data);
        
        auto response_task = client_.request(request).then([&](web::http::http_response http_response) {
            return parseResponse(http_response);
        });
        
        auto json_response = response_task.get();
        return json_response["success"].as_bool();
        
    } catch (const std::exception& e) {
        spdlog::error("Add comment error: {}", e.what());
        return false;
    }
}

std::vector<TaskComment> ApiClient::getTaskComments(int task_id) {
    std::vector<TaskComment> comments;
    
    if (!authenticated_) {
        return comments;
    }
    
    try {
        auto request = createRequest(web::http::methods::GET, "/tasks/" + std::to_string(task_id) + "/comments");
        auto response_task = client_.request(request).then([&](web::http::http_response http_response) {
            return parseResponse(http_response);
        });
        
        auto json_response = response_task.get();
        
        if (json_response["success"].as_bool()) {
            auto comments_array = json_response["data"].as_array();
            for (const auto& comment_json : comments_array) {
                comments.push_back(jsonToComment(comment_json));
            }
        }
        
    } catch (const std::exception& e) {
        spdlog::error("Get comments error: {}", e.what());
    }
    
    return comments;
}

std::vector<TaskHistory> ApiClient::getTaskHistory(int task_id) {
    std::vector<TaskHistory> history;
    
    if (!authenticated_) {
        return history;
    }
    
    try {
        auto request = createRequest(web::http::methods::GET, "/tasks/" + std::to_string(task_id) + "/history");
        auto response_task = client_.request(request).then([&](web::http::http_response http_response) {
            return parseResponse(http_response);
        });
        
        auto json_response = response_task.get();
        
        if (json_response["success"].as_bool()) {
            auto history_array = json_response["data"].as_array();
            for (const auto& history_json : history_array) {
                history.push_back(jsonToHistory(history_json));
            }
        }
        
    } catch (const std::exception& e) {
        spdlog::error("Get history error: {}", e.what());
    }
    
    return history;
}

std::vector<User> ApiClient::getUsers() {
    std::vector<User> users;
    
    if (!authenticated_) {
        return users;
    }
    
    try {
        auto request = createRequest(web::http::methods::GET, "/users");
        auto response_task = client_.request(request).then([&](web::http::http_response http_response) {
            return parseResponse(http_response);
        });
        
        auto json_response = response_task.get();
        
        if (json_response["success"].as_bool()) {
            auto users_array = json_response["data"].as_array();
            for (const auto& user_json : users_array) {
                users.push_back(jsonToUser(user_json));
            }
        }
        
    } catch (const std::exception& e) {
        spdlog::error("Get users error: {}", e.what());
    }
    
    return users;
}

void ApiClient::setAuthToken(const std::string& token) {
    auth_token_ = token;
}

bool ApiClient::isAuthenticated() const {
    return authenticated_;
}

User ApiClient::getCurrentUser() const {
    return current_user_;
}

web::http::http_request ApiClient::createRequest(web::http::method method, const std::string& path) {
    web::http::http_request request(method);
    request.set_request_uri(path);
    
    if (!auth_token_.empty()) {
        request.headers().add("Authorization", "Bearer " + auth_token_);
    }
    
    request.headers().add("Content-Type", "application/json");
    return request;
}

web::json::value ApiClient::parseResponse(const web::http::http_response& response) {
    if (response.status_code() != web::http::status_codes::OK) {
        web::json::value error_response;
        error_response["success"] = false;
        error_response["message"] = web::json::value::string("HTTP Error: " + std::to_string(response.status_code()));
        return error_response;
    }
    
    return response.extract_json().get();
}

Task ApiClient::jsonToTask(const web::json::value& json) {
    Task task;
    task.id = json["id"].as_integer();
    task.title = json["title"].as_string();
    task.description = json["description"].as_string();
    task.priority = stringToPriority(json["priority"].as_string());
    task.status = stringToStatus(json["status"].as_string());
    task.assigned_user_id = json["assigned_user_id"].as_integer();
    task.created_by = json["created_by"].as_integer();
    task.due_date = json["due_date"].as_string();
    task.created_at = json["created_at"].as_string();
    task.updated_at = json["updated_at"].as_string();
    return task;
}

User ApiClient::jsonToUser(const web::json::value& json) {
    User user;
    user.id = json["id"].as_integer();
    user.username = json["username"].as_string();
    user.role = stringToRole(json["role"].as_string());
    if (json.has_field("manager_id") && !json["manager_id"].is_null()) {
        user.manager_id = json["manager_id"].as_integer();
    }
    user.created_at = json["created_at"].as_string();
    user.updated_at = json["updated_at"].as_string();
    return user;
}

TaskComment ApiClient::jsonToComment(const web::json::value& json) {
    TaskComment comment;
    comment.id = json["id"].as_integer();
    comment.task_id = json["task_id"].as_integer();
    comment.user_id = json["user_id"].as_integer();
    comment.comment = json["comment"].as_string();
    comment.created_at = json["created_at"].as_string();
    return comment;
}

TaskHistory ApiClient::jsonToHistory(const web::json::value& json) {
    TaskHistory history;
    history.id = json["id"].as_integer();
    history.task_id = json["task_id"].as_integer();
    history.action = json["action"].as_string();
    history.user_id = json["user_id"].as_integer();
    history.comment = json["comment"].as_string();
    history.created_at = json["created_at"].as_string();
    return history;
}

} // namespace TaskManager
