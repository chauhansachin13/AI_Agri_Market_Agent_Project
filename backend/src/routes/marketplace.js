import { Router } from 'express';

import { asyncRoute } from '../middleware/errorHandler.js';
import { optionalAuth, requireAuth } from '../middleware/auth.js';
import { fetchMandiPrices } from '../services/aiClient.js';
import {
  createListing,
  createOffer,
  getListing,
  getOffer,
  listListings,
  listOffers,
  rejectOtherOffers,
  updateListing,
  updateOffer,
} from '../store/marketplace.js';

export const marketplaceRouter = Router();

const CLOSED_STATUSES = new Set(['sold', 'withdrawn', 'expired']);

function badRequest(res, message) {
  return res.status(400).json({ error: message });
}

/**
 * The prevailing mandi rate at the moment of listing.
 *
 * Recorded so a buyer sees the ask in context and neither side has to take the
 * other's word for the going rate. A failure here must not block the listing —
 * the reference price is useful, not essential.
 */
async function mandiReference(crop, location) {
  try {
    const records = await fetchMandiPrices({
      crop,
      state: location?.state,
      district: location?.district,
      limit: 20,
    });
    if (!records?.length) return undefined;
    const modal = records.map((r) => r.modal_price).filter((v) => v > 0);
    if (!modal.length) return undefined;
    return Math.round(modal.reduce((a, b) => a + b, 0) / modal.length);
  } catch {
    return undefined;
  }
}

// --- listings ---------------------------------------------------------------

marketplaceRouter.post(
  '/listings',
  requireAuth,
  asyncRoute(async (req, res) => {
    const { crop, quantityQuintal, askPricePerQuintal, variety, grade, location, notes,
      harvestDate, availableUntil } = req.body || {};

    if (!crop || !String(crop).trim()) return badRequest(res, 'crop is required');

    const quantity = Number(quantityQuintal);
    const ask = Number(askPricePerQuintal);
    if (!Number.isFinite(quantity) || quantity <= 0) {
      return badRequest(res, 'quantityQuintal must be a positive number');
    }
    if (!Number.isFinite(ask) || ask <= 0) {
      return badRequest(res, 'askPricePerQuintal must be a positive number');
    }
    if (grade && !['FAQ', 'Premium', 'Standard'].includes(grade)) {
      return badRequest(res, 'grade must be FAQ, Premium or Standard');
    }

    const where = location || req.user.location || {};
    const listing = await createListing({
      farmer: req.user.id,
      crop: String(crop).trim(),
      variety: variety || 'Other',
      grade: grade || 'FAQ',
      quantityQuintal: quantity,
      askPricePerQuintal: ask,
      mandiReferencePrice: await mandiReference(crop, where),
      location: { state: where.state, district: where.district, pincode: where.pincode },
      notes: notes ? String(notes).slice(0, 500) : undefined,
      harvestDate: harvestDate ? new Date(harvestDate) : undefined,
      availableUntil: availableUntil ? new Date(availableUntil) : undefined,
    });

    return res.status(201).json({ listing });
  }),
);

marketplaceRouter.get(
  '/listings',
  optionalAuth,
  asyncRoute(async (req, res) => {
    const limit = Math.min(Number.parseInt(req.query.limit, 10) || 50, 100);
    const listings = await listListings(
      {
        crop: req.query.crop,
        district: req.query.district,
        state: req.query.state,
        status: req.query.status || 'open',
        farmer: req.query.mine === 'true' && req.user ? req.user.id : undefined,
      },
      limit,
    );
    return res.json({ count: listings.length, listings });
  }),
);

marketplaceRouter.get(
  '/listings/:id',
  asyncRoute(async (req, res) => {
    const listing = await getListing(req.params.id);
    if (!listing) return res.status(404).json({ error: 'Listing not found' });
    const offers = await listOffers({ listing: req.params.id });
    return res.json({ listing, offers });
  }),
);

marketplaceRouter.patch(
  '/listings/:id',
  requireAuth,
  asyncRoute(async (req, res) => {
    const listing = await getListing(req.params.id);
    if (!listing) return res.status(404).json({ error: 'Listing not found' });
    if (String(listing.farmer) !== String(req.user.id)) {
      return res.status(403).json({ error: 'Only the farmer who listed it can change it' });
    }
    if (CLOSED_STATUSES.has(listing.status)) {
      return badRequest(res, `A ${listing.status} listing cannot be changed`);
    }

    const updates = {};
    if (req.body?.askPricePerQuintal !== undefined) {
      const ask = Number(req.body.askPricePerQuintal);
      if (!Number.isFinite(ask) || ask <= 0) {
        return badRequest(res, 'askPricePerQuintal must be a positive number');
      }
      updates.askPricePerQuintal = ask;
    }
    if (req.body?.quantityQuintal !== undefined) {
      const quantity = Number(req.body.quantityQuintal);
      if (!Number.isFinite(quantity) || quantity <= 0) {
        return badRequest(res, 'quantityQuintal must be a positive number');
      }
      updates.quantityQuintal = quantity;
    }
    if (req.body?.notes !== undefined) updates.notes = String(req.body.notes).slice(0, 500);
    if (req.body?.status === 'withdrawn') updates.status = 'withdrawn';

    if (Object.keys(updates).length === 0) {
      return badRequest(res, 'No updatable fields supplied');
    }

    return res.json({ listing: await updateListing(req.params.id, updates) });
  }),
);

// --- offers -----------------------------------------------------------------

marketplaceRouter.post(
  '/listings/:id/offers',
  requireAuth,
  asyncRoute(async (req, res) => {
    const listing = await getListing(req.params.id);
    if (!listing) return res.status(404).json({ error: 'Listing not found' });
    if (listing.status !== 'open') {
      return badRequest(res, `This listing is ${listing.status} and is not accepting offers`);
    }
    if (String(listing.farmer) === String(req.user.id)) {
      return badRequest(res, 'You cannot bid on your own listing');
    }

    const price = Number(req.body?.pricePerQuintal);
    if (!Number.isFinite(price) || price <= 0) {
      return badRequest(res, 'pricePerQuintal must be a positive number');
    }

    const quantity = Number(req.body?.quantityQuintal ?? listing.quantityQuintal);
    if (!Number.isFinite(quantity) || quantity <= 0) {
      return badRequest(res, 'quantityQuintal must be a positive number');
    }
    if (quantity > listing.quantityQuintal) {
      return badRequest(res, 'Offer quantity exceeds the quantity listed');
    }

    const offer = await createOffer({
      listing: req.params.id,
      buyer: req.user.id,
      pricePerQuintal: price,
      quantityQuintal: quantity,
      message: req.body?.message ? String(req.body.message).slice(0, 500) : undefined,
      pickupBy: req.body?.pickupBy ? new Date(req.body.pickupBy) : undefined,
    });

    return res.status(201).json({ offer });
  }),
);

marketplaceRouter.post(
  '/offers/:id/accept',
  requireAuth,
  asyncRoute(async (req, res) => {
    const offer = await getOffer(req.params.id);
    if (!offer) return res.status(404).json({ error: 'Offer not found' });

    const listing = await getListing(offer.listing);
    if (!listing) return res.status(404).json({ error: 'Listing not found' });
    if (String(listing.farmer) !== String(req.user.id)) {
      return res.status(403).json({ error: 'Only the farmer who listed it can accept an offer' });
    }
    if (offer.status !== 'pending') {
      return badRequest(res, `This offer is already ${offer.status}`);
    }
    if (listing.status !== 'open') {
      return badRequest(res, `This listing is ${listing.status}`);
    }

    const accepted = await updateOffer(req.params.id, {
      status: 'accepted',
      respondedAt: new Date(),
    });
    // Closing the other bids is part of accepting, not a follow-up step.
    await rejectOtherOffers(listing._id, req.params.id);
    const updated = await updateListing(listing._id, {
      status: 'sold',
      acceptedOffer: req.params.id,
    });

    return res.json({ offer: accepted, listing: updated });
  }),
);

marketplaceRouter.post(
  '/offers/:id/reject',
  requireAuth,
  asyncRoute(async (req, res) => {
    const offer = await getOffer(req.params.id);
    if (!offer) return res.status(404).json({ error: 'Offer not found' });

    const listing = await getListing(offer.listing);
    if (String(listing?.farmer) !== String(req.user.id)) {
      return res.status(403).json({ error: 'Only the farmer who listed it can reject an offer' });
    }
    if (offer.status !== 'pending') {
      return badRequest(res, `This offer is already ${offer.status}`);
    }

    return res.json({
      offer: await updateOffer(req.params.id, { status: 'rejected', respondedAt: new Date() }),
    });
  }),
);

marketplaceRouter.post(
  '/offers/:id/withdraw',
  requireAuth,
  asyncRoute(async (req, res) => {
    const offer = await getOffer(req.params.id);
    if (!offer) return res.status(404).json({ error: 'Offer not found' });
    if (String(offer.buyer) !== String(req.user.id)) {
      return res.status(403).json({ error: 'Only the buyer who made it can withdraw an offer' });
    }
    if (offer.status !== 'pending') {
      return badRequest(res, `This offer is already ${offer.status}`);
    }

    return res.json({
      offer: await updateOffer(req.params.id, { status: 'withdrawn', respondedAt: new Date() }),
    });
  }),
);

marketplaceRouter.get(
  '/offers/mine',
  requireAuth,
  asyncRoute(async (req, res) => {
    const offers = await listOffers({ buyer: req.user.id });
    return res.json({ count: offers.length, offers });
  }),
);
