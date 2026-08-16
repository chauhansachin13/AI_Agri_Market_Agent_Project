/**
 * Service worker.
 *
 * Rural connectivity is the constraint this exists for: the report's own
 * motivation is farmers on intermittent, low-bandwidth links. Two strategies,
 * chosen by what breaks if the data is stale:
 *
 *   - App shell and hashed assets: cache-first. They are immutable (the
 *     filename changes when the content does), so serving from cache is always
 *     correct and makes a repeat visit instant and offline-capable.
 *
 *   - API responses: network-first, falling back to the last good response.
 *     A price must be fresh when the network allows. When it does not, a
 *     yesterday's price clearly labelled as stale beats a blank screen — the
 *     client marks these with the `X-From-Cache` header so the UI can say so.
 *
 * Prices are never *written* from cache into a decision silently: the header
 * is what lets the interface tell the farmer the figure may be old.
 */
const VERSION = 'v1';
const SHELL_CACHE = `agri-shell-${VERSION}`;
const DATA_CACHE = `agri-data-${VERSION}`;

const SHELL_ASSETS = ['/', '/manifest.webmanifest', '/icon.svg'];

// Endpoints worth keeping a copy of. Auth and mutations are excluded: a stale
// login or a replayed listing would be wrong, not merely old.
const CACHEABLE_API = [/^\/api\/mandis/, /^\/api\/prices/, /^\/api\/queries\/languages/];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE).then((cache) => cache.addAll(SHELL_ASSETS)).then(() => self.skipWaiting()),
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key !== SHELL_CACHE && key !== DATA_CACHE)
            .map((key) => caches.delete(key)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

function isCacheableApi(pathname) {
  return CACHEABLE_API.some((pattern) => pattern.test(pathname));
}

async function networkFirst(request) {
  const cache = await caches.open(DATA_CACHE);
  try {
    const response = await fetch(request);
    if (response.ok) cache.put(request, response.clone());
    return response;
  } catch (error) {
    const cached = await cache.match(request);
    if (!cached) throw error;
    // Tell the app the figures are from cache so it can label them.
    const headers = new Headers(cached.headers);
    headers.set('X-From-Cache', 'true');
    return new Response(await cached.blob(), {
      status: cached.status,
      statusText: cached.statusText,
      headers,
    });
  }
}

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;

  const response = await fetch(request);
  if (response.ok && new URL(request.url).origin === self.location.origin) {
    const cache = await caches.open(SHELL_CACHE);
    cache.put(request, response.clone());
  }
  return response;
}

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (url.pathname.startsWith('/api/')) {
    if (isCacheableApi(url.pathname)) event.respondWith(networkFirst(request));
    return;
  }

  // Client-side routes have no file of their own; they are the app shell.
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request).catch(() => caches.match('/').then((r) => r || Response.error())),
    );
    return;
  }

  event.respondWith(cacheFirst(request));
});
