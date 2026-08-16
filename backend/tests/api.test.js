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

let stub;

before(async () => {
  stub = await startStubAiService();
  await startTestServer();
});
after(async () => {
  await stopTestServer();
  await stopStubAiService();
});
beforeEach(() => {
  resetStore();
  stub.calls.length = 0;
});

describe('GET /health', () => {
  test('reports the gateway and its dependencies', async () => {
    const { status, data } = await api('/health');
    assert.equal(status, 200);
    assert.equal(data.status, 'ok');
    assert.equal(data.database, 'in-memory');
    assert.equal(data.aiService.reachable, true);
  });
});

describe('POST /api/queries', () => {
  test('returns the agent response unchanged', async () => {
    const { status, data } = await api('/api/queries', {
      method: 'POST',
      body: { query: 'wheat price in Patna' },
    });
    assert.equal(status, 200);
    assert.equal(data.intent, 'price_query');
    assert.equal(data.english_answer, 'Wheat is Rs 2300 per quintal at Patna City mandi.');
    assert.ok(data.hindi_answer);
    assert.ok(Array.isArray(data.reasoning_steps));
  });

  test('rejects an empty query', async () => {
    const { status } = await api('/api/queries', { method: 'POST', body: { query: '   ' } });
    assert.equal(status, 400);
  });

  test('rejects a missing body', async () => {
    const { status } = await api('/api/queries', { method: 'POST', body: {} });
    assert.equal(status, 400);
  });

  test('works without authentication', async () => {
    const { status } = await api('/api/queries', {
      method: 'POST',
      body: { query: 'wheat price' },
    });
    assert.equal(status, 200);
  });

  test("falls back to the signed-in farmer's saved pincode", async () => {
    const { token } = await registerFarmer();
    await api('/api/queries', { method: 'POST', body: { query: 'wheat price' }, token });
    const forwarded = stub.calls.find((c) => c.path === '/agent/query');
    assert.equal(forwarded.body.pincode, '800001');
  });

  test('an explicit pincode overrides the profile default', async () => {
    const { token } = await registerFarmer();
    await api('/api/queries', {
      method: 'POST',
      body: { query: 'wheat price', pincode: '452001' },
      token,
    });
    const forwarded = stub.calls.find((c) => c.path === '/agent/query');
    assert.equal(forwarded.body.pincode, '452001');
  });

  test("uses the farmer's preferred language when none is given", async () => {
    const { token } = await registerFarmer({ preferredLanguage: 'en' });
    await api('/api/queries', { method: 'POST', body: { query: 'wheat price' }, token });
    const forwarded = stub.calls.find((c) => c.path === '/agent/query');
    assert.equal(forwarded.body.language_override, 'en');
  });

  test('persists the interaction for a signed-in farmer', async () => {
    const { token } = await registerFarmer();
    await api('/api/queries', { method: 'POST', body: { query: 'wheat price' }, token });
    const history = await api('/api/queries/history', { token });
    assert.equal(history.status, 200);
    assert.equal(history.data.length, 1);
    assert.equal(history.data[0].intent, 'price_query');
    assert.equal(history.data[0].recommendation, 'WAIT');
  });

  test('history requires authentication', async () => {
    assert.equal((await api('/api/queries/history')).status, 401);
  });

  test('stats aggregate by intent', async () => {
    await api('/api/queries', { method: 'POST', body: { query: 'wheat price' } });
    await api('/api/queries', { method: 'POST', body: { query: 'onion price' } });
    const { data } = await api('/api/queries/stats');
    assert.equal(data.total, 2);
    assert.equal(data.byIntent.price_query, 2);
    assert.ok(data.averageConfidence > 0);
  });
});

describe('POST /api/queries/parse', () => {
  test('exposes the NLP pipeline', async () => {
    const { status, data } = await api('/api/queries/parse', {
      method: 'POST',
      body: { query: 'wheat price in Patna' },
    });
    assert.equal(status, 200);
    assert.equal(data.crop, 'Wheat');
  });

  test('rejects an empty query', async () => {
    const { status } = await api('/api/queries/parse', { method: 'POST', body: { query: '' } });
    assert.equal(status, 400);
  });
});

describe('GET /api/mandis', () => {
  test('returns price records', async () => {
    const { status, data } = await api('/api/mandis?crop=Wheat&state=Bihar');
    assert.equal(status, 200);
    assert.equal(data.count, 1);
    assert.equal(data.records[0].commodity, 'Wheat');
  });

  test('serves a repeated request from cache', async () => {
    const first = await api('/api/mandis?crop=Wheat&state=Bihar');
    const second = await api('/api/mandis?crop=Wheat&state=Bihar');
    assert.equal(first.headers.get('x-cache'), 'MISS');
    assert.equal(second.headers.get('x-cache'), 'HIT');
    // The upstream service must have been called exactly once.
    assert.equal(stub.calls.filter((c) => c.path === '/mandi/prices').length, 1);
  });

  test('a different crop is a different cache key', async () => {
    await api('/api/mandis?crop=Wheat');
    const second = await api('/api/mandis?crop=Onion');
    assert.equal(second.headers.get('x-cache'), 'MISS');
  });

  test('coalesces concurrent identical requests into one upstream call', async () => {
    await Promise.all([
      api('/api/mandis?crop=Potato&state=Bihar'),
      api('/api/mandis?crop=Potato&state=Bihar'),
      api('/api/mandis?crop=Potato&state=Bihar'),
    ]);
    assert.equal(stub.calls.filter((c) => c.path === '/mandi/prices').length, 1);
  });

  test('caps the record limit', async () => {
    await api('/api/mandis?crop=Wheat&limit=9999');
    const forwarded = stub.calls.find((c) => c.path === '/mandi/prices');
    assert.equal(Number(forwarded.query.limit), 200);
  });

  test('returns buyer contacts', async () => {
    const { status, data } = await api('/api/mandis/buyers?state=Bihar&district=Patna');
    assert.equal(status, 200);
    assert.equal(data.buyers[0].apmc_name, 'Patna City APMC');
  });
});

describe('GET /api/prices', () => {
  test('returns a trend analysis', async () => {
    const { status, data } = await api('/api/prices/trend?crop=Wheat&district=Patna');
    assert.equal(status, 200);
    assert.equal(data.direction, 'upward');
    assert.equal(data.ema_7, 2400);
  });

  test('requires a crop for the trend', async () => {
    assert.equal((await api('/api/prices/trend')).status, 400);
  });

  test('returns a date-ordered series', async () => {
    const { data } = await api('/api/prices/series?crop=Wheat&district=Patna');
    const dates = data.points.map((p) => p.date);
    assert.deepEqual(dates, [...dates].sort());
  });

  test('requires a crop for the series', async () => {
    assert.equal((await api('/api/prices/series')).status, 400);
  });

  test('caps the history window', async () => {
    await api('/api/prices/series?crop=Wheat&days=9999');
    const forwarded = stub.calls.find((c) => c.path === '/mandi/series');
    assert.equal(Number(forwarded.query.days), 365);
  });
});

describe('PATCH /api/users/profile', () => {
  test('updates the profile', async () => {
    const { token } = await registerFarmer();
    const { status, data } = await api('/api/users/profile', {
      method: 'PATCH',
      token,
      body: { name: 'Ramesh K', preferredLanguage: 'en', crops: ['Onion'] },
    });
    assert.equal(status, 200);
    assert.equal(data.user.name, 'Ramesh K');
    assert.equal(data.user.preferredLanguage, 'en');
    assert.deepEqual(data.user.crops, ['Onion']);
  });

  test('rejects an unsupported language', async () => {
    const { token } = await registerFarmer();
    const { status } = await api('/api/users/profile', {
      method: 'PATCH',
      token,
      body: { preferredLanguage: 'fr' },
    });
    assert.equal(status, 400);
  });

  test('rejects a malformed pincode', async () => {
    const { token } = await registerFarmer();
    const { status } = await api('/api/users/profile', {
      method: 'PATCH',
      token,
      body: { location: { pincode: '12' } },
    });
    assert.equal(status, 400);
  });

  test('ignores an attempt to change the phone number', async () => {
    const { token } = await registerFarmer();
    const { status } = await api('/api/users/profile', {
      method: 'PATCH',
      token,
      body: { phone: '9999999999' },
    });
    // No updatable field was supplied, so the request is refused outright.
    assert.equal(status, 400);
    const me = await api('/api/auth/me', { token });
    assert.equal(me.data.user.phone, '9876543210');
  });

  test('requires authentication', async () => {
    assert.equal((await api('/api/users/profile', { method: 'PATCH', body: {} })).status, 401);
  });
});

describe('routing', () => {
  test('an unknown route returns 404 with a message', async () => {
    const { status, data } = await api('/api/nope');
    assert.equal(status, 404);
    assert.match(data.error, /Route not found/);
  });
});

describe('language auto-detection', () => {
  test("'auto' is forwarded as no override, so detection decides", async () => {
    await api('/api/queries', {
      method: 'POST',
      body: { query: 'कांद्याचा भाव किती आहे?', languageOverride: 'auto' },
    });
    const forwarded = stub.calls.find((c) => c.path === '/agent/query');
    assert.equal(forwarded.body.language_override, null);
  });

  test("'auto' is not replaced by the profile preference", async () => {
    // Otherwise a Marathi question from a farmer whose profile says Hindi
    // would be answered in Hindi despite them asking for detection.
    const { token } = await registerFarmer({ preferredLanguage: 'hi' });
    await api('/api/queries', {
      method: 'POST',
      token,
      body: { query: 'कांद्याचा भाव किती आहे?', languageOverride: 'auto' },
    });
    const forwarded = stub.calls.find((c) => c.path === '/agent/query');
    assert.equal(forwarded.body.language_override, null);
  });

  test('an explicit language is still honoured', async () => {
    await api('/api/queries', {
      method: 'POST',
      body: { query: 'wheat price', languageOverride: 'ta' },
    });
    const forwarded = stub.calls.find((c) => c.path === '/agent/query');
    assert.equal(forwarded.body.language_override, 'ta');
  });
});

describe('resource id contract', () => {
  test('every resource exposes `id`, not just the user', async () => {
    // The user resource always returned `id` while queries and listings
    // returned Mongo's `_id`, so the same API used two conventions depending
    // on which resource you asked for.
    const { token } = await registerFarmer();

    const me = await api('/api/auth/me', { token });
    assert.ok(me.data.user.id, 'user.id');

    await api('/api/queries', { method: 'POST', token, body: { query: 'wheat price' } });
    const history = await api('/api/queries/history', { token });
    assert.ok(history.data[0].id, 'query.id');

    const created = await api('/api/market/listings', {
      method: 'POST',
      token,
      body: { crop: 'Wheat', quantityQuintal: 10, askPricePerQuintal: 2500 },
    });
    assert.ok(created.data.listing.id, 'listing.id');

    const listed = await api('/api/market/listings');
    assert.ok(listed.data.listings[0].id, 'listed listing.id');
  });

  test('`id` and `_id` agree where both are present', async () => {
    const { token } = await registerFarmer();
    const created = await api('/api/market/listings', {
      method: 'POST',
      token,
      body: { crop: 'Onion', quantityQuintal: 5, askPricePerQuintal: 2000 },
    });
    const listing = created.data.listing;
    assert.equal(String(listing.id), String(listing._id));
  });

  test('a listing can be fetched by its `id`', async () => {
    const { token } = await registerFarmer();
    const created = await api('/api/market/listings', {
      method: 'POST',
      token,
      body: { crop: 'Potato', quantityQuintal: 8, askPricePerQuintal: 1500 },
    });
    const { status } = await api(`/api/market/listings/${created.data.listing.id}`);
    assert.equal(status, 200);
  });
});

describe('personalisation forwarding', () => {
  test('a profile in the request reaches the AI service', async () => {
    await api('/api/queries', {
      method: 'POST',
      body: {
        query: 'should i sell wheat',
        profile: { risk_tolerance: 'patient', has_storage: true },
      },
    });
    const forwarded = stub.calls.find((c) => c.path === '/agent/query');
    assert.equal(forwarded.body.profile.risk_tolerance, 'patient');
    assert.equal(forwarded.body.profile.has_storage, true);
  });

  test('no profile means none is forwarded', async () => {
    await api('/api/queries', { method: 'POST', body: { query: 'wheat price' } });
    const forwarded = stub.calls.find((c) => c.path === '/agent/query');
    assert.equal(forwarded.body.profile, null);
  });

  test("a signed-in farmer's crops fill in when the profile omits them", async () => {
    const { token } = await registerFarmer({ crops: ['Wheat', 'Potato'] });
    await api('/api/queries', {
      method: 'POST',
      token,
      body: { query: 'should i sell', profile: { risk_tolerance: 'cautious' } },
    });
    const forwarded = stub.calls.find((c) => c.path === '/agent/query');
    assert.deepEqual(forwarded.body.profile.crops, ['Wheat', 'Potato']);
  });
});
