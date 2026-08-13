import './setup-env.js';

import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { after, before, describe, test } from 'node:test';

import { api, startStubAiService, startTestServer, stopStubAiService, stopTestServer } from './helpers.js';
import { findFrontendBuild } from '../src/static.js';

before(async () => {
  await startStubAiService();
  await startTestServer();
});
after(async () => {
  await stopTestServer();
  await stopStubAiService();
});

const built = findFrontendBuild();

describe('serving the single-page app', () => {
  test('API routes are never shadowed by the SPA fallback', async () => {
    // The fallback returns index.html for unknown GETs. If it were mounted
    // before the API, or its pattern were too greedy, every endpoint would
    // silently start returning HTML.
    const { status, data } = await api('/api/mandis?crop=Wheat');
    assert.equal(status, 200);
    assert.equal(typeof data, 'object');
    assert.ok(Array.isArray(data.records));
  });

  test('the health endpoint still returns JSON', async () => {
    const { data } = await api('/health');
    assert.equal(data.status, 'ok');
  });

  test('an unknown API route still 404s as JSON, not as the app shell', async () => {
    const { status, data } = await api('/api/definitely-not-a-route');
    assert.equal(status, 404);
    assert.match(data.error, /Route not found/);
  });

  test('the build is discovered when it exists', { skip: !built }, () => {
    assert.ok(fs.existsSync(path.join(built, 'index.html')));
  });

  test('a client-side route serves the app shell', { skip: !built }, async () => {
    const { status, data } = await api('/market');
    assert.equal(status, 200);
    assert.match(String(data), /<div id="root">/);
  });

  test('a deep client-side route serves the app shell too', { skip: !built }, async () => {
    const { status } = await api('/prices');
    assert.equal(status, 200);
  });

  test('hashed assets are cached immutably, index.html is not', { skip: !built }, async () => {
    const shell = await api('/market');
    assert.match(shell.headers.get('cache-control') || '', /no-cache/);

    const html = String(shell.data);
    const asset = html.match(/\/assets\/[A-Za-z0-9._-]+\.js/)?.[0];
    assert.ok(asset, 'expected a hashed asset reference in index.html');

    const response = await api(asset);
    assert.equal(response.status, 200);
    assert.match(response.headers.get('cache-control') || '', /immutable/);
  });
});
