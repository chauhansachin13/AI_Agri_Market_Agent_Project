import axios from 'axios';

import { config } from '../config/index.js';

let cached = { url: null, instance: null };

/**
 * The axios instance, rebuilt if the target URL changes.
 *
 * Resolving lazily rather than at import time means the service address can be
 * set after this module is loaded — which is what the test harness does, and
 * what a late-loading secrets provider would do in deployment.
 */
/**
 * Some platforms expose a linked service as a bare `host:port` with no scheme —
 * Render's `fromService` is one. Axios treats that as a relative URL and every
 * call fails confusingly, so the scheme is filled in here: localhost over http,
 * anything else over https.
 */
function normaliseServiceUrl(value) {
  if (!value) return value;
  if (/^https?:\/\//i.test(value)) return value;
  const local = /^(localhost|127\.0\.0\.1|\[::1\])(:|$)/i.test(value);
  return `${local ? 'http' : 'https'}://${value}`;
}

function client() {
  const url = normaliseServiceUrl(process.env.AI_SERVICE_URL || config.aiServiceUrl);
  if (cached.url !== url) {
    cached = {
      url,
      instance: axios.create({
        baseURL: url,
        timeout: config.aiServiceTimeoutMs,
        headers: { 'Content-Type': 'application/json' },
      }),
    };
  }
  return cached.instance;
}

function wrapError(error, action) {
  const status = error.response?.status;
  const detail = error.response?.data?.detail || error.message;
  const wrapped = new Error(`AI service ${action} failed: ${detail}`);
  // A timeout or a downed AI service is a gateway problem, not the client's.
  wrapped.statusCode = status && status < 500 ? status : 502;
  return wrapped;
}

/** Run the full multi-agent pipeline over a farmer query. */
export async function runAgentQuery(payload) {
  try {
    const { data } = await client().post('/agent/query', payload);
    return data;
  } catch (error) {
    throw wrapError(error, 'query');
  }
}

/** Parse a query through the NLP pipeline without running the agents. */
export async function parseQuery(payload) {
  try {
    const { data } = await client().post('/nlp/parse', payload);
    return data;
  } catch (error) {
    throw wrapError(error, 'parse');
  }
}

export async function fetchMandiPrices(params) {
  try {
    const { data } = await client().get('/mandi/prices', { params });
    return data;
  } catch (error) {
    throw wrapError(error, 'price lookup');
  }
}

export async function fetchBuyers(params) {
  try {
    const { data } = await client().get('/mandi/buyers', { params });
    return data;
  } catch (error) {
    throw wrapError(error, 'buyer lookup');
  }
}

export async function fetchTrend(params) {
  try {
    const { data } = await client().get('/mandi/trend', { params });
    return data;
  } catch (error) {
    throw wrapError(error, 'trend lookup');
  }
}

export async function fetchSeries(params) {
  try {
    const { data } = await client().get('/mandi/series', { params });
    return data;
  } catch (error) {
    throw wrapError(error, 'series lookup');
  }
}

export async function health() {
  try {
    const { data } = await client().get('/health', { timeout: 5000 });
    return { reachable: true, ...data };
  } catch (error) {
    return { reachable: false, error: error.message };
  }
}

export { normaliseServiceUrl };

export async function fetchForecast(params) {
  try {
    const { data } = await client().get('/mandi/forecast', { params });
    return data;
  } catch (error) {
    throw wrapError(error, 'forecast');
  }
}

export async function fetchWeather(params) {
  try {
    const { data } = await client().get('/weather/outlook', { params });
    return data;
  } catch (error) {
    throw wrapError(error, 'weather lookup');
  }
}

export async function fetchLanguages() {
  try {
    const { data } = await client().get('/languages');
    return data;
  } catch (error) {
    throw wrapError(error, 'language lookup');
  }
}
