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

// WhatsApp webhook tests need a signing secret and a verify token, but must
// not have a real Graph API token — an accidental outbound send in CI would
// message a real phone number.
process.env.WHATSAPP_APP_SECRET = 'test-app-secret';
process.env.WHATSAPP_VERIFY_TOKEN = 'test-verify-token';
process.env.WHATSAPP_TOKEN = '';
process.env.WHATSAPP_PHONE_NUMBER_ID = '';
