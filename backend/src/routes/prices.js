import { Router } from 'express';

import { asyncRoute } from '../middleware/errorHandler.js';
import { withCache } from '../services/mandiCache.js';
import { fetchForecast, fetchSeries, fetchTrend, fetchWeather } from '../services/aiClient.js';

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

/** Trained multi-step price forecast (§6.3). */
pricesRouter.get(
  '/forecast',
  asyncRoute(async (req, res) => {
    if (!req.query.crop) {
      return res.status(400).json({ error: 'crop is required' });
    }

    const params = {
      crop: req.query.crop,
      state: req.query.state,
      district: req.query.district,
      horizon: Math.min(Number.parseInt(req.query.horizon, 10) || 7, 30),
    };

    const { value, cached } = await withCache('forecast', params, () => fetchForecast(params));
    res.set('X-Cache', cached ? 'HIT' : 'MISS');
    return res.json(value);
  }),
);

/** Weather outlook and its implication for supply (§6.3). */
pricesRouter.get(
  '/weather',
  asyncRoute(async (req, res) => {
    const params = {
      state: req.query.state,
      district: req.query.district,
      crop: req.query.crop,
      days: Math.min(Number.parseInt(req.query.days, 10) || 7, 16),
    };

    const { value, cached } = await withCache('weather', params, () => fetchWeather(params));
    res.set('X-Cache', cached ? 'HIT' : 'MISS');
    return res.json(value);
  }),
);
