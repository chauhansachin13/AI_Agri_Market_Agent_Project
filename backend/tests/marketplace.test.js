import assert from 'node:assert/strict';
import { after, before, beforeEach, describe, test } from 'node:test';

import {
  api,
  registerFarmer,
  resetStore,
  startStubAiService,
  startTestServer,
  stopStubAiService,
  stopTestServer,
} from './helpers.js';

let farmer;
let buyer;

before(async () => {
  await startStubAiService();
  await startTestServer();
});
after(async () => {
  await stopTestServer();
  await stopStubAiService();
});
beforeEach(async () => {
  resetStore();
  farmer = await registerFarmer();
  buyer = await registerFarmer({ phone: '9812345678', name: 'Traders Ltd' });
});

const newListing = (overrides = {}) => ({
  crop: 'Wheat',
  quantityQuintal: 40,
  askPricePerQuintal: 2400,
  location: { state: 'Bihar', district: 'Patna' },
  ...overrides,
});

async function createListing(overrides) {
  const { data } = await api('/api/market/listings', {
    method: 'POST',
    token: farmer.token,
    body: newListing(overrides),
  });
  return data.listing;
}

describe('POST /api/market/listings', () => {
  test('creates a listing', async () => {
    const { status, data } = await api('/api/market/listings', {
      method: 'POST',
      token: farmer.token,
      body: newListing(),
    });
    assert.equal(status, 201);
    assert.equal(data.listing.crop, 'Wheat');
    assert.equal(data.listing.status, 'open');
  });

  test('records the prevailing mandi rate for context', async () => {
    const listing = await createListing();
    assert.equal(listing.mandiReferencePrice, 2300);
  });

  test('requires authentication', async () => {
    const { status } = await api('/api/market/listings', {
      method: 'POST',
      body: newListing(),
    });
    assert.equal(status, 401);
  });

  test('rejects a missing crop', async () => {
    const { status } = await api('/api/market/listings', {
      method: 'POST',
      token: farmer.token,
      body: newListing({ crop: '' }),
    });
    assert.equal(status, 400);
  });

  test('rejects a non-positive quantity', async () => {
    const { status } = await api('/api/market/listings', {
      method: 'POST',
      token: farmer.token,
      body: newListing({ quantityQuintal: 0 }),
    });
    assert.equal(status, 400);
  });

  test('rejects an unknown grade', async () => {
    const { status } = await api('/api/market/listings', {
      method: 'POST',
      token: farmer.token,
      body: newListing({ grade: 'Gold' }),
    });
    assert.equal(status, 400);
  });

  test("falls back to the farmer's saved location", async () => {
    const { data } = await api('/api/market/listings', {
      method: 'POST',
      token: farmer.token,
      body: { crop: 'Onion', quantityQuintal: 10, askPricePerQuintal: 2000 },
    });
    assert.equal(data.listing.location.district, 'Patna');
  });
});

describe('GET /api/market/listings', () => {
  test('lists open listings', async () => {
    await createListing();
    const { status, data } = await api('/api/market/listings');
    assert.equal(status, 200);
    assert.equal(data.count, 1);
  });

  test('filters by crop', async () => {
    await createListing({ crop: 'Wheat' });
    await createListing({ crop: 'Onion' });
    const { data } = await api('/api/market/listings?crop=Onion');
    assert.equal(data.count, 1);
    assert.equal(data.listings[0].crop, 'Onion');
  });

  test('filters by district', async () => {
    await createListing({ location: { state: 'Bihar', district: 'Gaya' } });
    const miss = await api('/api/market/listings?district=Patna');
    const hit = await api('/api/market/listings?district=Gaya');
    assert.equal(miss.data.count, 0);
    assert.equal(hit.data.count, 1);
  });

  test('returns a listing with its offers', async () => {
    const listing = await createListing();
    await api(`/api/market/listings/${listing._id}/offers`, {
      method: 'POST',
      token: buyer.token,
      body: { pricePerQuintal: 2450 },
    });
    const { data } = await api(`/api/market/listings/${listing._id}`);
    assert.equal(data.offers.length, 1);
    assert.equal(data.offers[0].pricePerQuintal, 2450);
  });

  test('404s for an unknown listing', async () => {
    assert.equal((await api('/api/market/listings/deadbeefdeadbeefdeadbeef')).status, 404);
  });
});

describe('PATCH /api/market/listings/:id', () => {
  test('the owner can change the asking price', async () => {
    const listing = await createListing();
    const { status, data } = await api(`/api/market/listings/${listing._id}`, {
      method: 'PATCH',
      token: farmer.token,
      body: { askPricePerQuintal: 2500 },
    });
    assert.equal(status, 200);
    assert.equal(data.listing.askPricePerQuintal, 2500);
  });

  test('another user cannot change it', async () => {
    const listing = await createListing();
    const { status } = await api(`/api/market/listings/${listing._id}`, {
      method: 'PATCH',
      token: buyer.token,
      body: { askPricePerQuintal: 1 },
    });
    assert.equal(status, 403);
  });

  test('the owner can withdraw it', async () => {
    const listing = await createListing();
    const { data } = await api(`/api/market/listings/${listing._id}`, {
      method: 'PATCH',
      token: farmer.token,
      body: { status: 'withdrawn' },
    });
    assert.equal(data.listing.status, 'withdrawn');
  });

  test('a withdrawn listing can no longer be edited', async () => {
    const listing = await createListing();
    await api(`/api/market/listings/${listing._id}`, {
      method: 'PATCH',
      token: farmer.token,
      body: { status: 'withdrawn' },
    });
    const { status } = await api(`/api/market/listings/${listing._id}`, {
      method: 'PATCH',
      token: farmer.token,
      body: { askPricePerQuintal: 9999 },
    });
    assert.equal(status, 400);
  });
});

describe('offers', () => {
  test('a buyer can bid', async () => {
    const listing = await createListing();
    const { status, data } = await api(`/api/market/listings/${listing._id}/offers`, {
      method: 'POST',
      token: buyer.token,
      body: { pricePerQuintal: 2450, quantityQuintal: 20, message: 'Can collect Friday' },
    });
    assert.equal(status, 201);
    assert.equal(data.offer.status, 'pending');
  });

  test('a farmer cannot bid on their own listing', async () => {
    const listing = await createListing();
    const { status } = await api(`/api/market/listings/${listing._id}/offers`, {
      method: 'POST',
      token: farmer.token,
      body: { pricePerQuintal: 2450 },
    });
    assert.equal(status, 400);
  });

  test('an offer cannot exceed the quantity listed', async () => {
    const listing = await createListing({ quantityQuintal: 10 });
    const { status } = await api(`/api/market/listings/${listing._id}/offers`, {
      method: 'POST',
      token: buyer.token,
      body: { pricePerQuintal: 2450, quantityQuintal: 999 },
    });
    assert.equal(status, 400);
  });

  test('an offer defaults to the full listed quantity', async () => {
    const listing = await createListing({ quantityQuintal: 25 });
    const { data } = await api(`/api/market/listings/${listing._id}/offers`, {
      method: 'POST',
      token: buyer.token,
      body: { pricePerQuintal: 2450 },
    });
    assert.equal(data.offer.quantityQuintal, 25);
  });

  test('accepting an offer marks the listing sold', async () => {
    const listing = await createListing();
    const bid = await api(`/api/market/listings/${listing._id}/offers`, {
      method: 'POST',
      token: buyer.token,
      body: { pricePerQuintal: 2450 },
    });
    const { status, data } = await api(`/api/market/offers/${bid.data.offer._id}/accept`, {
      method: 'POST',
      token: farmer.token,
    });
    assert.equal(status, 200);
    assert.equal(data.offer.status, 'accepted');
    assert.equal(data.listing.status, 'sold');
  });

  test('accepting one offer rejects the others', async () => {
    const listing = await createListing();
    const third = await registerFarmer({ phone: '9700000001', name: 'Other Buyer' });

    const first = await api(`/api/market/listings/${listing._id}/offers`, {
      method: 'POST',
      token: buyer.token,
      body: { pricePerQuintal: 2450 },
    });
    const second = await api(`/api/market/listings/${listing._id}/offers`, {
      method: 'POST',
      token: third.token,
      body: { pricePerQuintal: 2400 },
    });

    await api(`/api/market/offers/${first.data.offer._id}/accept`, {
      method: 'POST',
      token: farmer.token,
    });

    // A buyer must not be left thinking their bid is live on sold produce.
    const detail = await api(`/api/market/listings/${listing._id}`);
    const other = detail.data.offers.find((o) => o._id === second.data.offer._id);
    assert.equal(other.status, 'rejected');
  });

  test('a sold listing accepts no further offers', async () => {
    const listing = await createListing();
    const bid = await api(`/api/market/listings/${listing._id}/offers`, {
      method: 'POST',
      token: buyer.token,
      body: { pricePerQuintal: 2450 },
    });
    await api(`/api/market/offers/${bid.data.offer._id}/accept`, {
      method: 'POST',
      token: farmer.token,
    });

    const { status } = await api(`/api/market/listings/${listing._id}/offers`, {
      method: 'POST',
      token: buyer.token,
      body: { pricePerQuintal: 2600 },
    });
    assert.equal(status, 400);
  });

  test('only the listing owner can accept', async () => {
    const listing = await createListing();
    const bid = await api(`/api/market/listings/${listing._id}/offers`, {
      method: 'POST',
      token: buyer.token,
      body: { pricePerQuintal: 2450 },
    });
    const { status } = await api(`/api/market/offers/${bid.data.offer._id}/accept`, {
      method: 'POST',
      token: buyer.token,
    });
    assert.equal(status, 403);
  });

  test('the farmer can reject an offer', async () => {
    const listing = await createListing();
    const bid = await api(`/api/market/listings/${listing._id}/offers`, {
      method: 'POST',
      token: buyer.token,
      body: { pricePerQuintal: 1000 },
    });
    const { data } = await api(`/api/market/offers/${bid.data.offer._id}/reject`, {
      method: 'POST',
      token: farmer.token,
    });
    assert.equal(data.offer.status, 'rejected');
  });

  test('the buyer can withdraw their own offer', async () => {
    const listing = await createListing();
    const bid = await api(`/api/market/listings/${listing._id}/offers`, {
      method: 'POST',
      token: buyer.token,
      body: { pricePerQuintal: 2450 },
    });
    const { data } = await api(`/api/market/offers/${bid.data.offer._id}/withdraw`, {
      method: 'POST',
      token: buyer.token,
    });
    assert.equal(data.offer.status, 'withdrawn');
  });

  test('a buyer cannot withdraw somebody else\'s offer', async () => {
    const listing = await createListing();
    const bid = await api(`/api/market/listings/${listing._id}/offers`, {
      method: 'POST',
      token: buyer.token,
      body: { pricePerQuintal: 2450 },
    });
    const { status } = await api(`/api/market/offers/${bid.data.offer._id}/withdraw`, {
      method: 'POST',
      token: farmer.token,
    });
    assert.equal(status, 403);
  });

  test('an already-resolved offer cannot be resolved again', async () => {
    const listing = await createListing();
    const bid = await api(`/api/market/listings/${listing._id}/offers`, {
      method: 'POST',
      token: buyer.token,
      body: { pricePerQuintal: 2450 },
    });
    await api(`/api/market/offers/${bid.data.offer._id}/accept`, {
      method: 'POST',
      token: farmer.token,
    });
    const { status } = await api(`/api/market/offers/${bid.data.offer._id}/reject`, {
      method: 'POST',
      token: farmer.token,
    });
    assert.equal(status, 400);
  });

  test('a buyer can list their own offers', async () => {
    const listing = await createListing();
    await api(`/api/market/listings/${listing._id}/offers`, {
      method: 'POST',
      token: buyer.token,
      body: { pricePerQuintal: 2450 },
    });
    const { data } = await api('/api/market/offers/mine', { token: buyer.token });
    assert.equal(data.count, 1);
  });
});
