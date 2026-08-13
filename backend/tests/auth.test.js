import assert from 'node:assert/strict';
import { after, before, beforeEach, describe, test } from 'node:test';

import { api, resetStore, startTestServer, stopTestServer, validFarmer } from './helpers.js';

before(async () => {
  await startTestServer();
});
after(async () => {
  await stopTestServer();
});
beforeEach(() => {
  resetStore();
});

describe('POST /api/auth/register', () => {
  test('creates an account and returns a token', async () => {
    const { status, data } = await api('/api/auth/register', { method: 'POST', body: validFarmer });
    assert.equal(status, 201);
    assert.equal(data.user.phone, validFarmer.phone);
    assert.ok(data.token);
  });

  test('never returns the password hash', async () => {
    const { data } = await api('/api/auth/register', { method: 'POST', body: validFarmer });
    assert.equal(data.user.passwordHash, undefined);
  });

  test('rejects a malformed phone number', async () => {
    const { status } = await api('/api/auth/register', {
      method: 'POST',
      body: { ...validFarmer, phone: '12345' },
    });
    assert.equal(status, 400);
  });

  test('rejects a short password', async () => {
    const { status } = await api('/api/auth/register', {
      method: 'POST',
      body: { ...validFarmer, password: 'abc' },
    });
    assert.equal(status, 400);
  });

  test('rejects a missing name', async () => {
    const { status } = await api('/api/auth/register', {
      method: 'POST',
      body: { ...validFarmer, name: '  ' },
    });
    assert.equal(status, 400);
  });

  test('rejects a duplicate phone number', async () => {
    await api('/api/auth/register', { method: 'POST', body: validFarmer });
    const { status } = await api('/api/auth/register', { method: 'POST', body: validFarmer });
    assert.equal(status, 409);
  });

  test('defaults the preferred language to Hindi', async () => {
    const body = { ...validFarmer };
    delete body.preferredLanguage;
    const { data } = await api('/api/auth/register', { method: 'POST', body });
    assert.equal(data.user.preferredLanguage, 'hi');
  });
});

describe('POST /api/auth/login', () => {
  beforeEach(async () => {
    await api('/api/auth/register', { method: 'POST', body: validFarmer });
  });

  test('returns a token for correct credentials', async () => {
    const { status, data } = await api('/api/auth/login', {
      method: 'POST',
      body: { phone: validFarmer.phone, password: validFarmer.password },
    });
    assert.equal(status, 200);
    assert.ok(data.token);
  });

  test('rejects a wrong password', async () => {
    const { status } = await api('/api/auth/login', {
      method: 'POST',
      body: { phone: validFarmer.phone, password: 'wrongpass' },
    });
    assert.equal(status, 401);
  });

  test('gives the same error for an unknown phone as for a wrong password', async () => {
    // Otherwise the endpoint leaks which numbers are registered.
    const unknown = await api('/api/auth/login', {
      method: 'POST',
      body: { phone: '9000000000', password: 'mandi123' },
    });
    const wrong = await api('/api/auth/login', {
      method: 'POST',
      body: { phone: validFarmer.phone, password: 'wrongpass' },
    });
    assert.equal(unknown.status, wrong.status);
    assert.equal(unknown.data.error, wrong.data.error);
  });
});

describe('GET /api/auth/me', () => {
  test('returns the authenticated profile', async () => {
    const { data } = await api('/api/auth/register', { method: 'POST', body: validFarmer });
    const me = await api('/api/auth/me', { token: data.token });
    assert.equal(me.status, 200);
    assert.equal(me.data.user.phone, validFarmer.phone);
  });

  test('rejects a request with no token', async () => {
    assert.equal((await api('/api/auth/me')).status, 401);
  });

  test('rejects a forged token', async () => {
    assert.equal((await api('/api/auth/me', { token: 'not.a.token' })).status, 401);
  });
});
