import { Router } from 'express';

import { asyncRoute } from '../middleware/errorHandler.js';
import { requireAuth } from '../middleware/auth.js';
import {
  createAlert,
  deleteAlert,
  getAlert,
  listAlerts,
  shouldTrigger,
  updateAlert,
} from '../store/alerts.js';
import { fetchMandiPrices } from '../services/aiClient.js';
import { withCache } from '../services/mandiCache.js';

export const alertsRouter = Router();

alertsRouter.use(requireAuth);

alertsRouter.get(
  '/',
  asyncRoute(async (req, res) => {
    const alerts = await listAlerts({ farmer: req.user.id, status: req.query.status });
    res.json({ count: alerts.length, alerts });
  }),
);

alertsRouter.post(
  '/',
  asyncRoute(async (req, res) => {
    const { crop, targetPrice, direction, state, district, notifyBy } = req.body || {};

    if (!crop || !String(crop).trim()) {
      return res.status(400).json({ error: 'crop is required' });
    }
    const target = Number(targetPrice);
    if (!Number.isFinite(target) || target <= 0) {
      return res.status(400).json({ error: 'targetPrice must be a positive number' });
    }
    if (direction && !['above', 'below'].includes(direction)) {
      return res.status(400).json({ error: "direction must be 'above' or 'below'" });
    }

    const alert = await createAlert({
      farmer: req.user.id,
      crop: String(crop).trim(),
      targetPrice: target,
      direction: direction || 'above',
      notifyBy: notifyBy === 'whatsapp' ? 'whatsapp' : 'app',
      // Fall back to the farmer's own district, which is what they almost
      // always mean when they do not name one.
      state: state ?? req.user.location?.state,
      district: district ?? req.user.location?.district,
    });

    return res.status(201).json({ alert });
  }),
);

/** Evaluate the caller's alerts against current prices. */
alertsRouter.post(
  '/check',
  asyncRoute(async (req, res) => {
    const alerts = await listAlerts({ farmer: req.user.id, status: 'active' });
    const triggered = [];

    for (const alert of alerts) {
      const params = { crop: alert.crop, state: alert.state, district: alert.district, limit: 50 };
      const { value: records } = await withCache('prices', params, () => fetchMandiPrices(params));

      if (!records?.length) {
        await updateAlert(alert.id, { lastCheckedAt: new Date() });
        continue;
      }

      // `above` watches the best price available; `below` watches the cheapest.
      const prices = records.map((r) => r.modal_price).filter(Number.isFinite);
      const observed =
        alert.direction === 'below' ? Math.min(...prices) : Math.max(...prices);

      const fired = shouldTrigger(alert, observed);
      const updated = await updateAlert(alert.id, {
        lastCheckedAt: new Date(),
        lastSeenPrice: observed,
        ...(fired ? { status: 'triggered', triggeredAt: new Date() } : {}),
      });

      if (fired) {
        const best = records.find((r) => r.modal_price === observed);
        triggered.push({ alert: updated, price: observed, market: best?.market, district: best?.district });
      }
    }

    res.json({ checked: alerts.length, triggered });
  }),
);

alertsRouter.patch(
  '/:id',
  asyncRoute(async (req, res) => {
    const alert = await getAlert(req.params.id);
    if (!alert) return res.status(404).json({ error: 'Alert not found' });
    if (String(alert.farmer) !== String(req.user.id)) {
      return res.status(403).json({ error: 'That alert belongs to someone else' });
    }

    const updates = {};
    if (req.body?.targetPrice !== undefined) {
      const target = Number(req.body.targetPrice);
      if (!Number.isFinite(target) || target <= 0) {
        return res.status(400).json({ error: 'targetPrice must be a positive number' });
      }
      updates.targetPrice = target;
    }
    if (req.body?.status !== undefined) {
      if (!['active', 'paused', 'triggered'].includes(req.body.status)) {
        return res.status(400).json({ error: 'invalid status' });
      }
      updates.status = req.body.status;
    }
    if (Object.keys(updates).length === 0) {
      return res.status(400).json({ error: 'No updatable fields supplied' });
    }

    return res.json({ alert: await updateAlert(req.params.id, updates) });
  }),
);

alertsRouter.delete(
  '/:id',
  asyncRoute(async (req, res) => {
    const alert = await getAlert(req.params.id);
    if (!alert) return res.status(404).json({ error: 'Alert not found' });
    if (String(alert.farmer) !== String(req.user.id)) {
      return res.status(403).json({ error: 'That alert belongs to someone else' });
    }
    await deleteAlert(req.params.id);
    return res.status(204).end();
  }),
);
