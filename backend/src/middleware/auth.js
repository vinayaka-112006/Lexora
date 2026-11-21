const { verifyAccessToken } = require("../utils/auth");

function getCookieValue(req, name) {
  const header = req.headers?.cookie;
  if (typeof header !== "string") return null;
  for (const part of header.split(";")) {
    const separator = part.indexOf("=");
    if (separator < 0 || part.slice(0, separator).trim() !== name) continue;
    try {
      return decodeURIComponent(part.slice(separator + 1).trim()) || null;
    } catch {
      return null;
    }
  }
  return null;
}

function createAuthMiddleware({ verifyToken = verifyAccessToken } = {}) {
  return function authenticate(req, res, next) {
    const token = getCookieValue(req, "access_token");
    if (!token)
      return res.status(401).json({ error: "Authentication required." });

    let userId;
    try {
      const decoded = verifyToken(token);
      if (!decoded || typeof decoded.sub !== "string" || !decoded.sub.trim()) {
        return res.status(401).json({ error: "Authentication required." });
      }
      userId = decoded.sub;
    } catch {
      return res.status(401).json({ error: "Authentication required." });
    }

    req.user = { id: userId };
    return next();
  };
}

module.exports = { createAuthMiddleware, getCookieValue };

// Complete authentication flow
// Let's visualize what happens when a user sends a request.
// Frontend sends API request

// Contains access_token cookie

// getCookieValue()

// Extract access_token

// verifyToken(token)

// Verify and decode token

// Failure
// 401

// Reject request

// Success
// Set req.user

// Attach user ID

// next()

// Continue to route handler

// 13. Important observations about your implementation
// A few details worth remembering:
// 1. Your middleware reads the token from a cookie named access_token.
// 2. It does not look for a token in the Authorization: Bearer header.
// 3. It verifies the token before trusting the user ID.
// 4. It stores the authenticated user's ID in req.user.id.
// 5. It returns the same generic 401 response for missing, invalid and expired tokens.
// 6. It uses dependency injection to make authentication easier to test.
// One important security distinction: this middleware verifies the token, but it does not itself configure cookie properties such as HttpOnly, Secure or SameSite. Those should be examined where your application creates the authentication cookie.
