// src/components/Profile.jsx
import { useState, useEffect, useCallback } from 'react';
import { tradeApi } from '../utils/api';
import { TrendingUp, TrendingDown, Minus, Trash2, PlusCircle, BarChart3, Activity } from 'lucide-react';

const ASSETS = ['XAU/USD', 'GBP/JPY', 'NASDAQ100'];
const ACTIONS = ['BUY', 'SELL'];
const RESULTS = ['Win', 'Loss', 'BE'];

const EMPTY_FORM = {
  asset: 'XAU/USD',
  action: 'BUY',
  entryPrice: '',
  stopLoss: '',
  takeProfit: '',
  exitPrice: '',
  resultOverride: '',  // '' = auto-calculate from PnL
};

/* ── helpers ─────────────────────────────────────────────────────────────── */

function fmtDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString('de-AT', { day: '2-digit', month: '2-digit', year: '2-digit' })
    + ' ' + d.toLocaleTimeString('de-AT', { hour: '2-digit', minute: '2-digit' });
}

function fmtEur(n) {
  const v = Number(n);
  if (isNaN(v)) return '—';
  const s = (v >= 0 ? '+' : '') + v.toFixed(2) + ' €';
  return s;
}

function ResultBadge({ result }) {
  const map = {
    Win:  { color: 'var(--accent-green)',  icon: <TrendingUp  size={11} /> },
    Loss: { color: 'var(--accent-red)',    icon: <TrendingDown size={11} /> },
    BE:   { color: 'var(--accent-amber)',  icon: <Minus       size={11} /> },
  };
  const { color, icon } = map[result] || map.BE;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      background: `${color}22`, border: `1px solid ${color}55`,
      color, borderRadius: 6, padding: '2px 8px',
      fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 700,
    }}>
      {icon}{result.toUpperCase()}
    </span>
  );
}

function StatCard({ label, value, color, sub }) {
  return (
    <div style={{
      background: 'var(--bg-card)', border: '1px solid var(--border)',
      borderRadius: 12, padding: '16px 20px', flex: '1 1 140px',
    }}>
      <div style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)',
        letterSpacing: '0.08em', marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color: color || 'var(--text-primary)',
        fontFamily: 'var(--font-mono)' }}>{value}</div>
      {sub && <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 3 }}>{sub}</div>}
    </div>
  );
}

/* ── Field ─────────────────────────────────────────────────────────────────── */
function Field({ label, children }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
      <label style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)',
        letterSpacing: '0.06em' }}>{label}</label>
      {children}
    </div>
  );
}

const inputStyle = {
  background: 'var(--bg-elevated)', border: '1px solid var(--border)',
  borderRadius: 8, padding: '8px 12px', color: 'var(--text-primary)',
  fontSize: 13, fontFamily: 'var(--font-mono)', outline: 'none',
  width: '100%', transition: 'border-color 0.2s',
};

const selectStyle = { ...inputStyle, cursor: 'pointer' };

/* ══════════════════════════════════════════════════════════════════════════ */

export default function Profile() {
  const [form, setForm]       = useState(EMPTY_FORM);
  const [trades, setTrades]   = useState([]);
  const [stats, setStats]     = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [filterResult, setFilterResult] = useState('All');
  const [filterAsset, setFilterAsset]   = useState('All');

  /* ── data loading ───────────────────────────────────────────────────────── */

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [tradeRes, statsRes] = await Promise.all([
        tradeApi.getTrades({ limit: 200 }),
        tradeApi.getTradeStats(),
      ]);
      setTrades(tradeRes.trades || []);
      setStats(statsRes);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  /* ── client-side validation hint ──────────────────────────────────────────── */

  const validationHint = (() => {
    const entry = parseFloat(form.entryPrice);
    const sl    = parseFloat(form.stopLoss);
    const tp    = parseFloat(form.takeProfit);
    if (!entry || !sl || !tp) return null;
    if (form.action === 'BUY') {
      if (sl >= entry) return '⚠ BUY: Stop Loss must be BELOW entry';
      if (tp <= entry) return '⚠ BUY: Take Profit must be ABOVE entry';
    } else {
      if (sl <= entry) return '⚠ SELL: Stop Loss must be ABOVE entry';
      if (tp >= entry) return '⚠ SELL: Take Profit must be BELOW entry';
    }
    return null;
  })();

  /* ── live position-size preview ─────────────────────────────────────────── */

  const positionPreview = (() => {
    const entry = parseFloat(form.entryPrice);
    const sl    = parseFloat(form.stopLoss);
    if (!entry || !sl || entry === sl) return null;
    const riskAmount = 5000 * 0.01;          // 1% of €5000
    const slDist     = Math.abs(entry - sl);
    const qty        = riskAmount / slDist;
    return { riskAmount: riskAmount.toFixed(2), qty: qty.toFixed(4), slDist: slDist.toFixed(4) };
  })();

  /* ── form submit ────────────────────────────────────────────────────────── */

  const handleSubmit = async () => {
    const { asset, action, entryPrice, stopLoss, takeProfit, exitPrice, resultOverride } = form;
    if (!entryPrice || !stopLoss || !takeProfit) {
      setError('Entry, Stop Loss and Take Profit are required.');
      return;
    }
    if (validationHint) {
      setError(validationHint.replace('⚠ ', ''));
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await tradeApi.createTrade({
        asset, action,
        entryPrice:     parseFloat(entryPrice),
        stopLoss:       parseFloat(stopLoss),
        takeProfit:     parseFloat(takeProfit),
        exitPrice:      exitPrice ? parseFloat(exitPrice) : null,
        resultOverride: resultOverride || null,
      });
      setForm(EMPTY_FORM);
      await loadData();
    } catch (e) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id) => {
    try {
      await tradeApi.deleteTrade(id);
      await loadData();
    } catch (e) {
      setError(e.message);
    }
  };

  /* ── filtered trades ────────────────────────────────────────────────────── */

  const displayed = trades.filter(t => {
    const okResult = filterResult === 'All' || t.result === filterResult;
    const okAsset  = filterAsset  === 'All' || t.asset  === filterAsset;
    return okResult && okAsset;
  });

  /* ── render ─────────────────────────────────────────────────────────────── */

  const pnlColor = stats
    ? stats.totalPnL > 0 ? 'var(--accent-green)'
    : stats.totalPnL < 0 ? 'var(--accent-red)'
    : 'var(--text-muted)'
    : 'var(--text-muted)';

  const pnlPercent = stats
    ? ((stats.totalPnL / 5000) * 100)
    : 0;

  return (
    <div style={{ padding: '0 24px 40px', maxWidth: 1400, margin: '0 auto' }}>

      {/* ── Page title ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 24 }}>
        <Activity size={18} color="var(--accent-blue)" />
        <h2 style={{ fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)',
          letterSpacing: '0.06em' }}>TRADE PROFILE</h2>
        <span style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)',
          border: '1px solid var(--border)', padding: '2px 8px', borderRadius: 4 }}>
          JOURNAL
        </span>
      </div>

      {/* ── Stats row ── */}
      {stats && (
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 24 }}>
          <StatCard
            label="TOTAL P&L"
            value={
              <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.1 }}>
                <span>{fmtEur(stats.totalPnL)}</span>
                <span style={{
                  fontSize: 10,
                  opacity: 0.7,
                  fontFamily: 'var(--font-mono)',
                  marginBottom: 4
                }}>
                  ({pnlPercent >= 0 ? '+' : ''}{pnlPercent.toFixed(2)}%)
                </span>
              </div>
            }            
            color={pnlColor}
            sub={`${stats.totalTrades} trades`}
          />
          <StatCard
            label="WINRATE"
            value={`${stats.winrate}%`}
            color={stats.winrate >= 50 ? 'var(--accent-green)' : 'var(--accent-red)'}
            sub={`${stats.wins}W / ${stats.losses}L / ${stats.breakevens}BE`}
          />
          <StatCard
            label="AVG WIN"
            value={fmtEur(stats.avgWin)}
            color="var(--accent-green)"
          />
          <StatCard
            label="AVG LOSS"
            value={fmtEur(stats.avgLoss)}
            color="var(--accent-red)"
          />
          <StatCard
            label="TOTAL TRADES"
            value={stats.totalTrades}
            color="var(--accent-blue)"
          />
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '340px 1fr', gap: 20, alignItems: 'start' }}>

        {/* ── Entry Form ── */}
        <div style={{
          background: 'var(--bg-card)', border: '1px solid var(--border)',
          borderRadius: 14, padding: 20,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 18 }}>
            <PlusCircle size={14} color="var(--accent-blue)" />
            <span style={{ fontSize: 12, fontWeight: 700, fontFamily: 'var(--font-mono)',
              letterSpacing: '0.06em' }}>NEW TRADE</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

            <Field label="ASSET">
              <select value={form.asset}
                onChange={e => setForm(f => ({ ...f, asset: e.target.value }))}
                style={selectStyle}>
                {ASSETS.map(a => <option key={a}>{a}</option>)}
              </select>
            </Field>

            <Field label="ACTION">
              <div style={{ display: 'flex', gap: 8 }}>
                {ACTIONS.map(a => (
                  <button key={a} onClick={() => setForm(f => ({ ...f, action: a }))}
                    style={{
                      flex: 1, padding: '8px 0', borderRadius: 8, border: '1px solid',
                      fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 700,
                      cursor: 'pointer', transition: 'all 0.15s',
                      borderColor: form.action === a
                        ? (a === 'BUY' ? 'var(--accent-green)' : 'var(--accent-red)')
                        : 'var(--border)',
                      background: form.action === a
                        ? (a === 'BUY' ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)')
                        : 'var(--bg-elevated)',
                      color: form.action === a
                        ? (a === 'BUY' ? 'var(--accent-green)' : 'var(--accent-red)')
                        : 'var(--text-muted)',
                    }}>
                    {a === 'BUY' ? '▲ BUY' : '▼ SELL'}
                  </button>
                ))}
              </div>
            </Field>

            <Field label="ENTRY PRICE">
              <input type="number" step="any" value={form.entryPrice}
                onChange={e => setForm(f => ({ ...f, entryPrice: e.target.value }))}
                placeholder="e.g. 2345.50" style={inputStyle} />
            </Field>

            <Field label="STOP LOSS">
              <input type="number" step="any" value={form.stopLoss}
                onChange={e => setForm(f => ({ ...f, stopLoss: e.target.value }))}
                placeholder="e.g. 2330.00" style={inputStyle} />
            </Field>

            {/* Live position-size preview */}
            {positionPreview && !validationHint && (
              <div style={{
                background: 'rgba(59,130,246,0.07)', border: '1px solid rgba(59,130,246,0.2)',
                borderRadius: 8, padding: '8px 12px',
                fontFamily: 'var(--font-mono)', fontSize: 11,
                display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 6,
              }}>
                <div>
                  <div style={{ color: 'var(--text-muted)', fontSize: 9, marginBottom: 2 }}>RISK AMOUNT</div>
                  <div style={{ color: 'var(--accent-amber)', fontWeight: 700 }}>€{positionPreview.riskAmount}</div>
                </div>
                <div>
                  <div style={{ color: 'var(--text-muted)', fontSize: 9, marginBottom: 2 }}>SL DISTANCE</div>
                  <div style={{ color: 'var(--text-secondary)' }}>{positionPreview.slDist}</div>
                </div>
                <div>
                  <div style={{ color: 'var(--text-muted)', fontSize: 9, marginBottom: 2 }}>QTY (UNITS)</div>
                  <div style={{ color: 'var(--accent-blue)', fontWeight: 700 }}>{positionPreview.qty}</div>
                </div>
              </div>
            )}

            <Field label="TAKE PROFIT">
              <input type="number" step="any" value={form.takeProfit}
                onChange={e => setForm(f => ({ ...f, takeProfit: e.target.value }))}
                placeholder="e.g. 2370.00" style={inputStyle} />
            </Field>

            <Field label="EXIT PRICE (optional — overrides TP/SL)">
              <input type="number" step="any" value={form.exitPrice}
                onChange={e => setForm(f => ({ ...f, exitPrice: e.target.value }))}
                placeholder="Leave empty to use TP" style={inputStyle} />
            </Field>

            <Field label="RESULT (optional — overrides auto-calculation)">
              <div style={{ display: 'flex', gap: 8 }}>
                {['', 'Win', 'Loss', 'BE'].map(r => (
                  <button key={r} onClick={() => setForm(f => ({ ...f, resultOverride: r }))}
                    style={{
                      flex: 1, padding: '7px 0', borderRadius: 8, border: '1px solid',
                      fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 700,
                      cursor: 'pointer', transition: 'all 0.15s',
                      borderColor: form.resultOverride === r
                        ? (r === 'Win' ? 'var(--accent-green)'
                          : r === 'Loss' ? 'var(--accent-red)'
                          : r === 'BE' ? 'var(--accent-amber)'
                          : 'var(--accent-blue)')
                        : 'var(--border)',
                      background: form.resultOverride === r
                        ? (r === 'Win' ? 'rgba(16,185,129,0.15)'
                          : r === 'Loss' ? 'rgba(239,68,68,0.15)'
                          : r === 'BE' ? 'rgba(245,158,11,0.15)'
                          : 'rgba(59,130,246,0.15)')
                        : 'var(--bg-elevated)',
                      color: form.resultOverride === r
                        ? (r === 'Win' ? 'var(--accent-green)'
                          : r === 'Loss' ? 'var(--accent-red)'
                          : r === 'BE' ? 'var(--accent-amber)'
                          : 'var(--accent-blue)')
                        : 'var(--text-muted)',
                    }}>
                    {r === '' ? 'AUTO' : r.toUpperCase()}
                  </button>
                ))}
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                AUTO = berechnet aus Entry vs. Exit
              </div>
            </Field>

            {/* Live validation hint */}
            {validationHint && (
              <div style={{
                background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.3)',
                borderRadius: 8, padding: '8px 12px',
                color: 'var(--accent-amber)', fontSize: 11, fontFamily: 'var(--font-mono)',
              }}>{validationHint}</div>
            )}

            {error && (
              <div style={{
                background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
                borderRadius: 8, padding: '8px 12px',
                color: 'var(--accent-red)', fontSize: 12,
              }}>{error}</div>
            )}

            <button
              onClick={handleSubmit}
              disabled={submitting}
              style={{
                background: submitting ? 'var(--bg-elevated)' : 'var(--accent-blue)',
                color: '#fff', border: 'none', borderRadius: 10,
                padding: '11px 0', fontSize: 13, fontWeight: 700,
                fontFamily: 'var(--font-mono)', letterSpacing: '0.06em',
                cursor: submitting ? 'not-allowed' : 'pointer',
                opacity: submitting ? 0.6 : 1,
                transition: 'all 0.15s',
              }}>
              {submitting ? 'SAVING…' : '+ SUBMIT TRADE'}
            </button>

            <div style={{ fontSize: 10, color: 'var(--text-muted)', textAlign: 'center',
              fontFamily: 'var(--font-mono)' }}>
              Fee: −3.00 € applied automatically
            </div>
          </div>
        </div>

        {/* ── History Table ── */}
        <div style={{
          background: 'var(--bg-card)', border: '1px solid var(--border)',
          borderRadius: 14, overflow: 'hidden',
        }}>
          {/* Table header */}
          <div style={{
            padding: '14px 20px', borderBottom: '1px solid var(--border)',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            flexWrap: 'wrap', gap: 10,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <BarChart3 size={14} color="var(--accent-blue)" />
              <span style={{ fontSize: 12, fontWeight: 700, fontFamily: 'var(--font-mono)',
                letterSpacing: '0.06em' }}>
                TRADE HISTORY
              </span>
              <span style={{ fontSize: 10, color: 'var(--text-muted)',
                fontFamily: 'var(--font-mono)' }}>
                ({displayed.length})
              </span>
            </div>
            {/* Filters */}
            <div style={{ display: 'flex', gap: 8 }}>
              <select value={filterAsset}
                onChange={e => setFilterAsset(e.target.value)}
                style={{ ...selectStyle, width: 'auto', fontSize: 11, padding: '5px 10px' }}>
                <option>All</option>
                {ASSETS.map(a => <option key={a}>{a}</option>)}
              </select>
              <select value={filterResult}
                onChange={e => setFilterResult(e.target.value)}
                style={{ ...selectStyle, width: 'auto', fontSize: 11, padding: '5px 10px' }}>
                <option>All</option>
                {RESULTS.map(r => <option key={r}>{r}</option>)}
              </select>
            </div>
          </div>

          {loading && (
            <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)',
              fontFamily: 'var(--font-mono)', fontSize: 12 }}>
              Loading…
            </div>
          )}

          {!loading && displayed.length === 0 && (
            <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)',
              fontFamily: 'var(--font-mono)', fontSize: 12 }}>
              No trades yet. Submit your first trade →
            </div>
          )}

          {!loading && displayed.length > 0 && (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border)' }}>
                    {['ASSET', 'ACTION', 'ENTRY', 'EXIT', 'SL', 'TP', 'QTY', 'RISK', 'RESULT', 'P&L', 'DATE', ''].map(h => (
                      <th key={h} style={{
                        padding: '10px 14px', textAlign: 'left',
                        fontSize: 10, color: 'var(--text-muted)',
                        fontFamily: 'var(--font-mono)', letterSpacing: '0.06em',
                        fontWeight: 600, whiteSpace: 'nowrap',
                      }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {displayed.map((t, i) => {
                    const pnl = Number(t.profitLoss);
                    const pnlCol = pnl > 0 ? 'var(--accent-green)'
                      : pnl < 0 ? 'var(--accent-red)' : 'var(--text-muted)';
                    return (
                      <tr key={t.id} style={{
                        borderBottom: '1px solid var(--border)',
                        background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.01)',
                        transition: 'background 0.15s',
                      }}
                        onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-card-hover)'}
                        onMouseLeave={e => e.currentTarget.style.background = i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.01)'}
                      >
                        <td style={{ padding: '10px 14px', fontFamily: 'var(--font-mono)',
                          fontWeight: 700, fontSize: 12 }}>{t.asset}</td>
                        <td style={{ padding: '10px 14px' }}>
                          <span style={{
                            color: t.action === 'BUY' ? 'var(--accent-green)' : 'var(--accent-red)',
                            fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: 11,
                          }}>{t.action}</span>
                        </td>
                        <td style={{ padding: '10px 14px', fontFamily: 'var(--font-mono)',
                          color: 'var(--text-secondary)' }}>
                          {Number(t.entryPrice).toFixed(2)}
                        </td>
                        <td style={{ padding: '10px 14px', fontFamily: 'var(--font-mono)',
                          color: 'var(--text-secondary)' }}>
                          {t.exitPrice != null ? Number(t.exitPrice).toFixed(2) : '—'}
                        </td>
                        <td style={{ padding: '10px 14px', fontFamily: 'var(--font-mono)',
                          color: 'var(--accent-red)', fontSize: 11 }}>
                          {Number(t.stopLoss).toFixed(2)}
                        </td>
                        <td style={{ padding: '10px 14px', fontFamily: 'var(--font-mono)',
                          color: 'var(--accent-green)', fontSize: 11 }}>
                          {Number(t.takeProfit).toFixed(2)}
                        </td>
                        <td style={{ padding: '10px 14px', fontFamily: 'var(--font-mono)',
                          color: 'var(--accent-blue)', fontSize: 11 }}>
                          {t.qty != null ? Number(t.qty).toFixed(4) : '—'}
                        </td>
                        <td style={{ padding: '10px 14px', fontFamily: 'var(--font-mono)',
                          color: 'var(--accent-amber)', fontSize: 11 }}>
                          {t.riskAmount != null ? '€' + Number(t.riskAmount).toFixed(2) : '—'}
                        </td>
                        <td style={{ padding: '10px 14px' }}>
                          <ResultBadge result={t.result} />
                        </td>
                        <td style={{
                          padding: '10px 14px', fontFamily: 'var(--font-mono)',
                          fontWeight: 700, color: pnlCol,
                        }}>
                          {fmtEur(pnl)}
                        </td>
                        <td style={{ padding: '10px 14px', color: 'var(--text-muted)',
                          fontSize: 11, whiteSpace: 'nowrap' }}>
                          {fmtDate(t.date)}
                        </td>
                        <td style={{ padding: '10px 14px' }}>
                          <button onClick={() => handleDelete(t.id)} style={{
                            background: 'transparent', border: 'none',
                            color: 'var(--text-muted)', cursor: 'pointer',
                            padding: 4, borderRadius: 6,
                            display: 'flex', alignItems: 'center',
                            transition: 'color 0.15s',
                          }}
                            onMouseEnter={e => e.currentTarget.style.color = 'var(--accent-red)'}
                            onMouseLeave={e => e.currentTarget.style.color = 'var(--text-muted)'}
                            title="Delete trade"
                          >
                            <Trash2 size={13} />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}