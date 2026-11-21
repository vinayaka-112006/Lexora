const express = require("express");
const { createAuthMiddleware } = require("../middleware/auth");
const { searchTavily } = require("../services/tavilyService");

const MAX_QUERY_LENGTH = 500;

function createNewsRouter({
  authMiddleware = createAuthMiddleware(),
  search = searchTavily,
} = {}) {
  const router = express.Router();

  router.post("/search", authMiddleware, async (req, res) => {
    const input = req.body;
    if (
      !input ||
      typeof input !== "object" ||
      Array.isArray(input) ||
      typeof input.query !== "string" ||
      !input.query.trim()
    ) {
      return res.status(400).json({
        error: "Enter a non-empty search query.",
        code: "INVALID_QUERY",
      });
    }
    const query = input.query.trim();
    if (query.length > MAX_QUERY_LENGTH) {
      return res.status(400).json({
        error: `Search query must be ${MAX_QUERY_LENGTH} characters or fewer.`,
        code: "QUERY_TOO_LONG",
      });
    }

    try {
      const result = await search(query);
      return res.json(result);
    } catch (error) {
      if (error?.code === "TAVILY_NOT_CONFIGURED") {
        return res.status(503).json({
          error: "News search is not configured on the server.",
          code: "TAVILY_NOT_CONFIGURED",
        });
      }
      if (
        error?.name === "TimeoutError" ||
        error?.name === "AbortError" ||
        error?.code === "ETIMEDOUT"
      ) {
        return res
          .status(504)
          .json({ error: "News search timed out.", code: "TAVILY_TIMEOUT" });
      }
      return res.status(503).json({
        error: "Current information is temporarily unavailable.",
        code: "TAVILY_UNAVAILABLE",
      });
    }
  });

  return router;
}

module.exports = { createNewsRouter, MAX_QUERY_LENGTH };

// Complete dry run
// Suppose the logged-in user searches:

// Latest Ayurveda regulatory developments in India
// Step	What happens
// 1	React sends POST /api/news/search
// 2	Authentication middleware verifies the user
// 3	Express validates the request body
// 4	Query is trimmed
// 5	Length is checked against 500 characters
// 6	searchTavily(query) is called
// 7	Tavily returns search results
// 8	Express sends the results to React

// If Tavily fails, the route returns an appropriate error instead.
// What to remember
// You now have three distinct backend route responsibilities:
// File	Responsibility
// auth.js	Registration, login, logout and session restoration
// query.js	Sends legal questions to the Python RAG service
// chats.js	Retrieves saved conversations
// news.js	Searches the web for current information

// One important architectural distinction: Your legal RAG pipeline and Tavily news search are separate services. The code here does not combine Tavily results with legal PDF retrieval.
