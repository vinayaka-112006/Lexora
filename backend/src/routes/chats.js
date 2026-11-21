const express = require("express");
const mongoose = require("mongoose");
const ChatLog = require("../models/ChatLog");
const { createAuthMiddleware } = require("../middleware/auth");

const CHAT_FIELDS =
  "_id query jurisdiction answer decision confidence citations abstentionReason createdAt updatedAt";
const CHAT_NOT_FOUND = { error: "Chat not found." };

function presentChat(chat) {
  return {
    id: String(chat._id),
    query: chat.query,
    jurisdiction: chat.jurisdiction,
    answer: chat.answer,
    decision: chat.decision,
    confidence: chat.confidence,
    citations: chat.citations,
    abstentionReason: chat.abstentionReason,
    createdAt: chat.createdAt,
    updatedAt: chat.updatedAt,
  };
}

function createChatsRouter({
  ChatLogModel = ChatLog,
  authMiddleware = createAuthMiddleware(),
} = {}) {
  const router = express.Router();

  router.get("/", authMiddleware, async (req, res) => {
    try {
      const chats = await ChatLogModel.find({ userId: req.user.id })
        .select(CHAT_FIELDS)
        .sort({ createdAt: -1 })
        .limit(50)
        .lean();
      return res.json(chats.map(presentChat));
    } catch {
      return res.status(500).json({ error: "Chat history unavailable." });
    }
  });

  router.get("/:id", authMiddleware, async (req, res) => {
    if (!mongoose.isObjectIdOrHexString(req.params.id)) {
      return res.status(404).json(CHAT_NOT_FOUND);
    }

    try {
      const chat = await ChatLogModel.findOne({
        _id: req.params.id,
        userId: req.user.id,
      })
        .select(CHAT_FIELDS)
        .lean();
      if (!chat) return res.status(404).json(CHAT_NOT_FOUND);
      return res.json(presentChat(chat));
    } catch {
      return res.status(500).json({ error: "Chat history unavailable." });
    }
  });

  return router;
}

module.exports = { createChatsRouter, presentChat };

// Complete execution flow
// Scenario A: User opens chat history
// 1. React sends GET /api/chats.
// 2. Authentication middleware verifies the user.
// 3. MongoDB finds that user's chats.
// 4. Results are sorted newest first and limited to 50.
// 5. Each chat is formatted using presentChat().
// 6. React receives the chat-history array.

// Scenario B: User opens one conversation
// 1. React sends GET /api/chats/:id.
// 2. Authentication middleware verifies the user.
// 3. Backend validates the MongoDB ID.
// 4. MongoDB searches using both chat ID and user ID.
// 5. Backend formats the matching chat and returns it.

// What to remember
// Function	Responsibility
// presentChat()	Formats a chat for the frontend
// createChatsRouter()	Creates the chat router
// GET /	Retrieves the latest 50 chats of a user
// GET /:id	Retrieves one chat belonging to that user

// One important distinction: query.js creates chat history; chats.js reads chat history.

// There are no update or delete endpoints in this file.
