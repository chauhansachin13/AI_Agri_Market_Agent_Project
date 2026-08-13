import { Router } from 'express';

import { asyncRoute } from '../middleware/errorHandler.js';
import { requireAuth } from '../middleware/auth.js';
import { updateUser } from '../store/index.js';

export const usersRouter = Router();

usersRouter.get('/profile', requireAuth, (req, res) => {
  res.json({ user: req.user });
});

usersRouter.patch(
  '/profile',
  requireAuth,
  asyncRoute(async (req, res) => {
    const { name, preferredLanguage, location, crops } = req.body || {};

    // Only profile fields are accepted — phone and password hash are not
    // editable here, so a crafted body cannot take over an account.
    const updates = {};
    if (name !== undefined) updates.name = String(name).trim();
    if (preferredLanguage !== undefined) {
      if (!['hi', 'en'].includes(preferredLanguage)) {
        return res.status(400).json({ error: 'preferredLanguage must be "hi" or "en"' });
      }
      updates.preferredLanguage = preferredLanguage;
    }
    if (location !== undefined) {
      const { state, district, pincode } = location || {};
      if (pincode && !/^[1-9]\d{5}$/.test(String(pincode))) {
        return res.status(400).json({ error: 'Invalid pincode' });
      }
      updates.location = { state, district, pincode };
    }
    if (crops !== undefined) {
      if (!Array.isArray(crops)) {
        return res.status(400).json({ error: 'crops must be an array' });
      }
      updates.crops = crops.map(String);
    }

    if (Object.keys(updates).length === 0) {
      return res.status(400).json({ error: 'No updatable fields supplied' });
    }

    const user = await updateUser(req.user.id, updates);
    return res.json({ user });
  }),
);
