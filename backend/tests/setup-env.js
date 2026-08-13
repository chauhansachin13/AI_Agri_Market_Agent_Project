/**
 * Test environment.
 *
 * This must be imported before anything that reads `config`. ESM evaluates all
 * imports before any statement in the importing module runs, so setting these
 * variables inside `helpers.js` alongside its imports would happen *after*
 * `src/config` had already snapshotted `process.env`.
 */
process.env.NODE_ENV = 'test';
process.env.JWT_SECRET = 'test-secret';
process.env.RATE_LIMIT_MAX = '1000000';
process.env.MONGO_URI = '';
process.env.MANDI_CACHE_TTL_MS = process.env.MANDI_CACHE_TTL_MS || '60000';
