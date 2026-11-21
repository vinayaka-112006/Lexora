const jwt = require("jsonwebtoken");

function getCookieOptions({
  secure = process.env.NODE_ENV === "production",
} = {}) {
  return { httpOnly: true, sameSite: "lax", secure, path: "/" };
}

function createAccessToken(
  userId,
  {
    secret = process.env.JWT_SECRET,
    expiresIn = process.env.JWT_EXPIRES_IN || "7d",
    jwtClient = jwt,
  } = {},
) {
  if (!secret) throw new Error("JWT_SECRET is not configured");
  return jwtClient.sign({ sub: String(userId) }, secret, { expiresIn });
}

function verifyAccessToken(
  token,
  { secret = process.env.JWT_SECRET, jwtClient = jwt } = {},
) {
  if (!secret) throw new Error("JWT_SECRET is not configured");
  return jwtClient.verify(token, secret);
}

module.exports = { createAccessToken, verifyAccessToken, getCookieOptions };

// Let's connect the two files we have studied.
// During login / token generation
// 1. User logs in

//    Authentication route validates the user's credentials.
// 2. createAccessToken(userId)

//    Generates a signed JWT containing the user ID.
// 3. getCookieOptions()

//    Supplies security options for the cookie.
// 4. Cookie is sent to the browser

//    The actual cookie-setting operation happens in the route.

// During a subsequent API request
// 1. Browser sends the cookie

//    Contains the access_token.
// 2. getCookieValue()

//    Extracts the token.
// 3. verifyAccessToken(token)

//    Checks the token and returns its payload.
// 4. req.user = { id: userId }

//    Attaches the authenticated user's ID to the request.
// 5. next()

//    Allows the request to reach the protected route.

// 6. Understanding the relationship between our files
// File	Responsibility
// server.js	Creates the application and registers middleware/routes
// config/db.js	Establishes MongoDB connection
// middleware/auth.js	Extracts and validates authentication for requests
// utils/auth.js	Generates JWTs, verifies JWTs and provides cookie settings

// Notice the separation:
// - utils/auth.js knows how JWTs work.
// - middleware/auth.js uses JWT verification to authenticate incoming requests.
// - server.js registers that middleware with the application.
// This is a good separation of responsibilities.
// 7. One security point to remember
// Your code uses:
// httpOnly: true,
// sameSite: 'lax',
// secure: process.env.NODE_ENV === 'production'

// These are useful cookie security settings. However, cookie security also depends on how the frontend and backend are deployed, their origins, and how cookies are created and cleared.

// We'll inspect that when we reach the authentication routes.
