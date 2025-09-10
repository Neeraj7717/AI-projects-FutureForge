#include "common.h"
#include <map>

namespace TaskManager {

std::string roleToString(UserRole role) {
    static const std::map<UserRole, std::string> roleMap = {
        {UserRole::SUPER_USER, "Super User"},
        {UserRole::MANAGER, "Manager"},
        {UserRole::EMPLOYEE, "Employee"}
    };
    return roleMap.at(role);
}

UserRole stringToRole(const std::string& role) {
    static const std::map<std::string, UserRole> roleMap = {
        {"Super User", UserRole::SUPER_USER},
        {"Manager", UserRole::MANAGER},
        {"Employee", UserRole::EMPLOYEE}
    };
    return roleMap.at(role);
}

std::string priorityToString(TaskPriority priority) {
    static const std::map<TaskPriority, std::string> priorityMap = {
        {TaskPriority::LOW, "Low"},
        {TaskPriority::MEDIUM, "Medium"},
        {TaskPriority::HIGH, "High"},
        {TaskPriority::URGENT, "Urgent"}
    };
    return priorityMap.at(priority);
}

TaskPriority stringToPriority(const std::string& priority) {
    static const std::map<std::string, TaskPriority> priorityMap = {
        {"Low", TaskPriority::LOW},
        {"Medium", TaskPriority::MEDIUM},
        {"High", TaskPriority::HIGH},
        {"Urgent", TaskPriority::URGENT}
    };
    return priorityMap.at(priority);
}

std::string statusToString(TaskStatus status) {
    static const std::map<TaskStatus, std::string> statusMap = {
        {TaskStatus::PENDING, "Pending"},
        {TaskStatus::IN_PROGRESS, "In Progress"},
        {TaskStatus::COMPLETED, "Completed"},
        {TaskStatus::CANCELLED, "Cancelled"}
    };
    return statusMap.at(status);
}

TaskStatus stringToStatus(const std::string& status) {
    static const std::map<std::string, TaskStatus> statusMap = {
        {"Pending", TaskStatus::PENDING},
        {"In Progress", TaskStatus::IN_PROGRESS},
        {"Completed", TaskStatus::COMPLETED},
        {"Cancelled", TaskStatus::CANCELLED}
    };
    return statusMap.at(status);
}

} // namespace TaskManager
