// src/components/SignalHistory.jsx — logged signals from SQLite DB
import { useState, useEffect, useCallback } from 'react';
import { Database, RefreshCw, TrendingUp, TrendingDown, Filter } from 'lucide-react';
import { api } from '../utils/api';
import { fmt } from '../utils/format';

const ASSET_OPTIONS = ['ALL', 'XAU/USD', 'GBP/JPY', 'NASDAQ100'];
const ACTION_OPTIONS = ['ALL', 'BUY', 'SELL'];

function StatPill({ label, value, color }) {
  return (
    <div style={{ background: 'var(--bg-base)', border: '1px solid var(--border)',
      borderRadius: 8, padding: '10px 16px', minWidth: 120 }}>
      <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 16, fontFamily: 'var(--font-mono)', fontWeight: 700,
        color: color || 'var(--text-primary)' }}>{value}</div>
    </div>
  );
}

export default function SignalHistory() {
  const [signals, setSignals]     = useState([]);
  const [stats, setStats]         = useState(null);
  const [loading, setLoading]     = useState(true);
  const [assetFilter, setAsset]   = useState('ALL');
  const [actionFilter, setAction] = useState('ALL');
  const [page, setPage]           = useState(0);
  const PER_PAGE = 25;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [hist, st] = await Promise.all([
        api.getSignalHistory({
          asset:  assetFilter  !== 'ALL' ? assetFilter  : undefined,
          action: actionFilter !== 'ALL' ? actionFilter : undefined,
          limit:  PER_PAGE,
          offset: page * PER_PAGE,
        }),
        api.getSignalStats(),
      ]);
      setSignals(hist.signals);
      setStats(st);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [assetFilter, actionFilter, page]);

  useEffect(() => { load(); }, [load]);

  return (
    <div style={{ padding: '0 24px 40px' }}>
      {/* Header */}
      <div style={{ marginBottom: 20, display: 'flex', alignItems: 'center',
        justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h2 style={{ fontSize: 16, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Database size={16} color="var(--accent-cyan)" /> Signal History
          </h2>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
            Auto-saved signals — only BUY/SELL with prob ≥ 60% and net profit &gt; 3× fee
          </p>
        </div>
        <button onClick={load} style={{ background: 'var(--bg-elevated)',
          border: '1px solid var(--border)', borderRadius: 8, padding: '7px 14px',
          color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', fontSize: 12,
          display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
          <RefreshCw size={12} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
          REFRESH
        </button>
      </div>

      {/* Stats pills */}
      {stats && (
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 20 }}>
          <StatPill label="TOTAL SIGNALS" value={stats.total_signals} color="var(--accent-blue)" />
          <StatPill label="LAST SIGNAL" value={stats.last_signal_at
            ? new Date(stats.last_signal_at).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})
            : '—'} />
          {stats.by_asset?.map(a => (
            <StatPill key={a.asset} label={a.asset}
              value={`${a.count} (${a.buys}↑ ${a.sells}↓)`}
              color="var(--accent-cyan)" />
          ))}
        </div>
      )}

      {/* Filters */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap',
        alignItems: 'center' }}>
        <Filter size={13} color="var(--text-muted)" />
        {ASSET_OPTIONS.map(a => (
          <button key={a} onClick={() => { setAsset(a); setPage(0); }} style={{
            background: assetFilter === a ? 'var(--accent-blue)' : 'var(--bg-elevated)',
            border: `1px solid ${assetFilter === a ? 'var(--accent-blue)' : 'var(--border)'}`,
            borderRadius: 6, padding: '4px 12px', color: assetFilter === a ? 'white' : 'var(--text-muted)',
            fontFamily: 'var(--font-mono)', fontSize: 11, cursor: 'pointer' }}>
            {a}
          </button>
        ))}
        <div style={{ width: 1, height: 18, background: 'var(--border)' }} />
        {ACTION_OPTIONS.map(a => (
          <button key={a} onClick={() => { setAction(a); setPage(0); }} style={{
            background: actionFilter === a
              ? (a === 'BUY' ? 'rgba(16,185,129,0.2)' : a === 'SELL' ? 'rgba(239,68,68,0.2)' : 'var(--accent-blue)')
              : 'var(--bg-elevated)',
            border: `1px solid ${actionFilter === a
              ? (a === 'BUY' ? 'var(--accent-green)' : a === 'SELL' ? 'var(--accent-red)' : 'var(--accent-blue)')
              : 'var(--border)'}`,
            borderRadius: 6, padding: '4px 12px',
            color: actionFilter === a
              ? (a === 'BUY' ? 'var(--accent-green)' : a === 'SELL' ? 'var(--accent-red)' : 'white')
              : 'var(--text-muted)',
            fontFamily: 'var(--font-mono)', fontSize: 11, cursor: 'pointer' }}>
            {a}
          </button>
        ))}
      </div>

      {/* Table */}
      {signals.length === 0 && !loading ? (
        <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--text-muted)' }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>📭</div>
          <div style={{ fontSize: 14 }}>No signals saved yet</div>
          <div style={{ fontSize: 12, marginTop: 6 }}>
            Signals appear here automatically when conditions are met during prediction.
          </div>
        </div>
      ) : (
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius-lg)', overflow: 'hidden' }}>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg-base)' }}>
                  {['TIME','ASSET','ACTION','WIN PROB','POSITION','RISK','NET PROFIT','EV','STOP LOSS','PRICE','HORIZON'].map(h => (
                    <th key={h} style={{ padding: '10px 12px', textAlign: 'left',
                      fontFamily: 'var(--font-mono)', fontSize: 9, letterSpacing: '0.07em',
                      color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {signals.map((s, i) => (
                  <tr key={s.id} style={{
                    borderBottom: '1px solid rgba(255,255,255,0.03)',
                    background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.01)',
                  }}>
                    <td style={{ padding: '9px 12px', color: 'var(--text-muted)',
                      fontFamily: 'var(--font-mono)', fontSize: 10, whiteSpace: 'nowrap' }}>
                      {new Date(s.logged_at).toLocaleDateString([],{month:'short',day:'numeric'})}<br/>
                      <span style={{fontSize:9}}>{new Date(s.logged_at).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}</span>
                    </td>
                    <td style={{ padding: '9px 12px', fontWeight: 700 }}>{s.asset}</td>
                    <td style={{ padding: '9px 12px' }}>
                      <span style={{
                        fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: 11,
                        color: s.action === 'BUY' ? 'var(--accent-green)' : 'var(--accent-red)',
                        background: s.action === 'BUY' ? 'rgba(16,185,129,0.12)' : 'rgba(239,68,68,0.12)',
                        padding: '2px 8px', borderRadius: 5,
                        display: 'inline-flex', alignItems: 'center', gap: 4,
                      }}>
                        {s.action === 'BUY' ? <TrendingUp size={10}/> : <TrendingDown size={10}/>}
                        {s.action}
                      </span>
                    </td>
                    <td style={{ padding: '9px 12px', fontFamily: 'var(--font-mono)',
                      color: s.win_probability >= 70 ? 'var(--accent-green)' : 'var(--accent-blue)' }}>
                      {s.win_probability?.toFixed(1)}%
                    </td>
                    <td style={{ padding: '9px 12px', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                      €{s.position_size_capped?.toLocaleString('de-DE',{minimumFractionDigits:0,maximumFractionDigits:0})}
                      {s.was_capped ? <span style={{fontSize:9,color:'var(--accent-amber)',marginLeft:4}}>CAP</span> : ''}
                    </td>
                    <td style={{ padding: '9px 12px', fontFamily: 'var(--font-mono)',
                      color: 'var(--accent-amber)' }}>
                      €{s.risk_amount?.toFixed(0)}
                    </td>
                    <td style={{ padding: '9px 12px', fontFamily: 'var(--font-mono)',
                      color: s.net_profit > 0 ? 'var(--accent-green)' : 'var(--accent-red)',
                      fontWeight: 700 }}>
                      {s.net_profit >= 0 ? '+' : ''}€{s.net_profit?.toFixed(2)}
                    </td>
                    <td style={{ padding: '9px 12px', fontFamily: 'var(--font-mono)',
                      color: s.expected_value > 0 ? 'var(--accent-green)' : 'var(--accent-red)' }}>
                      {s.expected_value >= 0 ? '+' : ''}€{s.expected_value?.toFixed(2)}
                    </td>
                    <td style={{ padding: '9px 12px', fontFamily: 'var(--font-mono)',
                      color: 'var(--text-muted)' }}>
                      {s.stop_loss_pct?.toFixed(2)}%
                    </td>
                    <td style={{ padding: '9px 12px', fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                      {s.current_price?.toLocaleString('en-US',{maximumFractionDigits:3})}
                    </td>
                    <td style={{ padding: '9px 12px', fontFamily: 'var(--font-mono)',
                      color: 'var(--text-muted)' }}>{s.time_horizon}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            padding: '10px 16px', borderTop: '1px solid var(--border)' }}>
            <span style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
              Page {page + 1} · {signals.length} rows
            </span>
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={() => setPage(p => Math.max(0, p-1))} disabled={page === 0}
                style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)',
                  borderRadius: 6, padding: '4px 12px', color: page === 0 ? 'var(--text-muted)' : 'var(--text-primary)',
                  fontFamily: 'var(--font-mono)', fontSize: 11, cursor: page === 0 ? 'default' : 'pointer' }}>
                ← PREV
              </button>
              <button onClick={() => setPage(p => p+1)} disabled={signals.length < PER_PAGE}
                style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)',
                  borderRadius: 6, padding: '4px 12px',
                  color: signals.length < PER_PAGE ? 'var(--text-muted)' : 'var(--text-primary)',
                  fontFamily: 'var(--font-mono)', fontSize: 11,
                  cursor: signals.length < PER_PAGE ? 'default' : 'pointer' }}>
                NEXT →
              </button>
            </div>
          </div>
        </div>
      )}
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
