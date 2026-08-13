import dotenv from 'dotenv';

dotenv.config();

const toInt = (value, fallback) => {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : fallback;
};

export const config = {
  port: toInt(process.env.PORT, 5000),
  nodeEnv: process.env.NODE_ENV || 'development',

  mongoUri: process.env.MONGO_URI || '',

  jwtSecret: process.env.JWT_SECRET || 'development-only-secret-change-me',
  jwtExpiresIn: process.env.JWT_EXPIRES_IN || '7d',

  aiServiceUrl: process.env.AI_SERVICE_URL || 'http://localhost:8000',
  aiServiceTimeoutMs: toInt(process.env.AI_SERVICE_TIMEOUT_MS, 30000),

  // Section 3.5: mandi records are cached and refreshed on a fixed interval so
  // repeat queries are served without a round trip to the government API.
  mandiCacheTtlMs: toInt(process.env.MANDI_CACHE_TTL_MS, 30 * 60 * 1000),

  corsOrigins: (process.env.CORS_ORIGINS || 'http://localhost:5173,http://localhost:3000')
    .split(',')
    .map((origin) => origin.trim())
    .filter(Boolean),

  rateLimitWindowMs: toInt(process.env.RATE_LIMIT_WINDOW_MS, 15 * 60 * 1000),
  rateLimitMax: toInt(process.env.RATE_LIMIT_MAX, 300),

  // Section 6.3: WhatsApp Business API delivery. Every field is optional; the
  // integration reports itself unconfigured rather than failing at startup.
  whatsapp: {
    graphUrl: process.env.WHATSAPP_GRAPH_URL || 'https://graph.facebook.com',
    apiVersion: process.env.WHATSAPP_API_VERSION || 'v21.0',
    token: process.env.WHATSAPP_TOKEN || '',
    phoneNumberId: process.env.WHATSAPP_PHONE_NUMBER_ID || '',
    verifyToken: process.env.WHATSAPP_VERIFY_TOKEN || '',
    appSecret: process.env.WHATSAPP_APP_SECRET || '',
  },
};

if (config.nodeEnv === 'production' && config.jwtSecret.startsWith('development-only')) {
  throw new Error('JWT_SECRET must be set to a real secret in production.');
}
