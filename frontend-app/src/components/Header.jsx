// src/components/Header.jsx
import { RefreshCw, Cpu, AlertTriangle } from 'lucide-react';
import { fmt } from '../utils/format';

export default function Header({ lastUpdated, nextRefreshIn, loading, onRefresh, globalAlert, retraining }) {
  return (
    <header style={{
      position: 'sticky', top: 0, zIndex: 100,
      background: 'rgba(8,10,15,0.92)',
      backdropFilter: 'blur(20px)',
      borderBottom: '1px solid var(--border)',
      padding: '0 24px',
      height: 56,
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      gap: 16,
    }}>
      {/* Logo */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{
          width: 28, height: 28,
          background: 'linear-gradient(135deg, #3b82f6, #8b5cf6)',
          borderRadius: 7,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 14, fontWeight: 700,
        }}>Δ</div>
        <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: 13, letterSpacing: '0.08em' }}>
          ORACLE<span style={{ color: 'var(--accent-blue)' }}>AI</span>
        </span>
        <span style={{
          fontSize: 10, fontFamily: 'var(--font-mono)',
          color: 'var(--text-muted)', marginLeft: 4,
          border: '1px solid var(--border)', padding: '1px 6px', borderRadius: 4,
        }}>BETA</span>
      </div>

      {/* Center: news alert */}
      {globalAlert && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6,
          background: 'rgba(245,158,11,0.1)',
          border: '1px solid rgba(245,158,11,0.3)',
          borderRadius: 8, padding: '4px 12px',
          color: 'var(--accent-amber)',
          fontSize: 11.5, fontWeight: 600,
          animation: 'pulse 2s infinite',
        }}>
          <AlertTriangle size={13} />
          HIGH-IMPACT NEWS DETECTED — TRADE RISK ELEVATED
        </div>
      )}

      {/* Right controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        {lastUpdated && (
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
              UPDATED {fmt.time(lastUpdated)}
            </div>
            <div style={{ fontSize: 10, color: 'var(--accent-blue)', fontFamily: 'var(--font-mono)' }}>
              REFRESH IN {fmt.countdown(nextRefreshIn)}
            </div>
          </div>
        )}

        {retraining && (
          <div style={{ display:'flex', alignItems:'center', gap:5,
            color:'var(--accent-purple)', fontSize:11, fontFamily:'var(--font-mono)' }}>
            <Cpu size={12} style={{ animation: 'spin 1s linear infinite' }} />
            TRAINING
          </div>
        )}

        <button
          onClick={onRefresh}
          disabled={loading}
          style={{
            background: 'var(--bg-elevated)', border: '1px solid var(--border)',
            borderRadius: 8, padding: '6px 14px',
            color: loading ? 'var(--text-muted)' : 'var(--text-primary)',
            fontSize: 12, fontFamily: 'var(--font-mono)',
            display: 'flex', alignItems: 'center', gap: 6,
            transition: 'var(--transition)',
          }}>
          <RefreshCw size={12} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
          {loading ? 'LOADING' : 'REFRESH'}
        </button>
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.6} }
      `}</style>
    </header>
  );
}
