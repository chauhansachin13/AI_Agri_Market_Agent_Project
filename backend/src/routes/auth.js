import bcrypt from 'bcryptjs';
import { Router } from 'express';

import { asyncRoute } from '../middleware/errorHandler.js';
import { requireAuth, signToken } from '../middleware/auth.js';
import { createUser, findUserByPhone } from '../store/index.js';

export const authRouter = Router();

const PHONE_PATTERN = /^[6-9]\d{9}$/;

function validateCredentials({ phone, password }) {
  if (!PHONE_PATTERN.test(String(phone || ''))) {
    const error = new Error('Phone must be a 10-digit Indian mobile number');
    error.statusCode = 400;
    throw error;
  }
  if (!password || String(password).length < 6) {
    const error = new Error('Password must be at least 6 characters');
    error.statusCode = 400;
    throw error;
  }
}

authRouter.post(
  '/register',
  asyncRoute(async (req, res) => {
    const { name, phone, password, preferredLanguage, location, crops } = req.body || {};

    if (!name || !String(name).trim()) {
      return res.status(400).json({ error: 'Name is required' });
    }
    validateCredentials({ phone, password });

    if (await findUserByPhone(phone)) {
      return res.status(409).json({ error: 'Phone number already registered' });
    }

    const user = await createUser({
      name: String(name).trim(),
      phone: String(phone),
      passwordHash: await bcrypt.hash(String(password), 10),
      preferredLanguage: preferredLanguage === 'en' ? 'en' : 'hi',
      location: location || {},
      crops: Array.isArray(crops) ? crops : [],
    });

    return res.status(201).json({ user, token: signToken(user.id) });
  }),
);

authRouter.post(
  '/login',
  asyncRoute(async (req, res) => {
    const { phone, password } = req.body || {};
    const user = await findUserByPhone(String(phone || ''), { withPassword: true });

    // The same message for an unknown phone and a wrong password, so the
    // endpoint cannot be used to enumerate registered numbers.
    const invalid = () => res.status(401).json({ error: 'Invalid phone number or password' });

    if (!user) return invalid();
    const matches = await bcrypt.compare(String(password || ''), user.passwordHash || '');
    if (!matches) return invalid();

    delete user.passwordHash;
    return res.json({ user, token: signToken(user.id) });
  }),
);

authRouter.get(
  '/me',
  requireAuth,
  asyncRoute(async (req, res) => {
    res.json({ user: req.user });
  }),
);
