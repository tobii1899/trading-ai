import { X, Settings as Icon } from 'lucide-react';

const FIELDS = [
  { key: 'accountBalance',  label: 'Account Balance (€)',         type:'number', min:100,  max:1000000, step:100 },
  { key: 'riskPerTradePct', label: 'Risk per Trade (%)',          type:'number', min:0.1,  max:10,      step:0.1 },
  { key: 'stopLossPct',     label: 'Stop Loss (%)',               type:'number', min:0.05, max:10,      step:0.05 },
  { key: 'feeEur',          label: 'Trading Fee (€ round-trip)',  type:'number', min:0,    max:50,      step:0.5 },
  { key: 'feeMultiplier',   label: 'Min profit = N × fee',        type:'number', min:1,    max:10,      step:0.5 },
  { key: 'minProb',         label: 'Min Probability (%)',         type:'number', min:50,   max:95,      step:1 },
  { key: 'horizonBars',     label: 'Horizon Bars (×5min)',        type:'number', min:1,    max:48,      step:1 },
  { key: 'refreshInterval', label: 'Auto-refresh (seconds)',      type:'number', min:30,   max:3600,    step:30 },
];

export default function SettingsDrawer({ open, onClose, settings, onChange }) {
  if (!open) return null;
  const horizonMin = (settings.horizonBars || 6) * 5;

  return (
    <div style={{ position:'fixed', inset:0, zIndex:200, display:'flex', justifyContent:'flex-end' }}>
      <div onClick={onClose} style={{ flex:1, background:'rgba(0,0,0,0.5)', backdropFilter:'blur(4px)' }} />
      <div style={{ width:340, background:'var(--bg-surface)', borderLeft:'1px solid var(--border)',
        padding:24, overflowY:'auto', animation:'slideIn 0.25s ease' }}>

        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:24 }}>
          <div style={{ display:'flex', alignItems:'center', gap:8, fontWeight:700, fontSize:14 }}>
            <Icon size={15} color="var(--accent-blue)" /> Settings
          </div>
          <button onClick={onClose} style={{ background:'transparent', color:'var(--text-muted)',
            border:'none', cursor:'pointer', padding:4 }}><X size={16}/></button>
        </div>

        {/* Computed info box */}
        <div style={{ background:'rgba(59,130,246,0.08)', border:'1px solid rgba(59,130,246,0.2)',
          borderRadius:10, padding:'12px 14px', marginBottom:20, fontSize:11, lineHeight:1.7 }}>
          <strong style={{ color:'var(--accent-blue)' }}>Position Sizing Preview</strong><br/>
          Risk amount: <strong>€{(settings.accountBalance * settings.riskPerTradePct / 100).toFixed(0)}</strong>
          <span style={{color:'var(--text-muted)'}}> ({settings.riskPerTradePct}% of €{settings.accountBalance?.toLocaleString()})</span><br/>
          Max position: <strong>€{(settings.accountBalance * 0.3).toFixed(0)}</strong>
          <span style={{color:'var(--text-muted)'}}> (30% safety cap)</span><br/>
          Horizon: <strong>{horizonMin >= 60 ? `${horizonMin/60}h` : `${horizonMin}min`}</strong>
          <span style={{color:'var(--text-muted)'}}> ({settings.horizonBars} bars × 5min)</span><br/>
          Min net profit needed: <strong>€{(settings.feeMultiplier * settings.feeEur).toFixed(2)}</strong>
          <span style={{color:'var(--text-muted)'}}> ({settings.feeMultiplier}× fee)</span>
        </div>

        {FIELDS.map(({ key, label, type, min, max, step }) => (
          <div key={key} style={{ marginBottom:16 }}>
            <label style={{ fontSize:11, color:'var(--text-muted)', display:'block',
              marginBottom:5, letterSpacing:'0.05em' }}>{label}</label>
            <input type={type} min={min} max={max} step={step} value={settings[key]}
              onChange={e => onChange(key, Number(e.target.value))}
              style={{ width:'100%', background:'var(--bg-base)',
                border:'1px solid var(--border-bright)', borderRadius:8,
                padding:'8px 12px', color:'var(--text-primary)',
                fontFamily:'var(--font-mono)', fontSize:13 }} />
          </div>
        ))}

        <div style={{ marginTop:12, padding:14, background:'rgba(239,68,68,0.07)',
          border:'1px solid rgba(239,68,68,0.2)', borderRadius:10, fontSize:11,
          color:'var(--text-muted)', lineHeight:1.6 }}>
          <strong style={{ color:'var(--accent-red)' }}>⚠ Disclaimer</strong><br/>
          Research tool only. Not financial advice. Always use a demo account first.
        </div>
      </div>
      <style>{`@keyframes slideIn { from{transform:translateX(100%)} to{transform:translateX(0)} }`}</style>
    </div>
  );
}
