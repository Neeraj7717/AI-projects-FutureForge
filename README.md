# Social Media API Server

A comprehensive Node.js API server with user management and post functionality, featuring JWT authentication and in-memory storage.

## Features

- ✅ User registration and login
- ✅ JWT-based authentication
- ✅ Post creation, listing, and deletion
- ✅ Post liking functionality
- ✅ In-memory storage (no database required)
- ✅ Comprehensive logging
- ✅ Input validation and error handling
- ✅ Security headers and CORS support
- ✅ Pagination for post listing
- ✅ User profile management

## Prerequisites

- Node.js (version 14 or higher)
- npm (comes with Node.js)

## Project Structure

```
task_0.1/
├── server.js                          # Main server file
├── package.json                       # Project dependencies and scripts
├── package-lock.json                  # Locked dependency versions
├── README.md                          # This documentation file
├── start.bat                          # Windows startup script
├── start.sh                           # Unix/Linux/macOS startup script
└── Social_Media_API.postman_collection.json  # Postman collection for testing
```

## Files Description

- **`server.js`**: Main Express.js server with all API endpoints
- **`package.json`**: Project configuration and dependencies
- **`start.bat`**: Windows batch script for easy server startup
- **`start.sh`**: Unix shell script for easy server startup
- **`Social_Media_API.postman_collection.json`**: Ready-to-use Postman collection for API testing

## Quick Start

### Option 1: Using Shell Scripts (Recommended)

#### Windows Users
```bash
# Double-click start.bat or run in Command Prompt
start.bat

# Or in PowerShell
.\start.bat
```

#### Unix-like Systems (Linux/macOS)
```bash
# Make the script executable (first time only)
chmod +x start.sh

# Run the script
./start.sh
```

The shell scripts will automatically:
- ✅ Check if Node.js is installed
- ✅ Install Node.js if needed (using appropriate package manager)
- ✅ Install project dependencies
- ✅ Start the server

### Shell Script Features

Both `start.bat` and `start.sh` include:
- 🚀 **One-click startup** - No manual setup required
- 🔍 **Smart dependency checking** - Only installs if needed
- 📁 **Working directory validation** - Ensures you're in the right folder
- ⏰ **Timestamp logging** - Shows when the server started
- 🌐 **Server information** - Displays URLs and endpoints
- ❌ **Error handling** - Clear error messages with helpful tips
- 📝 **Visual feedback** - Emojis and status indicators for better UX

### Option 2: Manual Installation

1. **Clone or download the project files**
   ```bash
   # If you have the files locally, navigate to the project directory
   cd task_0.1
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Start the server**
   ```bash
   # For production
   npm start
   
   # For development (with auto-restart)
   npm run dev
   ```

The server will start on `http://localhost:3000` by default.

## Environment Variables

You can customize the server configuration using environment variables:

- `PORT`: Server port (default: 3000)
- `JWT_SECRET`: Secret key for JWT tokens (default: 'your-secret-key-change-in-production')

Example:
```bash
PORT=4000 JWT_SECRET=my-super-secret-key npm start
```

## API Documentation

### Base URL
```
http://localhost:3000/api
```

### Authentication

Most endpoints require JWT authentication. Include the token in the Authorization header:
```
Authorization: Bearer <your-jwt-token>
```

### Endpoints

#### 1. User Registration
**POST** `/users/register`

Create a new user account.

**Request Body:**
```json
{
  "username": "john_doe",
  "email": "john@example.com",
  "password": "password123"
}
```

**Response:**
```json
{
  "message": "User registered successfully",
  "user": {
    "id": "uuid",
    "username": "john_doe",
    "email": "john@example.com",
    "createdAt": "2024-01-01T00:00:00.000Z"
  },
  "token": "jwt-token-here"
}
```

#### 2. User Login
**POST** `/users/login`

Authenticate user and get JWT token.

**Request Body:**
```json
{
  "username": "john_doe",
  "password": "password123"
}
```

**Response:**
```json
{
  "message": "Login successful",
  "user": {
    "id": "uuid",
    "username": "john_doe",
    "email": "john@example.com",
    "createdAt": "2024-01-01T00:00:00.000Z"
  },
  "token": "jwt-token-here"
}
```

#### 3. Create Post
**POST** `/posts` *(Requires Authentication)*

Create a new post.

**Request Body:**
```json
{
  "title": "My First Post",
  "content": "This is the content of my first post."
}
```

**Response:**
```json
{
  "message": "Post created successfully",
  "post": {
    "id": "uuid",
    "title": "My First Post",
    "content": "This is the content of my first post.",
    "authorId": "user-uuid",
    "authorUsername": "john_doe",
    "likes": 0,
    "createdAt": "2024-01-01T00:00:00.000Z",
    "updatedAt": "2024-01-01T00:00:00.000Z"
  }
}
```

#### 4. Like Post
**POST** `/posts/:postId/like` *(Requires Authentication)*

Like a specific post.

**Response:**
```json
{
  "message": "Post liked successfully",
  "likes": 1
}
```

#### 5. Delete Post
**DELETE** `/posts/:postId` *(Requires Authentication)*

Delete a post (only the author can delete their own posts).

**Response:**
```json
{
  "message": "Post deleted successfully"
}
```

#### 6. List Posts
**GET** `/posts`

Get all posts with optional filtering and pagination.

**Query Parameters:**
- `page`: Page number (default: 1)
- `limit`: Posts per page (default: 10)
- `author`: Filter by author username

**Example:**
```
GET /posts?page=1&limit=5&author=john_doe
```

**Response:**
```json
{
  "posts": [
    {
      "id": "uuid",
      "title": "My First Post",
      "content": "This is the content of my first post.",
      "authorId": "user-uuid",
      "authorUsername": "john_doe",
      "likes": 1,
      "createdAt": "2024-01-01T00:00:00.000Z",
      "updatedAt": "2024-01-01T00:00:00.000Z"
    }
  ],
  "pagination": {
    "currentPage": 1,
    "totalPages": 1,
    "totalPosts": 1,
    "postsPerPage": 5
  }
}
```

#### 7. Get Single Post
**GET** `/posts/:postId`

Get a specific post by ID.

**Response:**
```json
{
  "post": {
    "id": "uuid",
    "title": "My First Post",
    "content": "This is the content of my first post.",
    "authorId": "user-uuid",
    "authorUsername": "john_doe",
    "likes": 1,
    "createdAt": "2024-01-01T00:00:00.000Z",
    "updatedAt": "2024-01-01T00:00:00.000Z"
  }
}
```

#### 8. Get User Profile
**GET** `/users/profile` *(Requires Authentication)*

Get the authenticated user's profile and posts.

**Response:**
```json
{
  "user": {
    "id": "uuid",
    "username": "john_doe",
    "email": "john@example.com",
    "createdAt": "2024-01-01T00:00:00.000Z",
    "postsCount": 1
  },
  "posts": [
    {
      "id": "uuid",
      "title": "My First Post",
      "content": "This is the content of my first post.",
      "authorId": "user-uuid",
      "authorUsername": "john_doe",
      "likes": 1,
      "createdAt": "2024-01-01T00:00:00.000Z",
      "updatedAt": "2024-01-01T00:00:00.000Z"
    }
  ]
}
```

#### 9. Health Check
**GET** `/health`

Check server status and statistics.

**Response:**
```json
{
  "status": "OK",
  "timestamp": "2024-01-01T00:00:00.000Z",
  "uptime": 123.456,
  "usersCount": 5,
  "postsCount": 10
}
```

## Error Responses

All endpoints return consistent error responses:

```json
{
  "error": "Error message description"
}
```

Common HTTP status codes:
- `200`: Success
- `201`: Created
- `400`: Bad Request (validation errors)
- `401`: Unauthorized (authentication required)
- `403`: Forbidden (insufficient permissions)
- `404`: Not Found
- `409`: Conflict (resource already exists)
- `500`: Internal Server Error

## Usage Examples

### Using cURL

1. **Register a new user:**
```bash
curl -X POST http://localhost:3000/api/users/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "john_doe",
    "email": "john@example.com",
    "password": "password123"
  }'
```

2. **Login:**
```bash
curl -X POST http://localhost:3000/api/users/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "john_doe",
    "password": "password123"
  }'
```

3. **Create a post (with authentication):**
```bash
curl -X POST http://localhost:3000/api/posts \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "title": "My First Post",
    "content": "This is the content of my first post."
  }'
```

4. **Get all posts:**
```bash
curl -X GET http://localhost:3000/api/posts
```

### Using JavaScript/Fetch

```javascript
// Register user
const registerResponse = await fetch('http://localhost:3000/api/users/register', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    username: 'john_doe',
    email: 'john@example.com',
    password: 'password123'
  })
});

const { token } = await registerResponse.json();

// Create post with authentication
const postResponse = await fetch('http://localhost:3000/api/posts', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`
  },
  body: JSON.stringify({
    title: 'My First Post',
    content: 'This is the content of my first post.'
  })
});
```

## Security Features

- **JWT Authentication**: Secure token-based authentication
- **Password Hashing**: Passwords are hashed using bcrypt
- **Input Validation**: Comprehensive validation for all inputs
- **Security Headers**: Helmet.js for security headers
- **CORS Support**: Configurable Cross-Origin Resource Sharing
- **Error Handling**: Secure error responses without exposing sensitive information

## Logging

The server includes comprehensive logging:
- **INFO**: Successful operations
- **WARN**: Authentication failures, validation errors
- **ERROR**: Server errors and exceptions

Logs include timestamps and relevant context information.

## Data Storage

This API uses in-memory storage (JavaScript Maps) for:
- Users
- Posts
- User likes

**Note**: Data is lost when the server restarts. For production use, consider implementing a persistent database.

## Testing

The API can be tested using:
- Postman (see Postman collection below)
- cURL commands
- Any HTTP client
- Browser developer tools

## Troubleshooting

### Common Issues

1. **Port already in use:**
   ```bash
   # Change port using environment variable
   PORT=4000 npm start
   ```

2. **JWT token expired:**
   - Re-login to get a new token
   - Tokens expire after 24 hours

3. **CORS errors:**
   - The server includes CORS middleware
   - Ensure you're making requests from an allowed origin

4. **Validation errors:**
   - Check that all required fields are provided
   - Ensure password is at least 6 characters
   - Verify email format includes '@'

### Shell Script Troubleshooting

1. **Windows: Script not running**
   - Right-click `start.bat` → "Run as administrator"
   - Or run in Command Prompt: `start.bat`
   - Or run in PowerShell: `.\start.bat`

2. **Unix/Linux: Permission denied**
   ```bash
   chmod +x start.sh
   ./start.sh
   ```

3. **Node.js installation fails**
   - Windows: Install manually from https://nodejs.org/
   - Linux: `sudo apt-get install nodejs npm` (Ubuntu/Debian)
   - macOS: `brew install node` (requires Homebrew)

4. **Dependencies fail to install**
   - Check internet connection
   - Clear npm cache: `npm cache clean --force`
   - Delete `node_modules` folder and run script again

### Server Logs

Monitor server logs for debugging:
```bash
npm start
```

The server will log all requests, errors, and important events to the console.

## API Limitations

- In-memory storage (data lost on restart)
- No image upload support
- No real-time features
- No user roles or permissions beyond post ownership
- No password reset functionality

## Future Enhancements

Potential improvements for production use:
- Database integration (MongoDB, PostgreSQL)
- File upload support
- Real-time notifications
- User roles and permissions
- Password reset functionality
- Rate limiting
- API versioning
- Comprehensive testing suite

## License

MIT License - feel free to use and modify as needed. 