const mongoose = require("mongoose");

async function connectDB({
  mongooseClient = mongoose,
  uri = process.env.MONGODB_URI,
} = {}) {
  if (!uri || !uri.trim()) {
    throw new Error("MONGODB_URI is not configured");
  }

  if (mongooseClient.connection?.readyState === 1) {
    return mongooseClient.connection;
  }

  try {
    await mongooseClient.connect(uri, { serverSelectionTimeoutMS: 10000 });
    return mongooseClient.connection;
  } catch {
    throw new Error("MongoDB connection failed");
  }
}

module.exports = { connectDB };

// Complete execution flow
// server.js

// Calls connectDB()

// Check MONGODB_URI

// Is the connection string configured?

// Already connected

// Return existing connection

// Not connected

// Attempt mongoose.connect()

// Connection result

// Success: return connection

// Failure: throw error

// Remember that server.js catches the connection error and continues starting the HTTP server.
// 8. Example dry run
// Suppose your .env contains:
// MONGODB_URI=mongodb://127.0.0.1:27017/ipsakti

// You execute:
// await connectDB();

// Assume MongoDB is running and the initial connection state is 0.
// Step	Operation	Result
// 1	Read URI	URI exists
// 2	Check readyState	0, not connected
// 3	Call mongoose.connect()	Connection attempt
// 4	Wait using await	Waits for result
// 5	Connection succeeds	Returns connection

// If MongoDB is unavailable, the function throws MongoDB connection failed, and server.js catches it.
// 9. One important limitation to understand
// Your current implementation allows the backend to start even if MongoDB is unavailable.

// However, this does not mean all backend functionality will work.

// For example:
// - Authentication may fail if user records cannot be accessed.
// - Chat history may fail if it requires database operations.
// - Database-dependent queries may fail.
// The actual behaviour depends on how the route and service files handle database errors.
