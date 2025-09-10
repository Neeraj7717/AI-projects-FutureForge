#include "auth_service.h"
#include <spdlog/spdlog.h>
#include <sstream>
#include <iomanip>
#include <openssl/sha.h>
#include <openssl/evp.h>
#include <random>

namespace TaskManager {

AuthService::AuthService(Database& db) : db_(db) {
}

LoginResponse AuthService::login(const LoginRequest& request) {
    LoginResponse response;
    
    auto user = db_.getUserByUsername(request.username);
    if (!user.has_value()) {
        response.success = false;
        response.message = "Invalid username or password";
        return response;
    }
    
    if (!verifyPassword(request.password, user->password_hash)) {
        response.success = false;
        response.message = "Invalid username or password";
        return response;
    }
    
    response.success = true;
    response.token = generateToken(user.value());
    response.user = user.value();
    response.message = "Login successful";
    
    spdlog::info("User {} logged in successfully", request.username);
    return response;
}

bool AuthService::logout(const std::string& token) {
    // In a real implementation, you would invalidate the token
    // For simplicity, we'll just log the logout
    spdlog::info("User logged out");
    return true;
}

std::optional<User> AuthService::validateToken(const std::string& token) {
    // Simple token validation - in production, use JWT or similar
    // For now, we'll extract user ID from token and validate
    try {
        // Token format: "user_id:username:role"
        size_t pos1 = token.find(':');
        size_t pos2 = token.find(':', pos1 + 1);
        
        if (pos1 == std::string::npos || pos2 == std::string::npos) {
            return std::nullopt;
        }
        
        int user_id = std::stoi(token.substr(0, pos1));
        auto user = db_.getUserById(user_id);
        
        if (user.has_value() && user->username == token.substr(pos1 + 1, pos2 - pos1 - 1)) {
            return user;
        }
    } catch (const std::exception& e) {
        spdlog::error("Token validation error: {}", e.what());
    }
    
    return std::nullopt;
}

bool AuthService::hasPermission(const User& user, const std::string& action, int resource_id) {
    if (user.role == UserRole::SUPER_USER) {
        return true; // Super user can do everything
    }
    
    if (user.role == UserRole::MANAGER) {
        if (action == "view_all_tasks" || action == "create_task" || action == "edit_task" || action == "delete_task") {
            return true;
        }
        if (action == "view_user_tasks" && resource_id == user.id) {
            return true;
        }
        // Managers can manage their employees' tasks
        if (action == "manage_employee_task") {
            auto employees = db_.getUsersByManager(user.id);
            for (const auto& emp : employees) {
                if (emp.id == resource_id) return true;
            }
        }
        return false;
    }
    
    if (user.role == UserRole::EMPLOYEE) {
        if (action == "view_own_tasks" && resource_id == user.id) {
            return true;
        }
        if (action == "edit_own_task" && resource_id == user.id) {
            return true;
        }
        return false;
    }
    
    return false;
}

std::string AuthService::generateToken(const User& user) {
    // Simple token generation - in production, use JWT
    std::stringstream token;
    token << user.id << ":" << user.username << ":" << roleToString(user.role);
    return token.str();
}

bool AuthService::verifyPassword(const std::string& password, const std::string& hash) {
    // Simple password verification - in production, use bcrypt
    return password == hash;
}

std::string AuthService::hashPassword(const std::string& password) {
    // Simple password hashing - in production, use bcrypt
    return password; // For demo purposes, we're storing plain text
}

} // namespace TaskManager
