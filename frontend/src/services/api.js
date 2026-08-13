import axios from 'axios';

const client = axios.create({
  baseURL: import.meta.env?.VITE_API_URL || '/api',
  timeout: 40000,
  headers: { 'Content-Type': 'application/json' },
});

const TOKEN_KEY = 'agri.token';

export const tokenStore = {
  get: () => {
    try {
      return localStorage.getItem(TOKEN_KEY);
    } catch {
      return null; // private browsing, or storage disabled
    }
  },
  set: (token) => {
    try {
      if (token) localStorage.setItem(TOKEN_KEY, token);
      else localStorage.removeItem(TOKEN_KEY);
    } catch {
      /* non-fatal: the session simply will not survive a reload */
    }
  },
};

client.interceptors.request.use((request) => {
  const token = tokenStore.get();
  if (token) request.headers.Authorization = `Bearer ${token}`;
  return request;
});

client.interceptors.response.use(
  (response) => response,
  (error) => {
    // Surface the server's message rather than axios's generic status text.
    const message =
      error.response?.data?.error || error.response?.data?.detail || error.message;
    if (error.response?.status === 401) tokenStore.set(null);
    return Promise.reject(new Error(message));
  },
);

// --- auth -------------------------------------------------------------------
export const register = (payload) => client.post('/auth/register', payload).then((r) => r.data);
export const login = (payload) => client.post('/auth/login', payload).then((r) => r.data);
export const me = () => client.get('/auth/me').then((r) => r.data);

// --- queries ----------------------------------------------------------------
export const askAgent = (payload) => client.post('/queries', payload).then((r) => r.data);
export const parseQuery = (query) => client.post('/queries/parse', { query }).then((r) => r.data);
export const queryHistory = (limit = 20) =>
  client.get('/queries/history', { params: { limit } }).then((r) => r.data);

// --- market data ------------------------------------------------------------
export const mandiPrices = (params) => client.get('/mandis', { params }).then((r) => r.data);
export const mandiBuyers = (params) => client.get('/mandis/buyers', { params }).then((r) => r.data);
export const priceTrend = (params) => client.get('/prices/trend', { params }).then((r) => r.data);
export const priceSeries = (params) => client.get('/prices/series', { params }).then((r) => r.data);

// --- forecasting and weather (§6.3) -----------------------------------------
export const priceForecast = (params) =>
  client.get('/prices/forecast', { params }).then((r) => r.data);
export const weatherOutlook = (params) =>
  client.get('/prices/weather', { params }).then((r) => r.data);
export const supportedLanguages = () => client.get('/queries/languages').then((r) => r.data);

// --- marketplace (§6.3) ------------------------------------------------------
export const listListings = (params) =>
  client.get('/market/listings', { params }).then((r) => r.data);
export const getListing = (id) => client.get(`/market/listings/${id}`).then((r) => r.data);
export const createListing = (payload) =>
  client.post('/market/listings', payload).then((r) => r.data);
export const updateListing = (id, payload) =>
  client.patch(`/market/listings/${id}`, payload).then((r) => r.data);
export const makeOffer = (id, payload) =>
  client.post(`/market/listings/${id}/offers`, payload).then((r) => r.data);
export const acceptOffer = (id) =>
  client.post(`/market/offers/${id}/accept`).then((r) => r.data);
export const rejectOffer = (id) =>
  client.post(`/market/offers/${id}/reject`).then((r) => r.data);
export const withdrawOffer = (id) =>
  client.post(`/market/offers/${id}/withdraw`).then((r) => r.data);
export const myOffers = () => client.get('/market/offers/mine').then((r) => r.data);

// --- profile ----------------------------------------------------------------
export const updateProfile = (payload) =>
  client.patch('/users/profile', payload).then((r) => r.data);

export default client;
