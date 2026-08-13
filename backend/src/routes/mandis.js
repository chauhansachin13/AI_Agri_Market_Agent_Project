import { Router } from 'express';

import { asyncRoute } from '../middleware/errorHandler.js';
import { cacheStats, withCache } from '../services/mandiCache.js';
import { fetchBuyers, fetchMandiPrices } from '../services/aiClient.js';

export const mandisRouter = Router();

/** Cached mandi price records for the dashboard. */
mandisRouter.get(
  '/',
  asyncRoute(async (req, res) => {
    const params = {
      crop: req.query.crop,
      state: req.query.state,
      district: req.query.district,
      limit: Math.min(Number.parseInt(req.query.limit, 10) || 50, 200),
    };

    const { value, cached } = await withCache('prices', params, () => fetchMandiPrices(params));
    res.set('X-Cache', cached ? 'HIT' : 'MISS');
    res.json({ cached, count: value.length, records: value });
  }),
);

/** APMC and buyer contacts, serving the buyer_search intent. */
mandisRouter.get(
  '/buyers',
  asyncRoute(async (req, res) => {
    const params = {
      state: req.query.state,
      district: req.query.district,
      crop: req.query.crop,
    };

    const { value, cached } = await withCache('buyers', params, () => fetchBuyers(params));
    res.set('X-Cache', cached ? 'HIT' : 'MISS');
    res.json({ cached, count: value.length, buyers: value });
  }),
);

mandisRouter.get('/cache-stats', (_req, res) => {
  res.json(cacheStats());
});
