// src/utils/format.js

export const fmt = {
  pct: (v, decimals = 1) =>
    v == null ? '—' : `${v >= 0 ? '+' : ''}${Number(v).toFixed(decimals)}%`,

  eur: (v, decimals = 2) =>
    v == null ? '—' : `${v >= 0 ? '+' : ''}€${Math.abs(Number(v)).toFixed(decimals)}`,

  signed: (v, decimals = 2) =>
    v == null ? '—' : `${v >= 0 ? '+' : '−'}${Math.abs(Number(v)).toFixed(decimals)}`,

  price: (v) => {
    if (v == null) return '—';
    const n = Number(v);
    if (n > 1000) return n.toLocaleString('en-US', { maximumFractionDigits: 2 });
    if (n > 10)   return n.toFixed(3);
    return n.toFixed(5);
  },

  prob: (v) => v == null ? '—' : `${Number(v).toFixed(1)}%`,

  time: (d) => {
    if (!d) return '';
    const dt = typeof d === 'string' ? new Date(d) : d;
    return dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  },

  date: (d) => {
    if (!d) return '';
    const dt = typeof d === 'string' ? new Date(d) : d;
    return dt.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
  },

  countdown: (secs) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return m > 0 ? `${m}m ${s}s` : `${s}s`;
  },

  sharpe: (v) => v == null ? '—' : Number(v).toFixed(2),
};

export function actionColor(action) {
  switch (action) {
    case 'BUY':      return 'var(--accent-green)';
    case 'SELL':     return 'var(--accent-red)';
    default:         return 'var(--text-muted)';
  }
}

export function actionBg(action) {
  switch (action) {
    case 'BUY':      return 'rgba(16,185,129,0.12)';
    case 'SELL':     return 'rgba(239,68,68,0.12)';
    default:         return 'rgba(74,85,104,0.15)';
  }
}

export function evColor(ev) {
  if (ev == null) return 'var(--text-muted)';
  if (ev > 0.5)   return 'var(--accent-green)';
  if (ev < -0.5)  return 'var(--accent-red)';
  return 'var(--text-secondary)';
}

export function confColor(tier) {
  switch (tier) {
    case 'HIGH':   return 'var(--accent-green)';
    case 'MEDIUM': return 'var(--accent-amber)';
    default:       return 'var(--text-muted)';
  }
}

export function sentimentLabel(score) {
  if (score > 0.2)  return { label: 'Bullish', color: 'var(--accent-green)' };
  if (score < -0.2) return { label: 'Bearish', color: 'var(--accent-red)' };
  return { label: 'Neutral', color: 'var(--text-secondary)' };
}

export const ASSET_META = {
  'XAU/USD':    { icon: '⚡', color: '#f59e0b', label: 'Gold' },
  'GBP/JPY':    { icon: '₿', color: '#06b6d4', label: 'GBP/JPY' },
  'NASDAQ100':  { icon: '📈', color: '#8b5cf6', label: 'NDX 100' },
};
