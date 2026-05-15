// src/utils/api.js
const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  // GET /assets - list all supported assets + model status
  getAssets: () => request('/assets'),

  // GET /predict/all/signals - predictions for all assets at once
  getAllSignals: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/predict/all/signals${qs ? '?' + qs : ''}`);
  },

  // GET /predict/:asset - single asset prediction
  getSingleSignal: (asset, params = {}) => {
    const qs = new URLSearchParams(params).toString();
    const encoded = encodeURIComponent(asset);
    return request(`/predict/${encoded}${qs ? '?' + qs : ''}`);
  },

  // POST /backtest/:asset - run historical backtest
  runBacktest: (asset, body) =>
    request(`/backtest/${encodeURIComponent(asset)}`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  // POST /retrain - trigger model retraining
  retrain: (asset = null) =>
    request('/retrain', {
      method: 'POST',
      body: JSON.stringify({ asset }),
    }),

  // GET /model-status
  getModelStatus: () => request('/model-status'),

  // GET /health
  health: () => fetch(`${BASE.replace('/api', '')}/health`).then(r => r.json()),
};

// Signal history endpoints
export const signalApi = {
  getSignalHistory: (params = {}) => {
    const clean = Object.fromEntries(Object.entries(params).filter(([,v]) => v != null));
    const qs = new URLSearchParams(clean).toString();
    return request(`/signals/history${qs ? '?' + qs : ''}`);
  },
  getSignalStats: () => request('/signals/stats'),
};

// Trade endpoints
export const tradeApi = {
  getTrades: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/trades${qs ? '?' + qs : ''}`);
  },
  createTrade: (body) =>
    request('/trades', { method: 'POST', body: JSON.stringify(body) }),
  getTradeStats: () => request('/trades/stats'),
  deleteTrade: (id) =>
    request(`/trades/${id}`, { method: 'DELETE' }),
};

// Attach to main api object too for convenience
Object.assign(api, signalApi, tradeApi);
