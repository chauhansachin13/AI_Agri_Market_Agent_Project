import { Router } from 'express';

import { asyncRoute } from '../middleware/errorHandler.js';
import { withCache } from '../services/mandiCache.js';
import { fetchSeries, fetchTrend } from '../services/aiClient.js';

export const pricesRouter = Router();

/** EMA trend classification for one crop-location pair. */
pricesRouter.get(
  '/trend',
  asyncRoute(async (req, res) => {
    if (!req.query.crop) {
      return res.status(400).json({ error: 'crop is required' });
    }

    const params = {
      crop: req.query.crop,
      state: req.query.state,
      district: req.query.district,
      days: Math.min(Number.parseInt(req.query.days, 10) || 45, 365),
    };

    const { value, cached } = await withCache('trend', params, () => fetchTrend(params));
    res.set('X-Cache', cached ? 'HIT' : 'MISS');
    return res.json(value);
  }),
);

/** Daily modal price series backing the frontend trend chart. */
pricesRouter.get(
  '/series',
  asyncRoute(async (req, res) => {
    if (!req.query.crop) {
      return res.status(400).json({ error: 'crop is required' });
    }

    const params = {
      crop: req.query.crop,
      state: req.query.state,
      district: req.query.district,
      days: Math.min(Number.parseInt(req.query.days, 10) || 45, 365),
    };

    const { value, cached } = await withCache('series', params, () => fetchSeries(params));
    res.set('X-Cache', cached ? 'HIT' : 'MISS');
    return res.json(value);
  }),
);
