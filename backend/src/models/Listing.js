import mongoose from 'mongoose';

/**
 * A farmer's produce listing (Section 6.3, "Direct Farmer-Buyer Marketplace").
 *
 * This is the transactional layer the report identifies as the missing half of
 * the value chain: the intelligence platform tells a farmer what their crop is
 * worth and who is buying, but stops short of letting them act on it.
 *
 * `askPricePerQuintal` is what the farmer wants; `mandiReferencePrice` records
 * what the government data said at the moment of listing. Keeping both means a
 * buyer can see the ask in context, and neither side has to take the other's
 * word for the prevailing rate.
 */
const listingSchema = new mongoose.Schema(
  {
    farmer: { type: mongoose.Schema.Types.ObjectId, ref: 'User', required: true, index: true },
    crop: { type: String, required: true, trim: true, index: true },
    variety: { type: String, trim: true, default: 'Other' },
    grade: { type: String, enum: ['FAQ', 'Premium', 'Standard'], default: 'FAQ' },

    quantityQuintal: { type: Number, required: true, min: 0.1 },
    askPricePerQuintal: { type: Number, required: true, min: 1 },
    mandiReferencePrice: { type: Number, min: 0 },

    location: {
      state: { type: String, trim: true, index: true },
      district: { type: String, trim: true, index: true },
      pincode: { type: String, trim: true },
    },

    harvestDate: { type: Date },
    availableUntil: { type: Date },
    notes: { type: String, maxlength: 500 },

    status: {
      type: String,
      enum: ['open', 'reserved', 'sold', 'withdrawn', 'expired'],
      default: 'open',
      index: true,
    },
    acceptedOffer: { type: mongoose.Schema.Types.ObjectId, ref: 'Offer' },
  },
  { timestamps: true },
);

listingSchema.index({ crop: 1, 'location.district': 1, status: 1 });

export const Listing = mongoose.models.Listing || mongoose.model('Listing', listingSchema);
