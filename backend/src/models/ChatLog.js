const mongoose = require('mongoose');

const chatLogSchema = new mongoose.Schema({
  userId: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'User',
    required: true,
  },
  query: {
    type: String,
    required: true,
  },
  jurisdiction: String,
  answer: {
    type: String,
    required: true,
  },
  decision: {
    type: String,
    required: true,
  },
  confidence: Number,
  citations: {
    type: [mongoose.Schema.Types.Mixed],
    default: [],
  },
  abstentionReason: String,
}, {
  timestamps: true,
  autoIndex: false,
});

module.exports = mongoose.models.ChatLog || mongoose.model('ChatLog', chatLogSchema);
