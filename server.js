const express = require('express');
const jwt = require('jsonwebtoken');
const bcrypt = require('bcryptjs');
const cors = require('cors');
const helmet = require('helmet');
const morgan = require('morgan');
const { v4: uuidv4 } = require('uuid');

// Initialize Express app
const app = express();
const PORT = process.env.PORT || 3000;
const JWT_SECRET = process.env.JWT_SECRET || 'your-secret-key-change-in-production';

// Middleware
app.use(helmet()); // Security headers
app.use(cors()); // Enable CORS
app.use(morgan('combined')); // Logging
app.use(express.json()); // Parse JSON bodies
app.use(express.urlencoded({ extended: true })); // Parse URL-encoded bodies

// In-memory storage
const users = new Map();
const posts = new Map();
const userLikes = new Map(); // Track which users liked which posts

// Custom logger
const logger = {
  info: (message) => console.log(`[INFO] ${new Date().toISOString()}: ${message}`),
  error: (message) => console.error(`[ERROR] ${new Date().toISOString()}: ${message}`),
  warn: (message) => console.warn(`[WARN] ${new Date().toISOString()}: ${message}`)
};

// JWT Authentication Middleware
const authenticateToken = (req, res, next) => {
  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.split(' ')[1]; // Bearer TOKEN

  if (!token) {
    logger.warn('Authentication failed: No token provided');
    return res.status(401).json({ error: 'Access token required' });
  }

  jwt.verify(token, JWT_SECRET, (err, user) => {
    if (err) {
      logger.warn('Authentication failed: Invalid token');
      return res.status(403).json({ error: 'Invalid or expired token' });
    }
    req.user = user;
    next();
  });
};

// Input validation middleware
const validateUserInput = (req, res, next) => {
  const { username, email, password } = req.body;
  
  if (!username || !email || !password) {
    return res.status(400).json({ error: 'Username, email, and password are required' });
  }
  
  if (password.length < 6) {
    return res.status(400).json({ error: 'Password must be at least 6 characters long' });
  }
  
  if (!email.includes('@')) {
    return res.status(400).json({ error: 'Invalid email format' });
  }
  
  next();
};

const validatePostInput = (req, res, next) => {
  const { title, content } = req.body;
  
  if (!title || !content) {
    return res.status(400).json({ error: 'Title and content are required' });
  }
  
  if (title.length < 1 || content.length < 1) {
    return res.status(400).json({ error: 'Title and content cannot be empty' });
  }
  
  next();
};

// Routes

// 1. User Registration
app.post('/api/users/register', validateUserInput, async (req, res) => {
  try {
    const { username, email, password } = req.body;
    
    // Check if user already exists
    for (let user of users.values()) {
      if (user.username === username || user.email === email) {
        logger.warn(`Registration failed: User already exists - ${username}`);
        return res.status(409).json({ error: 'Username or email already exists' });
      }
    }
    
    // Hash password
    const hashedPassword = await bcrypt.hash(password, 10);
    
    // Create user
    const userId = uuidv4();
    const newUser = {
      id: userId,
      username,
      email,
      password: hashedPassword,
      createdAt: new Date().toISOString()
    };
    
    users.set(userId, newUser);
    
    // Create JWT token
    const token = jwt.sign({ userId, username }, JWT_SECRET, { expiresIn: '24h' });
    
    logger.info(`User registered successfully: ${username}`);
    
    res.status(201).json({
      message: 'User registered successfully',
      user: {
        id: newUser.id,
        username: newUser.username,
        email: newUser.email,
        createdAt: newUser.createdAt
      },
      token
    });
    
  } catch (error) {
    logger.error(`Registration error: ${error.message}`);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// 2. User Login
app.post('/api/users/login', async (req, res) => {
  try {
    const { username, password } = req.body;
    
    if (!username || !password) {
      return res.status(400).json({ error: 'Username and password are required' });
    }
    
    // Find user by username
    let user = null;
    for (let u of users.values()) {
      if (u.username === username) {
        user = u;
        break;
      }
    }
    
    if (!user) {
      logger.warn(`Login failed: User not found - ${username}`);
      return res.status(401).json({ error: 'Invalid credentials' });
    }
    
    // Verify password
    const isValidPassword = await bcrypt.compare(password, user.password);
    
    if (!isValidPassword) {
      logger.warn(`Login failed: Invalid password for user - ${username}`);
      return res.status(401).json({ error: 'Invalid credentials' });
    }
    
    // Create JWT token
    const token = jwt.sign({ userId: user.id, username: user.username }, JWT_SECRET, { expiresIn: '24h' });
    
    logger.info(`User logged in successfully: ${username}`);
    
    res.json({
      message: 'Login successful',
      user: {
        id: user.id,
        username: user.username,
        email: user.email,
        createdAt: user.createdAt
      },
      token
    });
    
  } catch (error) {
    logger.error(`Login error: ${error.message}`);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// 3. Create Post
app.post('/api/posts', authenticateToken, validatePostInput, (req, res) => {
  try {
    const { title, content } = req.body;
    const { userId, username } = req.user;
    
    const postId = uuidv4();
    const newPost = {
      id: postId,
      title,
      content,
      authorId: userId,
      authorUsername: username,
      likes: 0,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    };
    
    posts.set(postId, newPost);
    
    logger.info(`Post created successfully by user: ${username}`);
    
    res.status(201).json({
      message: 'Post created successfully',
      post: newPost
    });
    
  } catch (error) {
    logger.error(`Post creation error: ${error.message}`);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// 4. Like Post
app.post('/api/posts/:postId/like', authenticateToken, (req, res) => {
  try {
    const { postId } = req.params;
    const { userId } = req.user;
    
    const post = posts.get(postId);
    
    if (!post) {
      logger.warn(`Like failed: Post not found - ${postId}`);
      return res.status(404).json({ error: 'Post not found' });
    }
    
    // Check if user already liked the post
    const userLikeKey = `${userId}-${postId}`;
    if (userLikes.has(userLikeKey)) {
      logger.warn(`Like failed: User already liked post - ${postId}`);
      return res.status(400).json({ error: 'Post already liked by this user' });
    }
    
    // Add like
    post.likes += 1;
    userLikes.set(userLikeKey, true);
    posts.set(postId, post);
    
    logger.info(`Post liked successfully: ${postId}`);
    
    res.json({
      message: 'Post liked successfully',
      likes: post.likes
    });
    
  } catch (error) {
    logger.error(`Like error: ${error.message}`);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// 5. Delete Post
app.delete('/api/posts/:postId', authenticateToken, (req, res) => {
  try {
    const { postId } = req.params;
    const { userId } = req.user;
    
    const post = posts.get(postId);
    
    if (!post) {
      logger.warn(`Delete failed: Post not found - ${postId}`);
      return res.status(404).json({ error: 'Post not found' });
    }
    
    // Check if user is the author
    if (post.authorId !== userId) {
      logger.warn(`Delete failed: Unauthorized access to post - ${postId}`);
      return res.status(403).json({ error: 'You can only delete your own posts' });
    }
    
    // Remove post and all its likes
    posts.delete(postId);
    
    // Remove all likes for this post
    for (let [key] of userLikes) {
      if (key.endsWith(`-${postId}`)) {
        userLikes.delete(key);
      }
    }
    
    logger.info(`Post deleted successfully: ${postId}`);
    
    res.json({
      message: 'Post deleted successfully'
    });
    
  } catch (error) {
    logger.error(`Delete error: ${error.message}`);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// 6. List Posts
app.get('/api/posts', (req, res) => {
  try {
    const { page = 1, limit = 10, author } = req.query;
    const pageNum = parseInt(page);
    const limitNum = parseInt(limit);
    
    let allPosts = Array.from(posts.values());
    
    // Filter by author if specified
    if (author) {
      allPosts = allPosts.filter(post => post.authorUsername === author);
    }
    
    // Sort by creation date (newest first)
    allPosts.sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));
    
    // Pagination
    const startIndex = (pageNum - 1) * limitNum;
    const endIndex = startIndex + limitNum;
    const paginatedPosts = allPosts.slice(startIndex, endIndex);
    
    logger.info(`Posts retrieved successfully: ${paginatedPosts.length} posts`);
    
    res.json({
      posts: paginatedPosts,
      pagination: {
        currentPage: pageNum,
        totalPages: Math.ceil(allPosts.length / limitNum),
        totalPosts: allPosts.length,
        postsPerPage: limitNum
      }
    });
    
  } catch (error) {
    logger.error(`Posts retrieval error: ${error.message}`);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// 7. Get Single Post
app.get('/api/posts/:postId', (req, res) => {
  try {
    const { postId } = req.params;
    
    const post = posts.get(postId);
    
    if (!post) {
      logger.warn(`Post retrieval failed: Post not found - ${postId}`);
      return res.status(404).json({ error: 'Post not found' });
    }
    
    logger.info(`Post retrieved successfully: ${postId}`);
    
    res.json({
      post
    });
    
  } catch (error) {
    logger.error(`Post retrieval error: ${error.message}`);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// 8. Get User Profile
app.get('/api/users/profile', authenticateToken, (req, res) => {
  try {
    const { userId } = req.user;
    
    const user = users.get(userId);
    
    if (!user) {
      logger.warn(`Profile retrieval failed: User not found - ${userId}`);
      return res.status(404).json({ error: 'User not found' });
    }
    
    // Get user's posts
    const userPosts = Array.from(posts.values()).filter(post => post.authorId === userId);
    
    logger.info(`Profile retrieved successfully: ${user.username}`);
    
    res.json({
      user: {
        id: user.id,
        username: user.username,
        email: user.email,
        createdAt: user.createdAt,
        postsCount: userPosts.length
      },
      posts: userPosts
    });
    
  } catch (error) {
    logger.error(`Profile retrieval error: ${error.message}`);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Health check endpoint
app.get('/api/health', (req, res) => {
  res.json({
    status: 'OK',
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    usersCount: users.size,
    postsCount: posts.size
  });
});

// 404 handler
app.use('*', (req, res) => {
  logger.warn(`Route not found: ${req.method} ${req.originalUrl}`);
  res.status(404).json({ error: 'Route not found' });
});

// Error handling middleware
app.use((error, req, res, next) => {
  logger.error(`Unhandled error: ${error.message}`);
  res.status(500).json({ error: 'Internal server error' });
});

// Start server
app.listen(PORT, () => {
  logger.info(`Server is running on port ${PORT}`);
  logger.info(`Health check: http://localhost:${PORT}/api/health`);
  logger.info(`API Documentation: See README.md for detailed API documentation`);
});

module.exports = app; 