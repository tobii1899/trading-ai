// src/components/BacktestPanel.jsx
import { useState } from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ReferenceLine, ResponsiveContainer, CartesianGrid } from 'recharts';
import { Play, TrendingUp, TrendingDown, BarChart2 } from 'lucide-react';
import { useBacktest } from '../hooks/useSignals';
import { fmt } from '../utils/format';

const ASSETS = ['XAU/USD', 'GBP/JPY', 'NASDAQ100'];

function StatCard({ label, value, color, sub }) {
  return (
    <div style={{
      background: 'var(--bg-base)', border: '1px solid var(--border)',
      borderRadius: 10, padding: '12px 14px',
    }}>
      <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 5, letterSpacing: '0.06em' }}>{label}</div>
      <div style={{ fontSize: 18, fontFamily: 'var(--font-mono)', fontWeight: 700, color: color || 'var(--text-primary)' }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 3 }}>{sub}</div>}
    </div>
  );
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  const v = payload[0].value;
  return (
    <div style={{
      background: 'var(--bg-elevated)', border: '1px solid var(--border-bright)',
      borderRadius: 8, padding: '8px 12px', fontSize: 12,
    }}>
      <div style={{ color: 'var(--text-muted)', marginBottom: 3, fontSize: 10 }}>Bar #{label}</div>
      <div style={{
        fontFamily: 'var(--font-mono)', fontWeight: 700,
        color: v >= 0 ? 'var(--accent-green)' : 'var(--accent-red)',
      }}>
        {v >= 0 ? '+' : ''}€{Number(v).toFixed(2)}
      </div>
    </div>
  );
};

export default function BacktestPanel() {
  const [asset, setAsset] = useState('XAU/USD');
  const [config, setConfig] = useState({
    trade_size_eur: 100,
    min_probability_threshold: 55,
    fee_eur: 2,
    horizon_bars: 6,
    lookback_days: 30,
  });
  const { result, loading, error, run } = useBacktest(asset);

  const s = result?.summary;

  return (
    <div style={{ padding: '0 24px 40px' }}>
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ fontSize: 16, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}>
          <BarChart2 size={16} color="var(--accent-purple)" /> Backtesting Engine
        </h2>
        <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
          Simulate historical performance of the ML strategy
        </p>
      </div>

      {/* Config row */}
      <div style={{
        background: 'var(--bg-card)', border: '1px solid var(--border)',
        borderRadius: 'var(--radius-lg)', padding: 20, marginBottom: 20,
        display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 14,
      }}>
        {/* Asset selector */}
        <div>
          <label style={{ fontSize: 10, color: 'var(--text-muted)', display: 'block', marginBottom: 5 }}>ASSET</label>
          <select
            value={asset}
            onChange={e => setAsset(e.target.value)}
            style={{
              background: 'var(--bg-base)', border: '1px solid var(--border-bright)',
              color: 'var(--text-primary)', borderRadius: 7, padding: '6px 10px',
              fontFamily: 'var(--font-mono)', fontSize: 12, width: '100%',
            }}>
            {ASSETS.map(a => <option key={a} value={a}>{a}</option>)}
          </select>
        </div>

        {[
          { key: 'trade_size_eur', label: 'TRADE SIZE (€)', min: 10, max: 10000, step: 10 },
          { key: 'min_probability_threshold', label: 'MIN PROB (%)', min: 50, max: 90, step: 1 },
          { key: 'fee_eur', label: 'FEE (€ R/T)', min: 0, max: 20, step: 0.5 },
          { key: 'horizon_bars', label: 'HORIZON BARS', min: 1, max: 36, step: 1 },
          { key: 'lookback_days', label: 'LOOKBACK DAYS', min: 7, max: 60, step: 7 },
        ].map(({ key, label, min, max, step }) => (
          <div key={key}>
            <label style={{ fontSize: 10, color: 'var(--text-muted)', display: 'block', marginBottom: 5 }}>{label}</label>
            <input
              type="number" min={min} max={max} step={step}
              value={config[key]}
              onChange={e => setConfig(c => ({ ...c, [key]: Number(e.target.value) }))}
              style={{
                background: 'var(--bg-base)', border: '1px solid var(--border-bright)',
                color: 'var(--text-primary)', borderRadius: 7, padding: '6px 10px',
                fontFamily: 'var(--font-mono)', fontSize: 12, width: '100%',
              }}
            />
          </div>
        ))}

        {/* Run button */}
        <div style={{ display: 'flex', alignItems: 'flex-end' }}>
          <button
            onClick={() => run(config)}
            disabled={loading}
            style={{
              background: loading ? 'var(--bg-elevated)' : 'linear-gradient(135deg, #3b82f6, #8b5cf6)',
              border: 'none', borderRadius: 8, padding: '7px 18px', width: '100%',
              color: loading ? 'var(--text-muted)' : 'white',
              fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: 12,
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
              letterSpacing: '0.06em',
            }}>
            <Play size={12} />
            {loading ? 'RUNNING...' : 'RUN'}
          </button>
        </div>
      </div>

      {error && (
        <div style={{
          background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
          borderRadius: 10, padding: '12px 16px', color: 'var(--accent-red)',
          fontSize: 13, marginBottom: 20,
        }}>
          ⚠ {error} — make sure models are trained (/retrain endpoint)
        </div>
      )}

      {s && (
        <>
          {/* Summary stats */}
          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: 12, marginBottom: 20,
          }}>
            <StatCard label="TOTAL P&L" value={fmt.eur(s.total_pnl_eur)} color={s.total_pnl_eur >= 0 ? 'var(--accent-green)' : 'var(--accent-red)'} />
            <StatCard label="WIN RATE" value={`${s.win_rate_pct}%`} color={s.win_rate_pct >= 50 ? 'var(--accent-green)' : 'var(--accent-red)'} sub="(gross, pre-fee)" />
            <StatCard label="TRADES" value={s.trades_count} sub={`${s.win_count}W / ${s.loss_count}L`} />
            <StatCard label="SHARPE RATIO" value={fmt.sharpe(s.sharpe_ratio)} color={s.sharpe_ratio > 0 ? 'var(--accent-green)' : 'var(--accent-red)'} />
            <StatCard label="PROFIT FACTOR" value={s.profit_factor === Infinity ? '∞' : s.profit_factor?.toFixed(2)} />
            <StatCard label="MAX DRAWDOWN" value={fmt.eur(s.max_drawdown_eur)} color="var(--accent-red)" />
            <StatCard label="AVG WIN" value={fmt.eur(s.avg_win_eur)} color="var(--accent-green)" />
            <StatCard label="AVG LOSS" value={fmt.eur(s.avg_loss_eur)} color="var(--accent-red)" />
            <StatCard
              label="VS BUY & HOLD"
              value={fmt.eur(s.strategy_vs_buyhold_eur)}
              color={s.strategy_vs_buyhold_eur >= 0 ? 'var(--accent-green)' : 'var(--accent-red)'}
              sub={`B&H: ${fmt.pct(s.buy_hold_return_pct)}`}
            />
          </div>

          {/* Equity curve */}
          {result.equity_curve?.length > 1 && (
            <div style={{
              background: 'var(--bg-card)', border: '1px solid var(--border)',
              borderRadius: 'var(--radius-lg)', padding: 20,
            }}>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 14, fontFamily: 'var(--font-mono)', letterSpacing: '0.08em' }}>
                EQUITY CURVE — {asset}
              </div>
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={result.equity_curve.map(p => ({ idx: p.index, eq: p.equity_eur }))}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                  <XAxis dataKey="idx" tick={false} axisLine={false} tickLine={false} />
                  <YAxis
                    tick={{ fill: 'var(--text-muted)', fontSize: 10, fontFamily: 'Space Mono' }}
                    axisLine={false} tickLine={false}
                    tickFormatter={v => `€${v.toFixed(0)}`}
                    width={52}
                  />
                  <ReferenceLine y={0} stroke="rgba(255,255,255,0.15)" strokeDasharray="4 4" />
                  <Tooltip content={<CustomTooltip />} />
                  <Line
                    type="monotone" dataKey="eq" dot={false} strokeWidth={2}
                    stroke={s.total_pnl_eur >= 0 ? '#10b981' : '#ef4444'}
                    style={{ filter: `drop-shadow(0 0 6px ${s.total_pnl_eur >= 0 ? '#10b98180' : '#ef444480'})` }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Recent trades table */}
          {result.recent_trades?.length > 0 && (
            <div style={{
              marginTop: 20, background: 'var(--bg-card)', border: '1px solid var(--border)',
              borderRadius: 'var(--radius-lg)', padding: 20,
            }}>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12, fontFamily: 'var(--font-mono)', letterSpacing: '0.08em' }}>
                RECENT TRADES (last 20)
              </div>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                  <thead>
                    <tr style={{ color: 'var(--text-muted)' }}>
                      {['TIME', 'DIR', 'PROB', 'ACTUAL MOVE', 'GROSS P&L', 'NET P&L'].map(h => (
                        <th key={h} style={{ textAlign: 'left', padding: '4px 8px', fontFamily: 'var(--font-mono)', fontSize: 9, letterSpacing: '0.06em', borderBottom: '1px solid var(--border)' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {result.recent_trades.slice(0, 20).map((t, i) => (
                      <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                        <td style={{ padding: '5px 8px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{new Date(t.timestamp).toLocaleDateString([], {month:'short',day:'numeric'}) + ' ' + new Date(t.timestamp).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}</td>
                        <td style={{ padding: '5px 8px', color: t.direction === 'BUY' ? 'var(--accent-green)' : 'var(--accent-red)', fontFamily: 'var(--font-mono)', fontWeight: 700 }}>{t.direction}</td>
                        <td style={{ padding: '5px 8px', fontFamily: 'var(--font-mono)' }}>{t.probability}%</td>
                        <td style={{ padding: '5px 8px', fontFamily: 'var(--font-mono)', color: t.actual_return_pct >= 0 ? 'var(--accent-green)' : 'var(--accent-red)' }}>{fmt.pct(t.actual_return_pct, 4)}</td>
                        <td style={{ padding: '5px 8px', fontFamily: 'var(--font-mono)', color: t.raw_pnl_eur >= 0 ? 'var(--accent-green)' : 'var(--accent-red)' }}>{fmt.eur(t.raw_pnl_eur)}</td>
                        <td style={{ padding: '5px 8px', fontFamily: 'var(--font-mono)', color: t.net_pnl_eur >= 0 ? 'var(--accent-green)' : 'var(--accent-red)' }}>{fmt.eur(t.net_pnl_eur)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
