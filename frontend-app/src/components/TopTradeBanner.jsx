import { Zap, TrendingUp, TrendingDown } from 'lucide-react';
import { ASSET_META } from '../utils/format';

export default function TopTradeBanner({ trade }) {
  if (!trade) return null;
  const meta  = ASSET_META[trade.asset] || {};
  const isUp  = trade.action === 'BUY';
  const prob  = trade.win_probability ?? trade.up_probability ?? 0;
  const ev    = trade.expected_value ?? trade.expected_value_eur ?? 0;
  const move  = trade.expected_return_pct ?? 0;
  const pos   = trade.position_size_capped ?? trade.trade_size_eur ?? 0;

  return (
    <div style={{
      margin: '0 24px 20px',
      background: 'linear-gradient(135deg, rgba(59,130,246,0.12), rgba(139,92,246,0.12))',
      border: '1px solid rgba(59,130,246,0.4)',
      borderRadius: 'var(--radius-lg)', padding: '16px 20px',
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      flexWrap: 'wrap', gap: 14,
      boxShadow: '0 0 30px rgba(59,130,246,0.15)',
      position: 'relative', overflow: 'hidden',
    }}>
      <div style={{ position:'absolute', top:0, left:'-100%', right:0, bottom:0,
        background:'linear-gradient(90deg,transparent,rgba(59,130,246,0.06),transparent)',
        animation:'sweep 3s ease-in-out infinite', pointerEvents:'none' }} />

      <div style={{ display:'flex', alignItems:'center', gap:12 }}>
        <div style={{ width:36, height:36, borderRadius:10,
          background:'linear-gradient(135deg,#3b82f6,#8b5cf6)',
          display:'flex', alignItems:'center', justifyContent:'center' }}>
          <Zap size={17} color="white" fill="white" />
        </div>
        <div>
          <div style={{ fontSize:10, color:'var(--accent-blue)', fontFamily:'var(--font-mono)',
            fontWeight:700, letterSpacing:'0.1em', marginBottom:2 }}>⭐ TOP TRADE SIGNAL</div>
          <div style={{ fontSize:16, fontWeight:700 }}>
            {meta.icon} {trade.asset}
            <span style={{ marginLeft:10, fontSize:11, fontFamily:'var(--font-mono)',
              color: isUp ? 'var(--accent-green)' : 'var(--accent-red)',
              background: isUp ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)',
              padding:'2px 8px', borderRadius:5, fontWeight:700 }}>
              {isUp ? <TrendingUp size={10} style={{display:'inline',marginRight:3}}/> 
                    : <TrendingDown size={10} style={{display:'inline',marginRight:3}}/>}
              {trade.action}
            </span>
          </div>
        </div>
      </div>

      <div style={{ display:'flex', gap:24, flexWrap:'wrap' }}>
        {[
          { label: 'WIN PROB',       value: `${prob.toFixed(1)}%`,                     color: 'var(--accent-blue)' },
          { label: 'EXPECTED VALUE', value: `${ev >= 0 ? '+' : ''}€${ev.toFixed(2)}`,  color: ev >= 0 ? 'var(--accent-green)' : 'var(--accent-red)' },
          { label: 'EXPECTED MOVE',  value: `${move >= 0 ? '+' : ''}${move.toFixed(4)}%`, color: move >= 0 ? 'var(--accent-green)' : 'var(--accent-red)' },
          { label: 'POSITION SIZE',  value: `€${Number(pos).toLocaleString('de-DE',{maximumFractionDigits:0})}`, color: 'var(--text-primary)' },
          { label: 'HORIZON',        value: trade.time_horizon ?? '30min',              color: 'var(--text-primary)' },
        ].map(({ label, value, color }) => (
          <div key={label} style={{ textAlign:'center' }}>
            <div style={{ fontSize:10, color:'var(--text-muted)' }}>{label}</div>
            <div style={{ fontSize:18, fontFamily:'var(--font-mono)', fontWeight:700, color }}>{value}</div>
          </div>
        ))}
      </div>
      <style>{`@keyframes sweep { 0%{left:-100%} 100%{left:100%} }`}</style>
    </div>
  );
}
