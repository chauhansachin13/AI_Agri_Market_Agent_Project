import { Router } from 'express';

import { asyncRoute } from '../middleware/errorHandler.js';
import { optionalAuth, requireAuth } from '../middleware/auth.js';
import { listQueries, queryStats, saveQuery } from '../store/index.js';
import { fetchLanguages, parseQuery, runAgentQuery } from '../services/aiClient.js';

export const queriesRouter = Router();

/**
 * Submit a farmer query.
 *
 * The gateway forwards it to the AI service, persists the interaction, and
 * returns the agent response unchanged — the frontend is written against the
 * Section 4.7 schema, so the gateway must not reshape it.
 */
queriesRouter.post(
  '/',
  optionalAuth,
  asyncRoute(async (req, res) => {
    const { query, coordinates, pincode, sessionId, languageOverride, profile: personalisation } =
      req.body || {};

    if (!query || !String(query).trim()) {
      return res.status(400).json({ error: 'Query text is required' });
    }

    const profile = req.user?.location || {};
    const response = await runAgentQuery({
      query: String(query).trim(),
      coordinates: coordinates || null,
      // A pincode saved on the profile is a better default than nothing, but an
      // explicit one in the request always wins.
      pincode: pincode || profile.pincode || null,
      ip_address: req.ip,
      session_id: sessionId || null,
      // An explicit 'auto' means the farmer asked for detection, so the stored
      // profile preference must not quietly override it.
      language_override:
        languageOverride === 'auto'
          ? null
          : languageOverride || req.user?.preferredLanguage || null,
      // Personalisation is supplied per request and forwarded straight through;
      // the gateway does not store it, which is what keeps it local (§6.3).
      profile: personalisation
        ? {
            ...personalisation,
            crops: personalisation.crops ?? req.user?.crops ?? [],
          }
        : null,
    });

    await saveQuery({
      user: req.user?.id,
      sessionId: sessionId || null,
      text: String(query).trim(),
      intent: response.intent,
      entities: {
        crop: response.crop,
        state: profile.state,
        district: profile.district,
      },
      englishAnswer: response.english_answer,
      hindiAnswer: response.hindi_answer,
      recommendation: response.prediction?.recommendation,
      confidenceScore: response.confidence_score,
      factCheckStatus: response.fact_check_status,
      reasoningSteps: response.reasoning_steps,
      degraded: response.degraded,
      elapsedMs: response.elapsed_ms,
    });

    return res.json(response);
  }),
);

/** Parse a query without running the agents — used by the frontend for hints. */
queriesRouter.post(
  '/parse',
  asyncRoute(async (req, res) => {
    const { query } = req.body || {};
    if (!query || !String(query).trim()) {
      return res.status(400).json({ error: 'Query text is required' });
    }
    res.json(await parseQuery({ query: String(query).trim() }));
  }),
);

queriesRouter.get(
  '/history',
  requireAuth,
  asyncRoute(async (req, res) => {
    const limit = Math.min(Number.parseInt(req.query.limit, 10) || 20, 100);
    res.json(await listQueries({ userId: req.user.id, limit }));
  }),
);

queriesRouter.get(
  '/stats',
  asyncRoute(async (_req, res) => {
    res.json(await queryStats());
  }),
);

/** The languages the assistant can answer in (§6.3). */
queriesRouter.get(
  '/languages',
  asyncRoute(async (_req, res) => {
    res.json(await fetchLanguages());
  }),
);
