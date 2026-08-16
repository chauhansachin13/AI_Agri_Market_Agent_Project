import mongoose from 'mongoose';

/** A standing price watch for one crop and location. */
const alertSchema = new mongoose.Schema(
  {
    farmer: { type: mongoose.Schema.Types.ObjectId, ref: 'User', required: true, index: true },
    crop: { type: String, required: true, trim: true },
    state: { type: String, trim: true },
    district: { type: String, trim: true },
    targetPrice: { type: Number, required: true, min: 1 },
    // `above` is the common case: tell me when it is worth selling.
    direction: { type: String, enum: ['above', 'below'], default: 'above' },
    status: { type: String, enum: ['active', 'triggered', 'paused'], default: 'active', index: true },
    notifyBy: { type: String, enum: ['app', 'whatsapp'], default: 'app' },
    lastSeenPrice: Number,
    lastCheckedAt: Date,
    triggeredAt: Date,
  },
  { timestamps: true },
);

export const Alert = mongoose.models.Alert || mongoose.model('Alert', alertSchema);
