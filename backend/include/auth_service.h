#pragma once

#include "common.h"
#include "database.h"
#include <string>
#include <optional>

namespace TaskManager {

class AuthService {
public:
    AuthService(Database& db);
    
    LoginResponse login(const LoginRequest& request);
    bool logout(const std::string& token);
    std::optional<User> validateToken(const std::string& token);
    bool hasPermission(const User& user, const std::string& action, int resource_id = -1);
    
private:
    Database& db_;
    std::string generateToken(const User& user);
    bool verifyPassword(const std::string& password, const std::string& hash);
    std::string hashPassword(const std::string& password);
};

} // namespace TaskManager
