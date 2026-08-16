/**
 * Marketplace persistence (Section 6.3).
 *
 * Same facade pattern as the main store: Mongoose when a database is
 * connected, an in-memory implementation with an identical interface
 * otherwise, so the marketplace is fully exercisable without MongoDB.
 */
import crypto from 'node:crypto';

import { isDatabaseConnected } from '../config/db.js';
import { Listing } from '../models/Listing.js';
import { Offer } from '../models/Offer.js';

const memory = {
  listings: new Map(), // id -> listing
  offers: new Map(), // id -> offer
};

const newId = () => crypto.randomBytes(12).toString('hex');

/**
 * Normalise a stored document for the API.
 *
 * Mongo names its primary key `_id`, but the user resource has always exposed
 * `id`. Leaking the storage convention for some resources and not others makes
 * the API inconsistent in a way consumers trip over, so every resource gets an
 * `id`. `_id` is left in place as well, since existing clients read it.
 */
const shape = (doc) => {
  if (!doc) return doc;
  const plain = typeof doc.toObject === 'function' ? doc.toObject() : { ...doc };
  if (plain._id !== undefined && plain.id === undefined) {
    plain.id = String(plain._id);
  }
  return plain;
};

const matches = (listing, filters) => {
  if (filters.crop && listing.crop.toLowerCase() !== filters.crop.toLowerCase()) return false;
  if (filters.status && listing.status !== filters.status) return false;
  if (filters.farmer && String(listing.farmer) !== String(filters.farmer)) return false;
  if (
    filters.district &&
    (listing.location?.district || '').toLowerCase() !== filters.district.toLowerCase()
  ) {
    return false;
  }
  if (
    filters.state &&
    (listing.location?.state || '').toLowerCase() !== filters.state.toLowerCase()
  ) {
    return false;
  }
  return true;
};

// --- listings ---------------------------------------------------------------

export async function createListing(data) {
  if (isDatabaseConnected()) {
    return shape(await Listing.create(data));
  }
  const listing = {
    _id: newId(),
    status: 'open',
    grade: 'FAQ',
    variety: 'Other',
    createdAt: new Date(),
    updatedAt: new Date(),
    ...data,
  };
  listing.id = listing._id;
  memory.listings.set(listing._id, listing);
  return listing;
}

export async function getListing(id) {
  if (isDatabaseConnected()) {
    return shape(await Listing.findById(id).exec());
  }
  return memory.listings.get(id) || null;
}

export async function listListings(filters = {}, limit = 50) {
  if (isDatabaseConnected()) {
    const query = {};
    if (filters.crop) query.crop = new RegExp(`^${filters.crop}$`, 'i');
    if (filters.status) query.status = filters.status;
    if (filters.farmer) query.farmer = filters.farmer;
    if (filters.district) query['location.district'] = new RegExp(`^${filters.district}$`, 'i');
    if (filters.state) query['location.state'] = new RegExp(`^${filters.state}$`, 'i');
    return (await Listing.find(query).sort({ createdAt: -1 }).limit(limit).lean().exec()).map(shape);
  }

  return [...memory.listings.values()]
    .filter((listing) => matches(listing, filters))
    .sort((a, b) => b.createdAt - a.createdAt)
    .slice(0, limit);
}

export async function updateListing(id, updates) {
  if (isDatabaseConnected()) {
    return shape(
      await Listing.findByIdAndUpdate(id, updates, { new: true, runValidators: true }).exec(),
    );
  }
  const listing = memory.listings.get(id);
  if (!listing) return null;
  Object.assign(listing, updates, { updatedAt: new Date() });
  return listing;
}

// --- offers -----------------------------------------------------------------

export async function createOffer(data) {
  if (isDatabaseConnected()) {
    return shape(await Offer.create(data));
  }
  const offer = {
    _id: newId(),
    status: 'pending',
    createdAt: new Date(),
    updatedAt: new Date(),
    ...data,
  };
  offer.id = offer._id;
  memory.offers.set(offer._id, offer);
  return offer;
}

export async function getOffer(id) {
  if (isDatabaseConnected()) {
    return shape(await Offer.findById(id).exec());
  }
  return memory.offers.get(id) || null;
}

export async function listOffers(filters = {}, limit = 50) {
  if (isDatabaseConnected()) {
    const query = {};
    if (filters.listing) query.listing = filters.listing;
    if (filters.buyer) query.buyer = filters.buyer;
    if (filters.status) query.status = filters.status;
    return (await Offer.find(query).sort({ pricePerQuintal: -1 }).limit(limit).lean().exec()).map(shape);
  }

  return [...memory.offers.values()]
    .filter(
      (offer) =>
        (!filters.listing || String(offer.listing) === String(filters.listing)) &&
        (!filters.buyer || String(offer.buyer) === String(filters.buyer)) &&
        (!filters.status || offer.status === filters.status),
    )
    .sort((a, b) => b.pricePerQuintal - a.pricePerQuintal)
    .slice(0, limit);
}

export async function updateOffer(id, updates) {
  if (isDatabaseConnected()) {
    return shape(
      await Offer.findByIdAndUpdate(id, updates, { new: true, runValidators: true }).exec(),
    );
  }
  const offer = memory.offers.get(id);
  if (!offer) return null;
  Object.assign(offer, updates, { updatedAt: new Date() });
  return offer;
}

/**
 * Reject every other pending offer on a listing.
 *
 * Accepting one bid must close the rest in the same operation, or a buyer can
 * be left believing an offer is still live on produce that is already sold.
 */
export async function rejectOtherOffers(listingId, acceptedOfferId) {
  if (isDatabaseConnected()) {
    await Offer.updateMany(
      { listing: listingId, _id: { $ne: acceptedOfferId }, status: 'pending' },
      { status: 'rejected', respondedAt: new Date() },
    ).exec();
    return;
  }
  for (const offer of memory.offers.values()) {
    if (
      String(offer.listing) === String(listingId) &&
      String(offer._id) !== String(acceptedOfferId) &&
      offer.status === 'pending'
    ) {
      offer.status = 'rejected';
      offer.respondedAt = new Date();
    }
  }
}

/** Reset the in-memory marketplace. Test-only. */
export function resetMarketplace() {
  memory.listings.clear();
  memory.offers.clear();
}
