import mongoose from 'mongoose';

/**
 * A buyer's bid against a listing (Section 6.3).
 *
 * Offers are immutable once withdrawn or resolved, so the negotiation history
 * survives. A marketplace that quietly rewrites past bids is one a farmer has
 * no reason to trust.
 */
const offerSchema = new mongoose.Schema(
  {
    listing: { type: mongoose.Schema.Types.ObjectId, ref: 'Listing', required: true, index: true },
    buyer: { type: mongoose.Schema.Types.ObjectId, ref: 'User', required: true, index: true },

    pricePerQuintal: { type: Number, required: true, min: 1 },
    quantityQuintal: { type: Number, required: true, min: 0.1 },
    message: { type: String, maxlength: 500 },
    pickupBy: { type: Date },

    status: {
      type: String,
      enum: ['pending', 'accepted', 'rejected', 'withdrawn'],
      default: 'pending',
      index: true,
    },
    respondedAt: { type: Date },
  },
  { timestamps: true },
);

offerSchema.index({ listing: 1, status: 1 });

export const Offer = mongoose.models.Offer || mongoose.model('Offer', offerSchema);
