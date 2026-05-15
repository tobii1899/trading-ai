// src/components/AssetCard.jsx v3 — proper signal display
import { useState } from 'react';
import { TrendingUp, TrendingDown, Minus, AlertTriangle, Newspaper, ChevronDown, ChevronUp, Zap } from 'lucide-react';
import { fmt, sentimentLabel, ASSET_META } from '../utils/format';

// ── Color helpers ─────────────────────────────────────────────────────────────

function actionColor(a) {
  if (a === 'BUY')  return 'var(--accent-green)';
  if (a === 'SELL') return 'var(--accent-red)';
  return 'var(--text-muted)';
}
function actionBg(a) {
  if (a === 'BUY')  return 'rgba(16,185,129,0.12)';
  if (a === 'SELL') return 'rgba(239,68,68,0.12)';
  return 'rgba(74,85,104,0.12)';
}
function evColor(ev) {
  if (ev > 2)  return 'var(--accent-green)';
  if (ev > 0)  return 'var(--accent-cyan)';
  return 'var(--accent-red)';
}
function confColor(score) {
  if (score >= 70) return 'var(--accent-green)';
  if (score >= 40) return 'var(--accent-amber)';
  return 'var(--accent-red)';
}
function signalBorder(action, isTopTrade, hasNews) {
  if (action === 'BUY')      return '1px solid rgba(16,185,129,0.45)';
  if (action === 'SELL')     return '1px solid rgba(239,68,68,0.40)';
  if (isTopTrade)            return '1px solid rgba(59,130,246,0.5)';
  if (hasNews)               return '1px solid rgba(245,158,11,0.3)';
  return '1px solid var(--border)';
}
function signalGlow(action, isTopTrade) {
  if (action === 'BUY')  return 'var(--glow-green)';
  if (action === 'SELL') return 'var(--glow-red)';
  if (isTopTrade)        return 'var(--glow-blue)';
  return 'none';
}

// ── Sub-components ────────────────────────────────────────────────────────────

function ProbBar({ upPct, downPct }) {
  const up = upPct ?? 50;
  const dn = downPct ?? (100 - up);
  return (
    <div style={{ margin: '10px 0 6px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
        <span style={{ fontSize: 10, color: 'var(--accent-green)', fontFamily: 'var(--font-mono)', fontWeight: 700 }}>
          UP {up.toFixed(1)}%
        </span>
        <span style={{ fontSize: 10, color: 'var(--accent-red)', fontFamily: 'var(--font-mono)', fontWeight: 700 }}>
          DOWN {dn.toFixed(1)}%
        </span>
      </div>
      <div style={{ height: 6, borderRadius: 3, overflow: 'hidden', background: 'var(--bg-base)', display: 'flex' }}>
        <div style={{
          width: `${up}%`, height: '100%',
          background: 'linear-gradient(90deg, #10b981, #06b6d4)',
          transition: 'width 0.8s cubic-bezier(0.4,0,0.2,1)',
        }} />
        <div style={{ flex: 1, background: 'rgba(239,68,68,0.4)' }} />
      </div>
    </div>
  );
}

function ActionBadge({ action }) {
  const Icon = action === 'BUY' ? TrendingUp : action === 'SELL' ? TrendingDown : Minus;
  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      background: actionBg(action),
      border: `1px solid ${actionColor(action)}40`,
      borderRadius: 8, padding: '6px 18px',
      color: actionColor(action),
      fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: 14,
      letterSpacing: '0.1em',
      boxShadow: action !== 'NO TRADE' ? `0 0 14px ${actionColor(action)}35` : 'none',
    }}>
      <Icon size={14} />{action}
    </div>
  );
}

function ConfidenceBar({ score }) {
  const color = score >= 70 ? 'var(--accent-green)' : score >= 40 ? 'var(--accent-amber)' : 'var(--accent-red)';
  return (
    <div style={{ marginTop: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
        <span style={{ fontSize: 9, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', letterSpacing: '0.06em' }}>
          CONFIDENCE
        </span>
        <span style={{ fontSize: 9, color, fontFamily: 'var(--font-mono)', fontWeight: 700 }}>
          {score.toFixed(0)}%
        </span>
      </div>
      <div style={{ height: 3, borderRadius: 2, background: 'var(--bg-base)' }}>
        <div style={{
          width: `${Math.min(score, 100)}%`, height: '100%',
          background: color, borderRadius: 2,
          transition: 'width 0.8s ease',
        }} />
      </div>
    </div>
  );
}

function MetricRow({ label, value, valueColor, mono = true, dim = false }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '4px 0' }}>
      <span style={{ fontSize: 11, color: dim ? 'var(--text-muted)' : 'var(--text-secondary)' }}>{label}</span>
      <span style={{
        fontSize: 12, fontWeight: 600,
        fontFamily: mono ? 'var(--font-mono)' : 'var(--font-sans)',
        color: valueColor || 'var(--text-primary)',
        opacity: dim ? 0.6 : 1,
      }}>{value}</span>
    </div>
  );
}

function SectionLabel({ children }) {
  return (
    <div style={{
      fontSize: 9, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)',
      letterSpacing: '0.1em', marginBottom: 5, marginTop: 10,
    }}>{children}</div>
  );
}

function fmtEurSigned(v) {
  if (v == null || isNaN(v)) return '—';
  return `${v >= 0 ? '+' : ''}€${Math.abs(v).toFixed(2)}`;
}

function scoreColor(score) {
  if (score >= 90) return 'var(--accent-green)';
  if (score >= 80) return 'var(--accent-cyan)';
  if (score >= 70) return 'var(--accent-amber)';
  if (score >= 60) return '#a78bfa';
  return 'var(--accent-red)';
}

// ── Main card ─────────────────────────────────────────────────────────────────

export default function AssetCard({ asset, signal, isTop }) {
  const [expanded, setExpanded] = useState(false);
  if (!signal) return null;

  const meta      = ASSET_META[asset] || { icon: '◆', color: '#888' };
  const hasNews   = signal.high_impact_news;
  const sentiment = sentimentLabel(signal.news_sentiment || 0);

  // ── Field mapping ──────────────────────────────────────────────────────────
  const upProb       = signal.win_probability   ?? signal.up_probability   ?? 50;
  const downProb     = signal.lose_probability  ?? signal.down_probability ?? 50;
  const avgUpMove    = signal.avg_up_move   ?? 0;
  const avgDownMove  = signal.avg_down_move ?? 0;
  const expRetPct    = (upProb / 100) * avgUpMove - (1 - (upProb / 100)) * Math.abs(avgDownMove);;   // dominant-direction move
  const evPct        = signal.expected_value_pct;    // true EV%
  const ev           = signal.expected_value ?? signal.expected_value_eur;
  const netProfit    = signal.net_profit;
  const netLoss      = signal.net_loss;
  const posSize      = signal.position_size_capped ?? '—';
  const riskAmt      = signal.risk_amount;
  const sigStrength  = signal.signal_strength ?? 0;
  const topScore     = signal.top_trade_score ?? null;
  const topLabel     = signal.top_trade_label ?? '';
  const confScore    = signal.confidence_score ?? 0;
  const action       = signal.action;
  const isTrading    = action === 'BUY' || action === 'SELL';
  const isTopTrade   = isTop || (isTrading && (ev ?? 0) > 0 && upProb >= 70);

  // Direction display: dominant direction + its avg move
  const directionUp   = upProb >= 50;
  const directionMove = directionUp ? avgUpMove : avgDownMove;
  const directionLabel = directionUp
    ? `▲ UP (+${Number(avgUpMove).toFixed(4)}%)`
    : `▼ DOWN (${Number(avgDownMove).toFixed(4)}%)`;
  const directionColor = directionUp ? 'var(--accent-green)' : 'var(--accent-red)';

  // Card color logic: green=valid trade, amber=weak, default=no trade
  const cardBorder = signalBorder(action, isTopTrade, hasNews);
  const cardGlow   = signalGlow(action, isTopTrade);

  return (
    <div
      style={{
        background: 'var(--bg-card)',
        border: cardBorder,
        borderRadius: 'var(--radius-lg)',
        padding: 20, position: 'relative', overflow: 'hidden',
        transition: 'transform 0.2s, box-shadow 0.3s',
        boxShadow: cardGlow,
      }}
      onMouseEnter={e => {
        e.currentTarget.style.transform = 'translateY(-2px)';
        e.currentTarget.style.boxShadow = '0 8px 32px rgba(0,0,0,0.4)';
      }}
      onMouseLeave={e => {
        e.currentTarget.style.transform = '';
        e.currentTarget.style.boxShadow = cardGlow;
      }}
    >
      {/* Accent strip — green for BUY, red for SELL, blue for top */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: 2,
        background: action === 'BUY'
          ? 'linear-gradient(90deg,#10b981,#06b6d4)'
          : action === 'SELL'
            ? 'linear-gradient(90deg,#ef4444,#f59e0b)'
            : isTopTrade
              ? 'linear-gradient(90deg,#3b82f6,#8b5cf6,#06b6d4)'
              : 'transparent',
      }} />

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 36, height: 36, borderRadius: 10,
            background: `${meta.color}20`, border: `1px solid ${meta.color}40`,
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16,
          }}>
            {meta.icon}
          </div>
          <div>
            <div style={{ fontSize: 15, fontWeight: 700 }}>{asset}</div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
              {signal.current_price
                ? Number(signal.current_price).toLocaleString('en-US', { maximumFractionDigits: 3 })
                : '—'}
              {' • '}{signal.time_horizon ?? '30min'}
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
          {isTopTrade && (
            <div style={{
              fontSize: 9, fontFamily: 'var(--font-mono)', fontWeight: 700,
              color: 'var(--accent-blue)', background: 'rgba(59,130,246,0.12)',
              border: '1px solid rgba(59,130,246,0.3)', borderRadius: 4, padding: '2px 6px',
            }}>⭐ TOP TRADE</div>
          )}
          {signal.is_trending != null && (
            <div style={{
              fontSize: 9, fontFamily: 'var(--font-mono)',
              color: signal.is_trending ? 'var(--accent-cyan)' : 'var(--text-muted)',
            }}>
              {signal.is_trending ? '📈 TRENDING' : '↔ RANGING'}
            </div>
          )}
        </div>
      </div>

      {/* Probability bar */}
      <ProbBar upPct={upProb} downPct={downProb} />

      {/* Confidence bar */}
      <ConfidenceBar score={confScore} />

      {/* Action badge */}
      <div style={{ margin: '14px 0 6px', display: 'flex', justifyContent: 'center' }}>
        <ActionBadge action={action} />
      </div>

      {/* Reject reason */}
      {!isTrading && signal.reject_reason && (
        <div style={{
          marginBottom: 8, fontSize: 10,
          color: 'var(--text-muted)', textAlign: 'center',
          fontFamily: 'var(--font-mono)',
          background: 'var(--bg-base)', borderRadius: 6, padding: '5px 10px',
          border: '1px solid var(--border)',
        }}>
          ⚠ {signal.reject_reason}
        </div>
      )}

      {/* Key metrics */}
      <div style={{
        background: 'var(--bg-base)', borderRadius: 8, padding: '10px 12px',
        border: '1px solid var(--border)', marginTop: 4,
      }}>
        {/* Direction — dominant direction + its avg historical move */}
        <MetricRow
          label="Direction"
          value={directionLabel}
          valueColor={directionColor}
        />

        {/* Expected Move — full EV formula result for dominant direction */}
        <MetricRow
          label="Expected Move"
          value={expRetPct != null
            ? `${expRetPct >= 0 ? '+' : ''}${Number(expRetPct).toFixed(4)}%`
            : '—'}
          valueColor={expRetPct == null
            ? 'var(--text-muted)'
            : expRetPct >= 0 ? 'var(--accent-green)' : 'var(--accent-red)'}
        />

        {/* EV% — full formula */}
        <MetricRow
          label="EV (formula)"
          value={evPct != null
            ? `${evPct >= 0 ? '+' : ''}${Number(evPct).toFixed(4)}%`
            : '—'}
          valueColor={evPct == null ? 'var(--text-muted)' : evPct >= 0 ? 'var(--accent-cyan)' : 'var(--accent-red)'}
        />

        {/* Top Trade Score */}
        {topScore != null && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '5px 0', borderTop: '1px solid var(--border)', marginTop: 4 }}>
            <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Top Trade Score</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{ width: 80, height: 4, borderRadius: 2, background: 'var(--bg-elevated)' }}>
                <div style={{ width: `${Math.min(topScore, 100)}%`, height: '100%', borderRadius: 2, background: scoreColor(topScore), transition: 'width 0.8s ease' }} />
              </div>
              <span style={{ fontSize: 12, fontWeight: 700, fontFamily: 'var(--font-mono)', color: scoreColor(topScore), minWidth: 32, textAlign: 'right' }}>
                {topScore.toFixed(0)}
              </span>
              <span style={{
                fontSize: 10, fontFamily: 'var(--font-mono)', fontWeight: 700,
                color: scoreColor(topScore),
                background: `${scoreColor(topScore)}18`,
                border: `1px solid ${scoreColor(topScore)}44`,
                borderRadius: 5, padding: '1px 6px',
              }}>{topLabel}</span>
            </div>
          </div>
        )}

        {/* Signal strength */}
        <MetricRow
          label="Signal Strength"
          value={`${(sigStrength * 100).toFixed(1)}%`}
          valueColor={sigStrength >= 0.2 ? 'var(--accent-green)' : sigStrength >= 0.1 ? 'var(--accent-amber)' : 'var(--accent-red)'}
        />

        {/* EV in EUR */}
        <MetricRow
          label="Expected Value €"
          value={ev != null ? fmtEurSigned(ev) : '—'}
          valueColor={ev == null ? 'var(--text-muted)' : evColor(ev)}
        />

        {isTrading && (
          <>
            <div style={{ borderTop: '1px solid var(--border)', margin: '6px 0' }} />
            <MetricRow
              label="Position Size"
              value={posSize !== '—' ? `€${Number(posSize).toLocaleString('de-DE', { maximumFractionDigits: 0 })}` : '—'}
              valueColor="var(--accent-blue)"
            />
            <MetricRow
              label="Risk Amount"
              value={riskAmt != null ? `€${Number(riskAmt).toFixed(0)}` : '—'}
              valueColor="var(--accent-amber)"
            />
            <MetricRow
              label="Net Profit (TP hit)"
              value={netProfit != null ? fmtEurSigned(netProfit) : '—'}
              valueColor={netProfit == null ? 'var(--text-muted)' : netProfit > 0 ? 'var(--accent-green)' : 'var(--accent-red)'}
            />
            <MetricRow
              label="Net Loss (SL hit)"
              value={netLoss != null ? fmtEurSigned(typeof netLoss === 'number' && netLoss > 0 ? -netLoss : netLoss) : '—'}
              valueColor="var(--accent-red)"
            />
          </>
        )}

        <MetricRow
          label="Fee"
          value={`€${(signal.fee_eur ?? 2).toFixed(2)}`}
          valueColor="var(--text-muted)"
          dim
        />

        {signal.was_capped && (
          <div style={{ marginTop: 5, fontSize: 9, color: 'var(--accent-amber)', fontFamily: 'var(--font-mono)', textAlign: 'right' }}>
            ⚠ Position capped at 30%
          </div>
        )}
      </div>

      {/* News warning */}
      {hasNews && signal.news_warning && (
        <div style={{
          marginTop: 10, background: 'rgba(245,158,11,0.08)',
          border: '1px solid rgba(245,158,11,0.25)', borderRadius: 7, padding: '7px 10px',
          display: 'flex', gap: 7, alignItems: 'flex-start',
        }}>
          <AlertTriangle size={12} color="var(--accent-amber)" style={{ marginTop: 1, flexShrink: 0 }} />
          <span style={{ fontSize: 10.5, color: 'var(--accent-amber)', lineHeight: 1.45 }}>
            {signal.news_warning}
          </span>
        </div>
      )}

      {/* Expand toggle */}
      <button onClick={() => setExpanded(v => !v)} style={{
        marginTop: 10, width: '100%', background: 'transparent', border: 'none',
        color: 'var(--text-muted)', display: 'flex', alignItems: 'center',
        justifyContent: 'center', gap: 4, fontSize: 11, fontFamily: 'var(--font-mono)',
        padding: '4px 0', cursor: 'pointer',
      }}>
        {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        {expanded ? 'LESS' : 'MORE DETAILS'}
      </button>

      {expanded && (
        <div style={{ marginTop: 8, borderTop: '1px solid var(--border)', paddingTop: 10 }}>

          {/* Avg moves breakdown */}
          <SectionLabel>DIRECTIONAL AVG MOVES (TRAINING)</SectionLabel>
          <div style={{ background: 'var(--bg-base)', borderRadius: 7, padding: '8px 10px', border: '1px solid var(--border)', marginBottom: 8 }}>
            <MetricRow label="Avg UP move"   value={`+${Number(avgUpMove).toFixed(4)}%`}  valueColor="var(--accent-green)" />
            <MetricRow label="Avg DOWN move" value={`${Number(avgDownMove).toFixed(4)}%`} valueColor="var(--accent-red)" />
            <MetricRow
              label="EV formula"
              value={`(${upProb.toFixed(1)}% × +${Number(avgUpMove).toFixed(4)}%) + (${downProb.toFixed(1)}% × ${Number(avgDownMove).toFixed(4)}%)`}
              valueColor="var(--text-muted)"
              mono={false}
            />
          </div>

          {/* Market regime */}
          <SectionLabel>MARKET REGIME</SectionLabel>
          <div style={{ background: 'var(--bg-base)', borderRadius: 7, padding: '8px 10px', border: '1px solid var(--border)', marginBottom: 8 }}>
            <MetricRow label="ADX" value={signal.raw_prediction?.adx != null ? `${signal.raw_prediction.adx}` : (signal.adx != null ? `${Number(signal.adx).toFixed(1)}` : '—')} />
            <MetricRow label="Trending" value={signal.is_trending ? 'YES' : 'NO'} valueColor={signal.is_trending ? 'var(--accent-cyan)' : 'var(--text-muted)'} />
            <MetricRow label="Vol Regime" value={signal.vol_regime != null ? Number(signal.vol_regime).toFixed(2) : '—'} />
            <MetricRow label="ATR %" value={`${signal.raw_prediction?.atr_pct?.toFixed(4) ?? signal.atr_pct ?? '—'}%`} />
          </div>

          {/* Technical indicators */}
          <SectionLabel>TECHNICAL INDICATORS</SectionLabel>
          <div style={{ background: 'var(--bg-base)', borderRadius: 7, padding: '8px 10px', border: '1px solid var(--border)' }}>
            <MetricRow label="RSI (14)"   value={signal.raw_prediction?.last_rsi?.toFixed(1) ?? '—'} />
            <MetricRow label="MACD Hist"  value={signal.raw_prediction?.last_macd_hist?.toFixed(6) ?? '—'} />
            <MetricRow label="BB %B"      value={signal.raw_prediction?.last_bb_pct?.toFixed(3) ?? '—'} />
            <MetricRow label="Stop Loss %" value={`${signal.stop_loss_pct?.toFixed(2) ?? '0.5'}%`} />
          </div>

          {/* News */}
          {signal.recent_news?.length > 0 && (
            <>
              <div style={{
                fontSize: 10, color: 'var(--text-muted)', margin: '10px 0 6px',
                fontFamily: 'var(--font-mono)', letterSpacing: '0.08em',
                display: 'flex', alignItems: 'center', gap: 5,
              }}>
                <Newspaper size={10} /> NEWS
                <span style={{ color: sentiment.color, marginLeft: 4 }}>{sentiment.label}</span>
              </div>
              {signal.recent_news.map((n, i) => (
                <div key={i} style={{
                  fontSize: 11, color: 'var(--text-secondary)',
                  padding: '5px 0', lineHeight: 1.4,
                  borderBottom: i < signal.recent_news.length - 1 ? '1px solid var(--border)' : 'none',
                }}>
                  <span style={{
                    display: 'inline-block', width: 6, height: 6, borderRadius: '50%',
                    background: n.sentiment > 0 ? 'var(--accent-green)' : n.sentiment < 0 ? 'var(--accent-red)' : 'var(--text-muted)',
                    marginRight: 6, verticalAlign: 'middle',
                  }} />
                  {n.title}
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
}
