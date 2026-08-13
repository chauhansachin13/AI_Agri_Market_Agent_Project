import mongoose from 'mongoose';

/**
 * One farmer interaction (Section 3.3).
 *
 * Persisting the detected intent, extracted entities and confidence alongside
 * the answer is what makes the contextual memory across sessions — and the
 * query-pattern analytics described in the report — possible later.
 */
const querySchema = new mongoose.Schema(
  {
    user: { type: mongoose.Schema.Types.ObjectId, ref: 'User', index: true },
    sessionId: { type: String, index: true },
    text: { type: String, required: true, maxlength: 1000 },
    intent: {
      type: String,
      enum: ['price_query', 'buyer_search', 'sell_advice', 'trend_analysis'],
      index: true,
    },
    entities: {
      crop: String,
      state: String,
      district: String,
      quantityValue: Number,
      quantityUnit: String,
    },
    englishAnswer: String,
    hindiAnswer: String,
    recommendation: { type: String, enum: ['SELL', 'WAIT'] },
    confidenceScore: { type: Number, min: 0, max: 1 },
    factCheckStatus: {
      type: String,
      enum: ['verified', 'partially_verified', 'insufficient_evidence'],
    },
    reasoningSteps: [String],
    channel: { type: String, enum: ['web', 'whatsapp'], default: 'web', index: true },
    degraded: { type: Boolean, default: false },
    elapsedMs: Number,
  },
  { timestamps: true },
);

querySchema.index({ createdAt: -1 });

export const Query = mongoose.models.Query || mongoose.model('Query', querySchema);
