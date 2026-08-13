import { config } from '../config/index.js';

export function notFound(req, res) {
  res.status(404).json({ error: `Route not found: ${req.method} ${req.originalUrl}` });
}

/* eslint-disable-next-line no-unused-vars */
export function errorHandler(error, req, res, _next) {
  const status = error.statusCode || error.status || 500;

  if (status >= 500) {
    console.error('[error]', error);
  }

  const body = { error: error.message || 'Internal server error' };
  // Stack traces are useful in development and a disclosure risk in production.
  if (config.nodeEnv !== 'production' && status >= 500) {
    body.stack = error.stack;
  }

  res.status(status).json(body);
}

/** Wrap an async route handler so rejections reach the error handler. */
export const asyncRoute = (handler) => (req, res, next) =>
  Promise.resolve(handler(req, res, next)).catch(next);
