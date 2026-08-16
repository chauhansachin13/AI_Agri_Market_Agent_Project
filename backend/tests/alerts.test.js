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
import { shouldTrigger } from '../src/store/alerts.js';

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

describe('trigger logic', () => {
  test("'above' fires once the price reaches the target", () => {
    const alert = { direction: 'above', targetPrice: 2500 };
    assert.equal(shouldTrigger(alert, 2600), true);
    assert.equal(shouldTrigger(alert, 2500), true, 'reaching the target counts');
    assert.equal(shouldTrigger(alert, 2400), false);
  });

  test("'below' is the mirror", () => {
    const alert = { direction: 'below', targetPrice: 2000 };
    assert.equal(shouldTrigger(alert, 1900), true);
    assert.equal(shouldTrigger(alert, 2100), false);
  });

  test('a missing price never fires an alert', () => {
    // Firing on absent data would send a farmer to the mandi for nothing.
    assert.equal(shouldTrigger({ direction: 'above', targetPrice: 100 }, NaN), false);
    assert.equal(shouldTrigger({ direction: 'above', targetPrice: 100 }, undefined), false);
  });
});

describe('alerts API', () => {
  test('requires authentication', async () => {
    assert.equal((await api('/api/alerts')).status, 401);
  });

  test('creates an alert', async () => {
    const { token } = await registerFarmer();
    const { status, data } = await api('/api/alerts', {
      method: 'POST',
      token,
      body: { crop: 'Wheat', targetPrice: 2600 },
    });
    assert.equal(status, 201);
    assert.equal(data.alert.crop, 'Wheat');
    assert.equal(data.alert.status, 'active');
    assert.ok(data.alert.id);
  });

  test("defaults to the farmer's own district", async () => {
    const { token } = await registerFarmer();
    const { data } = await api('/api/alerts', {
      method: 'POST',
      token,
      body: { crop: 'Wheat', targetPrice: 2600 },
    });
    assert.equal(data.alert.district, 'Patna');
  });

  test('rejects a missing crop', async () => {
    const { token } = await registerFarmer();
    const { status } = await api('/api/alerts', {
      method: 'POST', token, body: { targetPrice: 2600 },
    });
    assert.equal(status, 400);
  });

  test('rejects a non-positive target', async () => {
    const { token } = await registerFarmer();
    for (const targetPrice of [0, -5, 'abc']) {
      const { status } = await api('/api/alerts', {
        method: 'POST', token, body: { crop: 'Wheat', targetPrice },
      });
      assert.equal(status, 400, `targetPrice=${targetPrice}`);
    }
  });

  test('rejects an invalid direction', async () => {
    const { token } = await registerFarmer();
    const { status } = await api('/api/alerts', {
      method: 'POST', token, body: { crop: 'Wheat', targetPrice: 100, direction: 'sideways' },
    });
    assert.equal(status, 400);
  });

  test('lists only the caller’s own alerts', async () => {
    const mine = await registerFarmer();
    const theirs = await registerFarmer({ phone: '9812345678' });
    await api('/api/alerts', { method: 'POST', token: mine.token, body: { crop: 'Wheat', targetPrice: 2600 } });
    await api('/api/alerts', { method: 'POST', token: theirs.token, body: { crop: 'Onion', targetPrice: 2000 } });

    const { data } = await api('/api/alerts', { token: mine.token });
    assert.equal(data.count, 1);
    assert.equal(data.alerts[0].crop, 'Wheat');
  });

  test('fires when the market reaches the target', async () => {
    // The stub reports wheat at 2300.
    const { token } = await registerFarmer();
    await api('/api/alerts', { method: 'POST', token, body: { crop: 'Wheat', targetPrice: 2000 } });

    const { data } = await api('/api/alerts/check', { method: 'POST', token });
    assert.equal(data.checked, 1);
    assert.equal(data.triggered.length, 1);
    assert.equal(data.triggered[0].alert.status, 'triggered');
    assert.equal(data.triggered[0].price, 2300);
  });

  test('does not fire below the target', async () => {
    const { token } = await registerFarmer();
    await api('/api/alerts', { method: 'POST', token, body: { crop: 'Wheat', targetPrice: 9999 } });

    const { data } = await api('/api/alerts/check', { method: 'POST', token });
    assert.equal(data.triggered.length, 0);
  });

  test('records the last seen price even when it does not fire', async () => {
    const { token } = await registerFarmer();
    await api('/api/alerts', { method: 'POST', token, body: { crop: 'Wheat', targetPrice: 9999 } });
    await api('/api/alerts/check', { method: 'POST', token });

    const { data } = await api('/api/alerts', { token });
    assert.equal(data.alerts[0].lastSeenPrice, 2300);
    assert.ok(data.alerts[0].lastCheckedAt);
  });

  test('a triggered alert is not re-checked', async () => {
    const { token } = await registerFarmer();
    await api('/api/alerts', { method: 'POST', token, body: { crop: 'Wheat', targetPrice: 2000 } });
    await api('/api/alerts/check', { method: 'POST', token });

    const second = await api('/api/alerts/check', { method: 'POST', token });
    assert.equal(second.data.checked, 0, 'already-triggered alerts drop out of the active set');
  });

  test('can be paused and resumed', async () => {
    const { token } = await registerFarmer();
    const created = await api('/api/alerts', {
      method: 'POST', token, body: { crop: 'Wheat', targetPrice: 2000 },
    });
    const id = created.data.alert.id;

    await api(`/api/alerts/${id}`, { method: 'PATCH', token, body: { status: 'paused' } });
    const paused = await api('/api/alerts/check', { method: 'POST', token });
    assert.equal(paused.data.checked, 0);

    await api(`/api/alerts/${id}`, { method: 'PATCH', token, body: { status: 'active' } });
    const resumed = await api('/api/alerts/check', { method: 'POST', token });
    assert.equal(resumed.data.checked, 1);
  });

  test('cannot modify someone else’s alert', async () => {
    const owner = await registerFarmer();
    const other = await registerFarmer({ phone: '9812345670' });
    const created = await api('/api/alerts', {
      method: 'POST', token: owner.token, body: { crop: 'Wheat', targetPrice: 2000 },
    });
    const { status } = await api(`/api/alerts/${created.data.alert.id}`, {
      method: 'PATCH', token: other.token, body: { status: 'paused' },
    });
    assert.equal(status, 403);
  });

  test('cannot delete someone else’s alert', async () => {
    const owner = await registerFarmer();
    const other = await registerFarmer({ phone: '9812345671' });
    const created = await api('/api/alerts', {
      method: 'POST', token: owner.token, body: { crop: 'Wheat', targetPrice: 2000 },
    });
    const { status } = await api(`/api/alerts/${created.data.alert.id}`, {
      method: 'DELETE', token: other.token,
    });
    assert.equal(status, 403);
  });

  test('deletes its own alert', async () => {
    const { token } = await registerFarmer();
    const created = await api('/api/alerts', {
      method: 'POST', token, body: { crop: 'Wheat', targetPrice: 2000 },
    });
    const { status } = await api(`/api/alerts/${created.data.alert.id}`, { method: 'DELETE', token });
    assert.equal(status, 204);

    const { data } = await api('/api/alerts', { token });
    assert.equal(data.count, 0);
  });

  test('404s on an unknown alert', async () => {
    const { token } = await registerFarmer();
    const { status } = await api('/api/alerts/aaaaaaaaaaaaaaaaaaaaaaaa', {
      method: 'PATCH', token, body: { status: 'paused' },
    });
    assert.equal(status, 404);
  });
});
