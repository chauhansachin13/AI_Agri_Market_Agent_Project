/**
 * Mandi price cache (Section 3.5 / 5.1).
 *
 * The report measures two response-time modes: ~1.8 s served from cache and
 * ~4.2 s when the government API is called live. This is that cache — a TTL
 * map keyed by the query parameters, with in-flight request coalescing so a
 * burst of identical queries produces one upstream call rather than many.
 */
import { config } from '../config/index.js';

const entries = new Map(); // key -> { value, expiresAt }
const inFlight = new Map(); // key -> Promise

const keyOf = (params) =>
  Object.entries(params)
    .filter(([, value]) => value !== undefined && value !== null && value !== '')
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([k, v]) => `${k}=${v}`)
    .join('&') || 'all';

export async function withCache(namespace, params, loader) {
  const key = `${namespace}:${keyOf(params)}`;
  const now = Date.now();

  const cached = entries.get(key);
  if (cached && cached.expiresAt > now) {
    return { value: cached.value, cached: true };
  }

  // Coalesce concurrent misses so N simultaneous requests make one upstream call.
  const pending = inFlight.get(key);
  if (pending) {
    return { value: await pending, cached: false };
  }

  const promise = loader()
    .then((value) => {
      entries.set(key, { value, expiresAt: Date.now() + config.mandiCacheTtlMs });
      return value;
    })
    .finally(() => {
      inFlight.delete(key);
    });

  inFlight.set(key, promise);
  return { value: await promise, cached: false };
}

export function invalidateCache() {
  entries.clear();
}

export function cacheStats() {
  const now = Date.now();
  let live = 0;
  for (const entry of entries.values()) {
    if (entry.expiresAt > now) live += 1;
  }
  return { entries: entries.size, live, ttlMs: config.mandiCacheTtlMs };
}
