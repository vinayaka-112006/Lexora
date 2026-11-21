const path = require("node:path");
const fs = require("node:fs");
const express = require("express");
const cors = require("cors");
const dotenv = require("dotenv");
const { createQueryRouter } = require("./routes/query");
const { createAuthRouter } = require("./routes/auth");
const { createChatsRouter } = require("./routes/chats");
const { createNewsRouter } = require("./routes/news");
const { createAuthMiddleware } = require("./middleware/auth");
const { connectDB } = require("./config/db");

dotenv.config({ path: path.resolve(__dirname, "../.env") });
if (!process.env.TAVILY_API_KEY) {
  try {
    const rootEnv = dotenv.parse(
      fs.readFileSync(path.resolve(__dirname, "../../.env")),
    );
    if (rootEnv.TAVILY_API_KEY)
      process.env.TAVILY_API_KEY = rootEnv.TAVILY_API_KEY;
  } catch {
    // Root .env is optional; the news route reports missing Tavily configuration safely.
  }
}

function createApp(options = {}) {
  const app = express();
  const frontendOrigins = process.env.FRONTEND_ORIGIN
    ? process.env.FRONTEND_ORIGIN.split(",")
        .map((origin) => origin.trim())
        .filter(Boolean)
    : ["http://localhost:5173", "http://127.0.0.1:5173"];
  const allowedFrontendOrigins = frontendOrigins.filter(
    (origin) => origin !== "*",
  );
  app.use(cors({ origin: allowedFrontendOrigins, credentials: true }));
  app.use(express.json({ limit: "1mb" }));
  const queryAuthMiddleware =
    options.queryAuthMiddleware ||
    createAuthMiddleware(options.queryAuthOptions);
  app.use(
    "/api/auth",
    createAuthRouter({
      ...options.authOptions,
      authMiddleware:
        options.authOptions?.authMiddleware || queryAuthMiddleware,
    }),
  );
  app.use(
    "/api/chats",
    createChatsRouter({ ...options, authMiddleware: queryAuthMiddleware }),
  );
  app.use(
    "/api/news",
    createNewsRouter({
      authMiddleware: queryAuthMiddleware,
      search: options.newsSearch,
    }),
  );
  app.use(
    "/api",
    createQueryRouter({ ...options, authMiddleware: queryAuthMiddleware }),
  );

  app.use((error, req, res, next) => {
    if (error?.type === "entity.parse.failed") {
      return res.status(400).json({ error: "Malformed JSON request" });
    }
    if (error?.type === "entity.too.large") {
      return res.status(413).json({ error: "Request body is too large" });
    }
    return next(error);
  });

  return app;
}

async function startServer({
  connectDatabase = connectDB,
  port = Number(process.env.PORT) || 3000,
} = {}) {
  try {
    await connectDatabase();
  } catch {
    console.error(
      "MongoDB connection unavailable; continuing without database access.",
    );
  }

  const server = createApp().listen(port, () => {
    console.log(`Backend listening on port ${server.address().port}`);
  });
  return server;
}

if (require.main === module) {
  startServer();
}

module.exports = { createApp, startServer };

// Complete execution flow
// Let's put everything together.
// 1. Node.js executes server.js

//    Imports modules and loads environment configuration.
// 2. require.main === module

//    Checks whether the file was executed directly.
// 3. startServer()

//    Attempts MongoDB connection.
// 4. createApp()

//    Creates Express and registers CORS, JSON parsing, authentication middleware and routers.
// 5. .listen(port)

//    Starts accepting HTTP requests.
// 6. Incoming API request

//    Passes through middleware and reaches the matching router.
// 7. Router executes its handler

//    Delegates the actual work to the appropriate service or model.

// 14. Important observations from this file
// A few things worth remembering:
// - The backend separates application creation from server startup.
// - It uses dependency injection to make testing easier.
// - Authentication middleware is shared across several routers.
// - MongoDB failure does not prevent the HTTP server from starting.
// - API route definitions are kept outside server.js.
// - The error middleware handles malformed and oversized JSON requests.
// One subtle point: the require() statements execute before dotenv.config(). If any imported module reads environment variables immediately during import, it may not see the values loaded from .env. Whether that matters depends on the implementation of those imported modules.
