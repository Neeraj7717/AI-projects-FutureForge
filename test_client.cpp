#include <iostream>
#include <cpprest/http_client.h>
#include <cpprest/json.h>
#include <thread>
#include <chrono>

using namespace web;
using namespace web::http;
using namespace web::http::client;

void testAPI() {
    http_client client("http://localhost:8080");
    
    try {
        // Test login
        std::cout << "Testing login..." << std::endl;
        
        json::value login_data;
        login_data["username"] = json::value::string("admin");
        login_data["password"] = json::value::string("admin123");
        
        http_request login_request(methods::POST);
        login_request.set_request_uri("/auth/login");
        login_request.set_body(login_data);
        login_request.headers().add("Content-Type", "application/json");
        
        auto login_response = client.request(login_request).get();
        auto login_json = login_response.extract_json().get();
        
        if (login_json["success"].as_bool()) {
            std::cout << "Login successful!" << std::endl;
            std::string token = login_json["token"].as_string();
            std::cout << "Token: " << token << std::endl;
            
            // Test getting tasks
            std::cout << "\nTesting get tasks..." << std::endl;
            
            http_request tasks_request(methods::GET);
            tasks_request.set_request_uri("/tasks");
            tasks_request.headers().add("Authorization", "Bearer " + token);
            
            auto tasks_response = client.request(tasks_request).get();
            auto tasks_json = tasks_response.extract_json().get();
            
            if (tasks_json["success"].as_bool()) {
                std::cout << "Tasks retrieved successfully!" << std::endl;
                auto tasks_array = tasks_json["data"].as_array();
                std::cout << "Number of tasks: " << tasks_array.size() << std::endl;
                
                for (const auto& task : tasks_array) {
                    std::cout << "Task: " << task["title"].as_string() 
                              << " (Priority: " << task["priority"].as_string() 
                              << ", Status: " << task["status"].as_string() << ")" << std::endl;
                }
            } else {
                std::cout << "Failed to get tasks: " << tasks_json["message"].as_string() << std::endl;
            }
            
            // Test creating a task
            std::cout << "\nTesting create task..." << std::endl;
            
            json::value new_task;
            new_task["title"] = json::value::string("Test Task from Client");
            new_task["description"] = json::value::string("This is a test task created by the client");
            new_task["priority"] = json::value::string("High");
            new_task["status"] = json::value::string("Pending");
            new_task["assigned_user_id"] = json::value::number(3); // employee1
            new_task["due_date"] = json::value::string("2024-12-31");
            
            http_request create_request(methods::POST);
            create_request.set_request_uri("/tasks");
            create_request.set_body(new_task);
            create_request.headers().add("Authorization", "Bearer " + token);
            create_request.headers().add("Content-Type", "application/json");
            
            auto create_response = client.request(create_request).get();
            auto create_json = create_response.extract_json().get();
            
            if (create_json["success"].as_bool()) {
                std::cout << "Task created successfully!" << std::endl;
            } else {
                std::cout << "Failed to create task: " << create_json["message"].as_string() << std::endl;
            }
            
        } else {
            std::cout << "Login failed: " << login_json["message"].as_string() << std::endl;
        }
        
    } catch (const std::exception& e) {
        std::cout << "Error: " << e.what() << std::endl;
    }
}

int main() {
    std::cout << "Task Manager API Test Client" << std::endl;
    std::cout << "Make sure the server is running on http://localhost:8080" << std::endl;
    std::cout << "Press Enter to start testing..." << std::endl;
    std::cin.get();
    
    testAPI();
    
    std::cout << "\nTest completed. Press Enter to exit..." << std::endl;
    std::cin.get();
    
    return 0;
}
