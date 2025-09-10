#pragma once

#include "common.h"
#include <sqlite3.h>
#include <memory>
#include <vector>

namespace TaskManager {

class Database {
public:
    Database(const std::string& db_path);
    ~Database();

    bool initialize();
    void close();

    // User operations
    bool createUser(const User& user);
    std::optional<User> getUserByUsername(const std::string& username);
    std::optional<User> getUserById(int id);
    std::vector<User> getAllUsers();
    std::vector<User> getUsersByManager(int manager_id);
    bool updateUser(const User& user);
    bool deleteUser(int id);

    // Task operations
    bool createTask(const Task& task);
    std::optional<Task> getTaskById(int id);
    std::vector<Task> getAllTasks();
    std::vector<Task> getTasksByUser(int user_id);
    std::vector<Task> getTasksByManager(int manager_id);
    bool updateTask(const Task& task);
    bool deleteTask(int id);

    // Task history operations
    bool addTaskHistory(const TaskHistory& history);
    std::vector<TaskHistory> getTaskHistory(int task_id);

    // Task comment operations
    bool addTaskComment(const TaskComment& comment);
    std::vector<TaskComment> getTaskComments(int task_id);

private:
    std::string db_path_;
    sqlite3* db_;
    bool is_connected_;

    bool executeQuery(const std::string& query);
    bool createTables();
    void seedDefaultData();
};

} // namespace TaskManager
