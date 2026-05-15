// src/components/Skeleton.jsx
export function CardSkeleton() {
  return (
    <div style={{
      background: 'var(--bg-card)', border: '1px solid var(--border)',
      borderRadius: 'var(--radius-lg)', padding: 20, overflow: 'hidden',
    }}>
      {[70, 45, 90, 55, 80, 60, 75].map((w, i) => (
        <div key={i} style={{
          height: i === 0 ? 18 : 12, width: `${w}%`,
          background: 'var(--bg-elevated)',
          borderRadius: 4, marginBottom: i === 0 ? 16 : 10,
          animation: `shimmer 1.5s infinite ${i * 0.1}s`,
        }} />
      ))}
      <style>{`
        @keyframes shimmer {
          0%,100% { opacity: 0.4; }
          50% { opacity: 0.8; }
        }
      `}</style>
    </div>
  );
}

export function ErrorCard({ message, onRetry }) {
  return (
    <div style={{
      background: 'rgba(239,68,68,0.07)', border: '1px solid rgba(239,68,68,0.2)',
      borderRadius: 'var(--radius-lg)', padding: 24,
      display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12,
      gridColumn: '1/-1',
    }}>
      <div style={{ fontSize: 28 }}>⚠️</div>
      <div style={{ color: 'var(--accent-red)', fontWeight: 600 }}>Failed to load signals</div>
      <div style={{ color: 'var(--text-muted)', fontSize: 12, textAlign: 'center', maxWidth: 360 }}>
        {message}<br />
        Make sure the backend is running on port 8000.
      </div>
      {onRetry && (
        <button onClick={onRetry} style={{
          background: 'var(--bg-elevated)', border: '1px solid var(--border-bright)',
          borderRadius: 8, padding: '7px 18px',
          color: 'var(--text-primary)', fontFamily: 'var(--font-mono)', fontSize: 12,
        }}>RETRY</button>
      )}
    </div>
  );
}
