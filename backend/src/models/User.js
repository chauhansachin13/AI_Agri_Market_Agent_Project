import mongoose from 'mongoose';

/**
 * Farmer profile (Section 3.3).
 *
 * Phone number is the identity key rather than email — it is what a rural user
 * reliably has, and what the eventual WhatsApp channel would key on too.
 */
const userSchema = new mongoose.Schema(
  {
    name: { type: String, required: true, trim: true, maxlength: 120 },
    phone: {
      type: String,
      required: true,
      unique: true,
      trim: true,
      match: [/^[6-9]\d{9}$/, 'Phone must be a 10-digit Indian mobile number'],
    },
    passwordHash: { type: String, required: true, select: false },
    preferredLanguage: { type: String, enum: ['hi', 'en'], default: 'hi' },
    location: {
      state: { type: String, trim: true },
      district: { type: String, trim: true },
      pincode: { type: String, trim: true, match: [/^[1-9]\d{5}$/, 'Invalid pincode'] },
    },
    crops: [{ type: String, trim: true }],
  },
  { timestamps: true },
);

userSchema.methods.toPublicJSON = function toPublicJSON() {
  return {
    id: this._id.toString(),
    name: this.name,
    phone: this.phone,
    preferredLanguage: this.preferredLanguage,
    location: this.location,
    crops: this.crops,
    createdAt: this.createdAt,
  };
};

export const User = mongoose.models.User || mongoose.model('User', userSchema);
