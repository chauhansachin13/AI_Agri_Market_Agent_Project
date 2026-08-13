import jwt from 'jsonwebtoken';

import { config } from '../config/index.js';
import { findUserById } from '../store/index.js';

export function signToken(userId) {
  return jwt.sign({ sub: userId }, config.jwtSecret, { expiresIn: config.jwtExpiresIn });
}

function extractToken(req) {
  const header = req.headers.authorization || '';
  return header.startsWith('Bearer ') ? header.slice(7).trim() : null;
}

/** Reject the request unless it carries a valid token. */
export async function requireAuth(req, res, next) {
  const token = extractToken(req);
  if (!token) {
    return res.status(401).json({ error: 'Authentication required' });
  }

  try {
    const payload = jwt.verify(token, config.jwtSecret);
    const user = await findUserById(payload.sub);
    if (!user) {
      return res.status(401).json({ error: 'Account no longer exists' });
    }
    req.user = user;
    return next();
  } catch {
    return res.status(401).json({ error: 'Invalid or expired token' });
  }
}

/**
 * Attach the user when a valid token is present, but let anonymous requests
 * through. Farmers can ask questions without an account; signing in only adds
 * history and personalisation.
 */
export async function optionalAuth(req, _res, next) {
  const token = extractToken(req);
  if (!token) return next();

  try {
    const payload = jwt.verify(token, config.jwtSecret);
    req.user = await findUserById(payload.sub);
  } catch {
    req.user = null;
  }
  return next();
}
