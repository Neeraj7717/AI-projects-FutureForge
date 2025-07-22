#!/bin/bash

# Bash script to install Node.js and start the server
# Run this script with: ./start.sh

echo "=== Social Media API Setup Script ==="

# Function to detect OS
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "linux"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    elif [[ "$OSTYPE" == "cygwin" ]] || [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
        echo "windows"
    else
        echo "unknown"
    fi
}

# Function to install Node.js on Linux
install_nodejs_linux() {
    echo "Installing Node.js on Linux..."
    
    # Check if curl is available
    if ! command -v curl &> /dev/null; then
        echo "Installing curl..."
        sudo apt-get update && sudo apt-get install -y curl
    fi
    
    # Install Node.js using NodeSource repository
    curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
    sudo apt-get install -y nodejs
    
    echo "Node.js installation completed!"
}

# Function to install Node.js on macOS
install_nodejs_macos() {
    echo "Installing Node.js on macOS..."
    
    # Check if Homebrew is installed
    if ! command -v brew &> /dev/null; then
        echo "Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
    
    # Install Node.js using Homebrew
    brew install node
    
    echo "Node.js installation completed!"
}

# Check if Node.js is installed
echo "Checking if Node.js is installed..."
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    echo "Node.js is already installed: $NODE_VERSION"
else
    echo "Node.js is not installed. Installing Node.js..."
    
    OS=$(detect_os)
    case $OS in
        "linux")
            install_nodejs_linux
            ;;
        "macos")
            install_nodejs_macos
            ;;
        "windows")
            echo "Please run the batch script (start.bat) on Windows"
            exit 1
            ;;
        *)
            echo "Unsupported operating system. Please install Node.js manually from https://nodejs.org/"
            exit 1
            ;;
    esac
    
    # Verify installation
    if command -v node &> /dev/null; then
        NODE_VERSION=$(node --version)
        echo "Node.js successfully installed: $NODE_VERSION"
    else
        echo "Failed to install Node.js. Please install it manually from https://nodejs.org/"
        exit 1
    fi
fi

# Check if npm is available
echo "Checking npm..."
if command -v npm &> /dev/null; then
    NPM_VERSION=$(npm --version)
    echo "npm is available: $NPM_VERSION"
else
    echo "npm is not available. Please ensure Node.js is properly installed."
    exit 1
fi

# Install dependencies
echo "Installing project dependencies..."
if npm install; then
    echo "Dependencies installed successfully!"
else
    echo "Failed to install dependencies. Please check your internet connection and try again."
    exit 1
fi

# Start the server
echo "Starting the server..."
echo "Server will be available at: http://localhost:3000"
echo "Press Ctrl+C to stop the server"
echo ""

if npm start; then
    echo "Server started successfully!"
else
    echo "Failed to start the server. Please check the server.js file for any errors."
    exit 1
fi 