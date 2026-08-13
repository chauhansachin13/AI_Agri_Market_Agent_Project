import './setup-env.js';

import express from 'express';

import { createApp } from '../src/app.js';
import { invalidateCache } from '../src/services/mandiCache.js';
import { resetMarketplace } from '../src/store/marketplace.js';
import { resetMemoryStore } from '../src/store/index.js';

let server;
let baseUrl;
let stubServer;

export async function startTestServer() {
  if (server) return baseUrl;
  const app = createApp();
  await new Promise((resolve) => {
    server = app.listen(0, resolve);
  });
  baseUrl = `http://127.0.0.1:${server.address().port}`;
  return baseUrl;
}

export async function stopTestServer() {
  if (server) {
    await new Promise((resolve) => server.close(resolve));
    server = undefined;
    baseUrl = undefined;
  }
}

/**
 * A stand-in for the Python AI service.
 *
 * The gateway's job is routing, caching, persistence and auth — not inference.
 * Pointing it at a stub that speaks the Section 4.7 schema tests exactly that,
 * without needing the Python service running. `calls` records what the gateway
 * forwarded, so the tests can assert on it.
 */
export async function startStubAiService({ failWith } = {}) {
  const calls = [];
  const app = express();
  app.use(express.json());

  app.get('/health', (_req, res) => res.json({ status: 'ok', version: 'stub' }));

  app.post('/agent/query', (req, res) => {
    calls.push({ path: '/agent/query', body: req.body });
    if (failWith) return res.status(failWith).json({ detail: 'stub failure' });
    return res.json({
      intent: 'price_query',
      crop: 'Wheat',
      location: 'Patna, Bihar',
      live_mandi_prices: [
        {
          state: 'Bihar',
          district: 'Patna',
          market: 'Patna City',
          commodity: 'Wheat',
          variety: 'Other',
          grade: 'FAQ',
          arrival_date: '2026-08-01',
          min_price: 2250,
          max_price: 2350,
          modal_price: 2300,
          price_range: 100,
          source: 'agmarknet',
        },
      ],
      buyers: [],
      best_mandi: 'Patna City, Patna',
      trend_analysis: {
        direction: 'stable',
        ema_7: 2300,
        ema_14: 2300,
        ema_30: 2300,
        volatility: 0.01,
        confidence: 0.6,
        samples: 30,
      },
      prediction: { recommendation: 'WAIT', confidence: 0.62, reason: 'prices are flat' },
      confidence_score: 0.78,
      fact_check_status: 'verified',
      fact_check_claims: [],
      english_answer: 'Wheat is Rs 2300 per quintal at Patna City mandi.',
      hindi_answer: 'पटना सिटी मंडी में गेहूं का भाव 2300 रुपये प्रति क्विंटल है।',
      reasoning_steps: ['Intent Detection: price_query', 'Mandi Intelligence: 1 record'],
      retrieved_context: [],
      search_snippets: [],
      elapsed_ms: 42,
      degraded: false,
    });
  });

  app.post('/nlp/parse', (req, res) => {
    calls.push({ path: '/nlp/parse', body: req.body });
    res.json({
      language: 'en',
      intent: 'price_query',
      intent_confidence: 0.8,
      crop: 'Wheat',
      crop_hindi: 'गेहूं',
      quantity_value: null,
      quantity_unit: null,
      location: { state: 'Bihar', district: 'Patna', resolved_by: 'text', confidence: 0.95 },
    });
  });

  app.get('/mandi/prices', (req, res) => {
    calls.push({ path: '/mandi/prices', query: req.query });
    res.json([
      {
        state: 'Bihar',
        district: 'Patna',
        market: 'Patna City',
        commodity: req.query.crop || 'Wheat',
        variety: 'Other',
        grade: 'FAQ',
        arrival_date: '2026-08-01',
        min_price: 2250,
        max_price: 2350,
        modal_price: 2300,
        price_range: 100,
        source: 'agmarknet',
      },
    ]);
  });

  app.get('/mandi/buyers', (req, res) => {
    calls.push({ path: '/mandi/buyers', query: req.query });
    res.json([
      {
        apmc_name: 'Patna City APMC',
        state: 'Bihar',
        district: 'Patna',
        address: 'Patna City Yard',
        contact: '06123456789',
        trading_hours: '06:00 - 14:00 IST',
        commodities: ['Wheat'],
        source: 'enam',
      },
    ]);
  });

  app.get('/mandi/trend', (req, res) => {
    calls.push({ path: '/mandi/trend', query: req.query });
    res.json({
      direction: 'upward',
      ema_7: 2400,
      ema_14: 2350,
      ema_30: 2300,
      volatility: 0.02,
      confidence: 0.71,
      samples: 45,
    });
  });

  app.get('/mandi/series', (req, res) => {
    calls.push({ path: '/mandi/series', query: req.query });
    res.json({
      crop: req.query.crop,
      state: req.query.state ?? null,
      district: req.query.district ?? null,
      points: [
        { date: '2026-07-30', modal_price: 2280 },
        { date: '2026-07-31', modal_price: 2290 },
        { date: '2026-08-01', modal_price: 2300 },
      ],
    });
  });

  await new Promise((resolve) => {
    stubServer = app.listen(0, resolve);
  });

  process.env.AI_SERVICE_URL = `http://127.0.0.1:${stubServer.address().port}`;
  return { calls, url: process.env.AI_SERVICE_URL };
}

export async function stopStubAiService() {
  if (stubServer) {
    await new Promise((resolve) => stubServer.close(resolve));
    stubServer = undefined;
  }
}

export function resetStore() {
  resetMemoryStore();
  resetMarketplace();
  invalidateCache();
}

export async function api(path, { method = 'GET', body, token } = {}) {
  const headers = {};
  if (body) headers['Content-Type'] = 'application/json';
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetch(`${baseUrl}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  const text = await response.text();
  let data;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  return { status: response.status, headers: response.headers, data };
}

export const validFarmer = {
  name: 'Ramesh Kumar',
  phone: '9876543210',
  password: 'mandi123',
  preferredLanguage: 'hi',
  location: { state: 'Bihar', district: 'Patna', pincode: '800001' },
  crops: ['Wheat', 'Potato'],
};

export async function registerFarmer(overrides = {}) {
  const { data } = await api('/api/auth/register', {
    method: 'POST',
    body: { ...validFarmer, ...overrides },
  });
  return data;
}
