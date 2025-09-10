#include "database.h"
#include <spdlog/spdlog.h>
#include <sstream>
#include <iomanip>
#include <algorithm>

namespace TaskManager {

Database::Database(const std::string& db_path) : db_path_(db_path), db_(nullptr), is_connected_(false) {
}

Database::~Database() {
    close();
}

bool Database::initialize() {
    int rc = sqlite3_open(db_path_.c_str(), &db_);
    if (rc != SQLITE_OK) {
        spdlog::error("Cannot open database: {}", sqlite3_errmsg(db_));
        return false;
    }

    is_connected_ = true;
    
    if (!createTables()) {
        spdlog::error("Failed to create tables");
        return false;
    }

    seedDefaultData();
    return true;
}

void Database::close() {
    if (db_) {
        sqlite3_close(db_);
        db_ = nullptr;
        is_connected_ = false;
    }
}

bool Database::createTables() {
    std::vector<std::string> queries = {
        R"(
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            manager_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (manager_id) REFERENCES users(id)
        )
        )",
        R"(
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            priority TEXT NOT NULL,
            status TEXT NOT NULL,
            assigned_user_id INTEGER NOT NULL,
            created_by INTEGER NOT NULL,
            due_date TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (assigned_user_id) REFERENCES users(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
        )",
        R"(
        CREATE TABLE IF NOT EXISTS task_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            comment TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        )",
        R"(
        CREATE TABLE IF NOT EXISTS task_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            comment TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        )"
    };

    for (const auto& query : queries) {
        if (!executeQuery(query)) {
            return false;
        }
    }

    return true;
}

void Database::seedDefaultData() {
    // Check if users already exist
    sqlite3_stmt* stmt;
    const char* query = "SELECT COUNT(*) FROM users";
    
    if (sqlite3_prepare_v2(db_, query, -1, &stmt, nullptr) == SQLITE_OK) {
        if (sqlite3_step(stmt) == SQLITE_ROW) {
            int count = sqlite3_column_int(stmt, 0);
            if (count > 0) {
                sqlite3_finalize(stmt);
                return; // Data already exists
            }
        }
    }
    sqlite3_finalize(stmt);

    // Create default users
    std::vector<std::string> defaultUsers = {
        "INSERT INTO users (username, password_hash, role, manager_id) VALUES ('admin', 'admin123', 'Super User', NULL)",
        "INSERT INTO users (username, password_hash, role, manager_id) VALUES ('manager1', 'manager123', 'Manager', 1)",
        "INSERT INTO users (username, password_hash, role, manager_id) VALUES ('employee1', 'emp123', 'Employee', 2)",
        "INSERT INTO users (username, password_hash, role, manager_id) VALUES ('employee2', 'emp123', 'Employee', 2)"
    };

    for (const auto& query : defaultUsers) {
        executeQuery(query);
    }

    // Create sample tasks
    std::vector<std::string> sampleTasks = {
        "INSERT INTO tasks (title, description, priority, status, assigned_user_id, created_by, due_date) VALUES ('Review Code', 'Review the new authentication module', 'High', 'Pending', 3, 2, '2024-01-15')",
        "INSERT INTO tasks (title, description, priority, status, assigned_user_id, created_by, due_date) VALUES ('Update Documentation', 'Update API documentation', 'Medium', 'In Progress', 4, 2, '2024-01-20')",
        "INSERT INTO tasks (title, description, priority, status, assigned_user_id, created_by, due_date) VALUES ('Fix Bug #123', 'Fix the login validation bug', 'Urgent', 'Pending', 3, 1, '2024-01-10')"
    };

    for (const auto& query : sampleTasks) {
        executeQuery(query);
    }
}

bool Database::executeQuery(const std::string& query) {
    char* errMsg = 0;
    int rc = sqlite3_exec(db_, query.c_str(), nullptr, nullptr, &errMsg);
    
    if (rc != SQLITE_OK) {
        spdlog::error("SQL error: {}", errMsg);
        sqlite3_free(errMsg);
        return false;
    }
    
    return true;
}

bool Database::createUser(const User& user) {
    std::stringstream query;
    query << "INSERT INTO users (username, password_hash, role, manager_id) VALUES ('"
          << user.username << "', '" << user.password_hash << "', '"
          << roleToString(user.role) << "', ";
    
    if (user.manager_id.has_value()) {
        query << user.manager_id.value();
    } else {
        query << "NULL";
    }
    query << ")";

    return executeQuery(query.str());
}

std::optional<User> Database::getUserByUsername(const std::string& username) {
    std::string query = "SELECT * FROM users WHERE username = '" + username + "'";
    sqlite3_stmt* stmt;
    
    if (sqlite3_prepare_v2(db_, query.c_str(), -1, &stmt, nullptr) != SQLITE_OK) {
        return std::nullopt;
    }

    if (sqlite3_step(stmt) == SQLITE_ROW) {
        User user;
        user.id = sqlite3_column_int(stmt, 0);
        user.username = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 1));
        user.password_hash = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 2));
        user.role = stringToRole(reinterpret_cast<const char*>(sqlite3_column_text(stmt, 3)));
        
        if (sqlite3_column_type(stmt, 4) != SQLITE_NULL) {
            user.manager_id = sqlite3_column_int(stmt, 4);
        }
        
        user.created_at = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 5));
        user.updated_at = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 6));
        
        sqlite3_finalize(stmt);
        return user;
    }
    
    sqlite3_finalize(stmt);
    return std::nullopt;
}

std::optional<User> Database::getUserById(int id) {
    std::string query = "SELECT * FROM users WHERE id = " + std::to_string(id);
    sqlite3_stmt* stmt;
    
    if (sqlite3_prepare_v2(db_, query.c_str(), -1, &stmt, nullptr) != SQLITE_OK) {
        return std::nullopt;
    }

    if (sqlite3_step(stmt) == SQLITE_ROW) {
        User user;
        user.id = sqlite3_column_int(stmt, 0);
        user.username = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 1));
        user.password_hash = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 2));
        user.role = stringToRole(reinterpret_cast<const char*>(sqlite3_column_text(stmt, 3)));
        
        if (sqlite3_column_type(stmt, 4) != SQLITE_NULL) {
            user.manager_id = sqlite3_column_int(stmt, 4);
        }
        
        user.created_at = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 5));
        user.updated_at = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 6));
        
        sqlite3_finalize(stmt);
        return user;
    }
    
    sqlite3_finalize(stmt);
    return std::nullopt;
}

std::vector<User> Database::getAllUsers() {
    std::vector<User> users;
    std::string query = "SELECT * FROM users ORDER BY username";
    sqlite3_stmt* stmt;
    
    if (sqlite3_prepare_v2(db_, query.c_str(), -1, &stmt, nullptr) != SQLITE_OK) {
        return users;
    }

    while (sqlite3_step(stmt) == SQLITE_ROW) {
        User user;
        user.id = sqlite3_column_int(stmt, 0);
        user.username = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 1));
        user.password_hash = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 2));
        user.role = stringToRole(reinterpret_cast<const char*>(sqlite3_column_text(stmt, 3)));
        
        if (sqlite3_column_type(stmt, 4) != SQLITE_NULL) {
            user.manager_id = sqlite3_column_int(stmt, 4);
        }
        
        user.created_at = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 5));
        user.updated_at = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 6));
        
        users.push_back(user);
    }
    
    sqlite3_finalize(stmt);
    return users;
}

std::vector<User> Database::getUsersByManager(int manager_id) {
    std::vector<User> users;
    std::string query = "SELECT * FROM users WHERE manager_id = " + std::to_string(manager_id) + " ORDER BY username";
    sqlite3_stmt* stmt;
    
    if (sqlite3_prepare_v2(db_, query.c_str(), -1, &stmt, nullptr) != SQLITE_OK) {
        return users;
    }

    while (sqlite3_step(stmt) == SQLITE_ROW) {
        User user;
        user.id = sqlite3_column_int(stmt, 0);
        user.username = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 1));
        user.password_hash = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 2));
        user.role = stringToRole(reinterpret_cast<const char*>(sqlite3_column_text(stmt, 3)));
        
        if (sqlite3_column_type(stmt, 4) != SQLITE_NULL) {
            user.manager_id = sqlite3_column_int(stmt, 4);
        }
        
        user.created_at = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 5));
        user.updated_at = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 6));
        
        users.push_back(user);
    }
    
    sqlite3_finalize(stmt);
    return users;
}

bool Database::createTask(const Task& task) {
    std::stringstream query;
    query << "INSERT INTO tasks (title, description, priority, status, assigned_user_id, created_by, due_date) VALUES ('"
          << task.title << "', '" << task.description << "', '"
          << priorityToString(task.priority) << "', '" << statusToString(task.status) << "', "
          << task.assigned_user_id << ", " << task.created_by << ", '"
          << task.due_date << "')";

    bool success = executeQuery(query.str());
    if (success) {
        // Get the last inserted ID
        sqlite3_stmt* stmt;
        const char* id_query = "SELECT last_insert_rowid()";
        if (sqlite3_prepare_v2(db_, id_query, -1, &stmt, nullptr) == SQLITE_OK) {
            if (sqlite3_step(stmt) == SQLITE_ROW) {
                // In a real implementation, you'd update the task object with the new ID
            }
        }
        sqlite3_finalize(stmt);
    }
    return success;
}

std::vector<Task> Database::getAllTasks() {
    std::vector<Task> tasks;
    std::string query = "SELECT * FROM tasks ORDER BY created_at DESC";
    sqlite3_stmt* stmt;
    
    if (sqlite3_prepare_v2(db_, query.c_str(), -1, &stmt, nullptr) != SQLITE_OK) {
        return tasks;
    }

    while (sqlite3_step(stmt) == SQLITE_ROW) {
        Task task;
        task.id = sqlite3_column_int(stmt, 0);
        task.title = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 1));
        task.description = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 2));
        task.priority = stringToPriority(reinterpret_cast<const char*>(sqlite3_column_text(stmt, 3)));
        task.status = stringToStatus(reinterpret_cast<const char*>(sqlite3_column_text(stmt, 4)));
        task.assigned_user_id = sqlite3_column_int(stmt, 5);
        task.created_by = sqlite3_column_int(stmt, 6);
        task.due_date = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 7));
        task.created_at = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 8));
        task.updated_at = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 9));
        
        tasks.push_back(task);
    }
    
    sqlite3_finalize(stmt);
    return tasks;
}

std::vector<Task> Database::getTasksByUser(int user_id) {
    std::vector<Task> tasks;
    std::string query = "SELECT * FROM tasks WHERE assigned_user_id = " + std::to_string(user_id) + " ORDER BY created_at DESC";
    sqlite3_stmt* stmt;
    
    if (sqlite3_prepare_v2(db_, query.c_str(), -1, &stmt, nullptr) != SQLITE_OK) {
        return tasks;
    }

    while (sqlite3_step(stmt) == SQLITE_ROW) {
        Task task;
        task.id = sqlite3_column_int(stmt, 0);
        task.title = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 1));
        task.description = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 2));
        task.priority = stringToPriority(reinterpret_cast<const char*>(sqlite3_column_text(stmt, 3)));
        task.status = stringToStatus(reinterpret_cast<const char*>(sqlite3_column_text(stmt, 4)));
        task.assigned_user_id = sqlite3_column_int(stmt, 5);
        task.created_by = sqlite3_column_int(stmt, 6);
        task.due_date = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 7));
        task.created_at = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 8));
        task.updated_at = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 9));
        
        tasks.push_back(task);
    }
    
    sqlite3_finalize(stmt);
    return tasks;
}

std::vector<Task> Database::getTasksByManager(int manager_id) {
    std::vector<Task> tasks;
    std::string query = "SELECT t.* FROM tasks t "
                       "JOIN users u ON t.assigned_user_id = u.id "
                       "WHERE u.manager_id = " + std::to_string(manager_id) + " OR t.created_by = " + std::to_string(manager_id) + " "
                       "ORDER BY t.created_at DESC";
    sqlite3_stmt* stmt;
    
    if (sqlite3_prepare_v2(db_, query.c_str(), -1, &stmt, nullptr) != SQLITE_OK) {
        return tasks;
    }

    while (sqlite3_step(stmt) == SQLITE_ROW) {
        Task task;
        task.id = sqlite3_column_int(stmt, 0);
        task.title = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 1));
        task.description = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 2));
        task.priority = stringToPriority(reinterpret_cast<const char*>(sqlite3_column_text(stmt, 3)));
        task.status = stringToStatus(reinterpret_cast<const char*>(sqlite3_column_text(stmt, 4)));
        task.assigned_user_id = sqlite3_column_int(stmt, 5);
        task.created_by = sqlite3_column_int(stmt, 6);
        task.due_date = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 7));
        task.created_at = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 8));
        task.updated_at = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 9));
        
        tasks.push_back(task);
    }
    
    sqlite3_finalize(stmt);
    return tasks;
}

bool Database::updateTask(const Task& task) {
    std::stringstream query;
    query << "UPDATE tasks SET title = '" << task.title 
          << "', description = '" << task.description
          << "', priority = '" << priorityToString(task.priority)
          << "', status = '" << statusToString(task.status)
          << "', assigned_user_id = " << task.assigned_user_id
          << ", due_date = '" << task.due_date
          << "', updated_at = CURRENT_TIMESTAMP WHERE id = " << task.id;

    return executeQuery(query.str());
}

bool Database::deleteTask(int id) {
    std::string query = "DELETE FROM tasks WHERE id = " + std::to_string(id);
    return executeQuery(query);
}

bool Database::addTaskHistory(const TaskHistory& history) {
    std::stringstream query;
    query << "INSERT INTO task_history (task_id, action, user_id, comment) VALUES ("
          << history.task_id << ", '" << history.action << "', " << history.user_id 
          << ", '" << history.comment << "')";

    return executeQuery(query.str());
}

std::vector<TaskHistory> Database::getTaskHistory(int task_id) {
    std::vector<TaskHistory> history;
    std::string query = "SELECT * FROM task_history WHERE task_id = " + std::to_string(task_id) + " ORDER BY created_at DESC";
    sqlite3_stmt* stmt;
    
    if (sqlite3_prepare_v2(db_, query.c_str(), -1, &stmt, nullptr) != SQLITE_OK) {
        return history;
    }

    while (sqlite3_step(stmt) == SQLITE_ROW) {
        TaskHistory h;
        h.id = sqlite3_column_int(stmt, 0);
        h.task_id = sqlite3_column_int(stmt, 1);
        h.action = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 2));
        h.user_id = sqlite3_column_int(stmt, 3);
        h.comment = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 4));
        h.created_at = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 5));
        
        history.push_back(h);
    }
    
    sqlite3_finalize(stmt);
    return history;
}

bool Database::addTaskComment(const TaskComment& comment) {
    std::stringstream query;
    query << "INSERT INTO task_comments (task_id, user_id, comment) VALUES ("
          << comment.task_id << ", " << comment.user_id << ", '" << comment.comment << "')";

    return executeQuery(query.str());
}

std::vector<TaskComment> Database::getTaskComments(int task_id) {
    std::vector<TaskComment> comments;
    std::string query = "SELECT * FROM task_comments WHERE task_id = " + std::to_string(task_id) + " ORDER BY created_at DESC";
    sqlite3_stmt* stmt;
    
    if (sqlite3_prepare_v2(db_, query.c_str(), -1, &stmt, nullptr) != SQLITE_OK) {
        return comments;
    }

    while (sqlite3_step(stmt) == SQLITE_ROW) {
        TaskComment c;
        c.id = sqlite3_column_int(stmt, 0);
        c.task_id = sqlite3_column_int(stmt, 1);
        c.user_id = sqlite3_column_int(stmt, 2);
        c.comment = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 3));
        c.created_at = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 4));
        
        comments.push_back(c);
    }
    
    sqlite3_finalize(stmt);
    return comments;
}

} // namespace TaskManager
