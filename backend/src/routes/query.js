const express = require("express");
const { randomUUID } = require("node:crypto");
const { performance } = require("node:perf_hooks");
const { createAuthMiddleware } = require("../middleware/auth");
const ChatLog = require("../models/ChatLog");

const DEFAULT_TIMEOUT_MS = 270000;

function isTimeoutError(error) {
  return (
    error?.name === "TimeoutError" ||
    error?.name === "AbortError" ||
    error?.code === "ETIMEDOUT"
  );
}

function configuredRagUrl() {
  const value = process.env.RAG_SERVICE_URL;
  if (!value) return null;
  try {
    const parsed = new URL(value);
    if (!["http:", "https:"].includes(parsed.protocol)) return null;
    return parsed.toString().replace(/\/+$/, "");
  } catch {
    return null;
  }
}

function writeRequestLog(level, event, fields) {
  console[level](JSON.stringify({ service: "node_proxy", event, ...fields }));
}

function createQueryRouter({
  fetchImpl = global.fetch,
  timeoutMs = DEFAULT_TIMEOUT_MS,
  authMiddleware = createAuthMiddleware(),
  ChatLogModel = ChatLog,
} = {}) {
  const router = express.Router();

  router.use((req, res, next) => {
    const requestId = randomUUID();
    const startedAt = performance.now();
    let completed = false;
    req.requestId = requestId;
    res.setHeader("X-Request-ID", requestId);
    writeRequestLog("info", "request_start", {
      request_id: requestId,
      method: req.method,
      route: req.path,
    });
    const logCompletion = (event) => {
      if (completed) return;
      completed = true;
      writeRequestLog("info", event, {
        request_id: requestId,
        http_status: res.statusCode,
        duration_ms: Number((performance.now() - startedAt).toFixed(3)),
      });
    };
    res.once("finish", () => logCompletion("request_complete"));
    res.once("close", () => logCompletion("request_closed"));
    next();
  });

  async function proxy(req, res, path, body, { persistChatLog = false } = {}) {
    const baseUrl = configuredRagUrl();
    if (!baseUrl || typeof fetchImpl !== "function") {
      writeRequestLog("warn", "upstream_failure", {
        request_id: req.requestId,
        reason: "configuration_unavailable",
      });
      return res.status(503).json({ error: "RAG service unavailable" });
    }

    let upstream;
    try {
      upstream = await fetchImpl(`${baseUrl}${path}`, {
        method: body === undefined ? "GET" : "POST",
        headers:
          body === undefined
            ? {
                Accept: "application/json",
                "X-Request-ID": req.requestId,
              }
            : {
                Accept: "application/json",
                "Content-Type": "application/json",
                "X-Request-ID": req.requestId,
              },
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: AbortSignal.timeout(timeoutMs),
      });
    } catch (error) {
      const timedOut = isTimeoutError(error);
      writeRequestLog("warn", "upstream_failure", {
        request_id: req.requestId,
        reason: timedOut ? "timeout" : "unavailable",
      });
      if (timedOut) {
        return res.status(504).json({ error: "RAG service timed out" });
      }
      return res.status(503).json({ error: "RAG service unavailable" });
    }

    if (!upstream.ok) {
      writeRequestLog("warn", "upstream_failure", {
        request_id: req.requestId,
        reason: "http_error",
        upstream_status: upstream.status,
      });
      if (upstream.status === 422 && body !== undefined) {
        return res.status(400).json({ error: "Invalid query request" });
      }
      return res.status(503).json({ error: "RAG service unavailable" });
    }

    let data;
    try {
      data = await upstream.json();
    } catch {
      writeRequestLog("warn", "upstream_failure", {
        request_id: req.requestId,
        reason: "invalid_json",
      });
      return res
        .status(502)
        .json({ error: "Invalid response from RAG service" });
    }
    if (data === null || typeof data !== "object" || Array.isArray(data)) {
      writeRequestLog("warn", "upstream_failure", {
        request_id: req.requestId,
        reason: "invalid_response_shape",
      });
      return res
        .status(502)
        .json({ error: "Invalid response from RAG service" });
    }

    if (
      persistChatLog &&
      typeof data.answer === "string" &&
      typeof data.decision === "string"
    ) {
      const chatLog = {
        userId: req.user.id,
        query: body.query,
        answer: data.answer,
        decision: data.decision,
        citations: Array.isArray(data.citations) ? data.citations : [],
      };
      if (body.jurisdiction !== undefined)
        chatLog.jurisdiction = body.jurisdiction;
      if (
        typeof data.confidence === "number" &&
        Number.isFinite(data.confidence)
      ) {
        chatLog.confidence = data.confidence;
      }
      if (typeof data.abstention_reason === "string") {
        chatLog.abstentionReason = data.abstention_reason;
      }

      try {
        await ChatLogModel.create(chatLog);
      } catch {
        // Persistence must not change the established query response contract.
      }
    }
    return res.status(upstream.status).json(data);
  }

  router.post("/query", authMiddleware, (req, res) => {
    const input = req.body;
    if (!input || typeof input !== "object" || Array.isArray(input)) {
      return res
        .status(400)
        .json({ error: "Request body must be a JSON object" });
    }
    if (typeof input.query !== "string" || !input.query.trim()) {
      return res
        .status(400)
        .json({ error: "query must be a non-empty string" });
    }
    if (
      input.jurisdiction !== undefined &&
      typeof input.jurisdiction !== "string"
    ) {
      return res.status(400).json({ error: "jurisdiction must be a string" });
    }
    if (input.history !== undefined && !Array.isArray(input.history)) {
      return res.status(400).json({ error: "history must be an array" });
    }

    const payload = { query: input.query };
    if (input.jurisdiction !== undefined)
      payload.jurisdiction = input.jurisdiction;
    if (Array.isArray(input.history))
      payload.history = input.history.slice(-10);
    return proxy(req, res, "/query", payload, { persistChatLog: true });
  });

  router.get("/health/rag", (req, res) => proxy(req, res, "/health"));
  return router;
}

module.exports = { createQueryRouter, configuredRagUrl, DEFAULT_TIMEOUT_MS };

// Complete dry run
// Let's imagine a logged-in user asks:
// Can Ashwagandha be patented in India?

// 1. Frontend sends the request

//    POST /api/query
//    {
//      "query": "Can Ashwagandha be patented in India?",
//      "jurisdiction": "India",
//      "history": []
//    }
// 2. Authentication

//    authMiddleware verifies the access token and identifies the user.
// 3. Validation and logging

//    Express checks the question, jurisdiction and history, then assigns a request ID.
// 4. Proxy sends request

//    Express forwards the payload to Python's /query endpoint.
// 5. Python processes the question

//    Your RAG pipeline retrieves legal documents, generates an answer and validates citations.
// 6. Express receives the response

//    It checks the HTTP status, parses JSON and validates the response shape.
// 7. MongoDB persistence

//    Express saves the question, answer, decision, citations and other available fields.
// 8. Frontend receives the answer

//    Express returns the JSON response to React.

// 11. Exports
// module.exports = {
//   createQueryRouter,
//   configuredRagUrl,
//   DEFAULT_TIMEOUT_MS
// };

// This makes three things available to other files:
// - createQueryRouter: Used by server.js to mount the router.
// - configuredRagUrl: Can be reused elsewhere.
// - DEFAULT_TIMEOUT_MS: Can be reused as the default timeout value.

// What you should remember from this file
// There are three major responsibilities:
// Responsibility	Function
// Request tracking	router.use() middleware
// Python communication	proxy()
// Receiving and validating user questions	POST /query

// And one additional responsibility: saving successful RAG responses in MongoDB.

// A few implementation details worth remembering:
// - The query endpoint requires authentication; the RAG health endpoint does not.
// - Only the last 10 conversation-history entries are forwarded.
// - Chat-log saving is best-effort: a database write failure does not prevent the answer from being returned.
// - The Express layer checks basic data types, while the Python service performs the actual RAG processing.
