const express = require("express");
const bcrypt = require("bcryptjs");
const jwt = require("jsonwebtoken");
const User = require("../models/User");
const { createAccessToken, getCookieOptions } = require("../utils/auth");
const { createAuthMiddleware } = require("../middleware/auth");

const INVALID_CREDENTIALS = "Invalid email or password.";

function normalizeEmail(value) {
  return typeof value === "string" ? value.trim().toLowerCase() : "";
}

function validEmail(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

function safeUser(user) {
  return {
    id: String(user._id ?? user.id),
    name: user.name,
    email: user.email,
  };
}

function createAuthRouter({
  UserModel = User,
  bcryptClient = bcrypt,
  jwtClient = jwt,
  jwtSecret = process.env.JWT_SECRET,
  jwtExpiresIn = process.env.JWT_EXPIRES_IN || "7d",
  cookieOptions = getCookieOptions(),
  authMiddleware = createAuthMiddleware(),
} = {}) {
  const router = express.Router();

  router.get("/me", authMiddleware, async (req, res) => {
    try {
      const user = await UserModel.findById(req.user.id);
      if (!user)
        return res.status(401).json({ error: "Authentication required." });
      return res.status(200).json({ user: safeUser(user) });
    } catch {
      return res.status(500).json({ error: "Session could not be restored." });
    }
  });

  router.post("/logout", (req, res) => {
    res.clearCookie("access_token", cookieOptions);
    return res.status(200).json({ message: "Logged out." });
  });

  router.post("/register", async (req, res) => {
    const name = typeof req.body?.name === "string" ? req.body.name.trim() : "";
    const email = normalizeEmail(req.body?.email);
    const password = req.body?.password;

    if (!name) return res.status(400).json({ error: "Name is required." });
    if (!validEmail(email))
      return res.status(400).json({ error: "A valid email is required." });
    if (typeof password !== "string" || password.length < 8) {
      return res
        .status(400)
        .json({ error: "Password must be at least 8 characters." });
    }

    try {
      if (await UserModel.findOne({ email })) {
        return res
          .status(409)
          .json({ error: "An account with this email already exists." });
      }
      const passwordHash = await bcryptClient.hash(password, 12);
      const user = await UserModel.create({ name, email, passwordHash });
      return res.status(201).json({ user: safeUser(user) });
    } catch (error) {
      if (error?.code === 11000) {
        return res
          .status(409)
          .json({ error: "An account with this email already exists." });
      }
      return res.status(500).json({ error: "Registration is unavailable." });
    }
  });

  router.post("/login", async (req, res) => {
    const email = normalizeEmail(req.body?.email);
    const password = req.body?.password;
    if (!validEmail(email) || typeof password !== "string" || !password) {
      return res
        .status(400)
        .json({ error: "A valid email and password are required." });
    }

    let user;
    try {
      user = await UserModel.findOne({ email });
      if (!user || !(await bcryptClient.compare(password, user.passwordHash))) {
        return res.status(401).json({ error: INVALID_CREDENTIALS });
      }
    } catch {
      return res.status(500).json({ error: "Login is unavailable." });
    }

    if (!jwtSecret)
      return res
        .status(500)
        .json({ error: "Authentication is not configured." });
    try {
      const token = createAccessToken(user._id ?? user.id, {
        secret: jwtSecret,
        expiresIn: jwtExpiresIn,
        jwtClient,
      });
      res.cookie("access_token", token, cookieOptions);
      return res.status(200).json({ user: safeUser(user) });
    } catch {
      return res.status(500).json({ error: "Login is unavailable." });
    }
  });

  return router;
}

module.exports = { createAuthRouter, normalizeEmail, validEmail };

// Complete authentication lifecycle
// Now let's connect everything we have studied.
// A. Registration
// 1. Frontend sends name, email and password.
// 2. Normalize and validate input.
// 3. Check whether the email already exists.
// 4. Hash password using bcrypt.
// 5. Save user in MongoDB.
// 6. Return safe user details.

// B. Login
// 1. Frontend sends email and password.
// 2. Find user in MongoDB.
// 3. Compare password with bcrypt hash.
// 4. Generate JWT using createAccessToken().
// 5. Set access_token cookie.
// 6. Return safe user details.

// C. Accessing a protected endpoint
// 1. Browser sends the access token cookie.
// 2. getCookieValue() extracts the token.
// 3. verifyAccessToken() validates it.
// 4. Middleware attaches req.user.id.
// 5. Protected route executes its operation.

// D. Logout
// 1. Frontend calls /api/auth/logout.
// 2. Backend clears the access_token cookie.
// 3. Browser no longer sends that cookie.

// 12. Important things to notice in your implementation
// Observation	Explanation
// Password hashing	bcrypt with cost factor 12
// JWT expiry	Seven days by default
// Authentication storage	HTTP-only cookie
// Duplicate email protection	Database lookup and duplicate-key handling
// Session restoration	/api/auth/me
// Logout	Clears browser cookie
// Registration	Does not automatically log in
// JWT revocation	No server-side blacklist is implemented here

// One additional point: because this uses cookie-based authentication, the frontend must send credentials with cross-origin requests when required. Your server.js already configures CORS with credentials: true. We'll verify the frontend request configuration when we study React.

// Also, SameSite=Lax provides some CSRF protection, but it isn't a complete replacement for a deliberate CSRF strategy in every deployment configuration.
