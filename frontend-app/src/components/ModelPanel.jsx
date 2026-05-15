// src/components/ModelPanel.jsx
import { useState } from 'react';
import { Cpu, RefreshCw, CheckCircle, XCircle, Clock } from 'lucide-react';
import { api } from '../utils/api';
import { useModelStatus } from '../hooks/useSignals';
import { fmt } from '../utils/format';

export default function ModelPanel() {
  const { status, loading, refresh } = useModelStatus();
  const [retraining, setRetraining] = useState(false);
  const [retMsg, setRetMsg] = useState(null);

  async function triggerRetrain(asset = null) {
    setRetraining(true);
    setRetMsg(null);
    try {
      const r = await api.retrain(asset);
      setRetMsg({ type: 'ok', text: r.message });
      // Poll status after 2s
      setTimeout(refresh, 2000);
    } catch (e) {
      setRetMsg({ type: 'err', text: e.message });
    } finally {
      setRetraining(false);
    }
  }

  const models = status?.models || {};

  return (
    <div style={{ padding: '0 24px 40px' }}>
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ fontSize: 16, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Cpu size={16} color="var(--accent-purple)" /> Model Management
        </h2>
        <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
          View training metrics and trigger retraining
        </p>
      </div>

      {retMsg && (
        <div style={{
          padding: '10px 14px', borderRadius: 8, marginBottom: 16, fontSize: 12,
          background: retMsg.type === 'ok' ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)',
          border: `1px solid ${retMsg.type === 'ok' ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'}`,
          color: retMsg.type === 'ok' ? 'var(--accent-green)' : 'var(--accent-red)',
        }}>
          {retMsg.text}
        </div>
      )}

      <div style={{ marginBottom: 16, display: 'flex', gap: 10 }}>
        <button
          onClick={() => triggerRetrain(null)}
          disabled={retraining}
          style={{
            background: 'linear-gradient(135deg, #8b5cf6, #3b82f6)',
            border: 'none', borderRadius: 8, padding: '8px 18px',
            color: 'white', fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: 12,
            display: 'flex', alignItems: 'center', gap: 6, opacity: retraining ? 0.6 : 1,
          }}>
          <RefreshCw size={12} style={{ animation: retraining ? 'spin 1s linear infinite' : 'none' }} />
          RETRAIN ALL MODELS
        </button>
        <button onClick={refresh} style={{
          background: 'var(--bg-elevated)', border: '1px solid var(--border)',
          borderRadius: 8, padding: '8px 14px',
          color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', fontSize: 12,
        }}>REFRESH STATUS</button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(300px,1fr))', gap: 14 }}>
        {Object.entries(models).map(([asset, info]) => (
          <div key={asset} style={{
            background: 'var(--bg-card)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius-lg)', padding: 18,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <div style={{ fontWeight: 700, fontSize: 14 }}>{asset}</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
                {info.is_trained
                  ? <><CheckCircle size={13} color="var(--accent-green)" /> <span style={{ color: 'var(--accent-green)' }}>TRAINED</span></>
                  : <><XCircle size={13} color="var(--text-muted)" /> <span style={{ color: 'var(--text-muted)' }}>NOT TRAINED</span></>}
              </div>
            </div>

            {info.is_trained && info.metrics ? (
              <div style={{ background: 'var(--bg-base)', borderRadius: 8, padding: '10px 12px', border: '1px solid var(--border)', fontSize: 11 }}>
                {[
                  ['Test AUC', info.metrics.test_auc],
                  ['Test Accuracy', `${(info.metrics.test_accuracy * 100).toFixed(1)}%`],
                  ['CV AUC (avg)', info.metrics.cv_auc_avg],
                  ['Log Loss', info.metrics.test_logloss],
                  ['Train Samples', info.metrics.train_samples?.toLocaleString()],
                  ['Test Samples', info.metrics.test_samples?.toLocaleString()],
                  ['Horizon Bars', info.metrics.horizon_bars],
                  ['Features', info.metrics.n_features],
                ].map(([label, value]) => (
                  <div key={label} style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0' }}>
                    <span style={{ color: 'var(--text-muted)' }}>{label}</span>
                    <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{value}</span>
                  </div>
                ))}

                {info.metrics.cv_auc_scores && (
                  <div style={{ marginTop: 8 }}>
                    <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4 }}>CV FOLD AUC SCORES</div>
                    <div style={{ display: 'flex', gap: 4 }}>
                      {info.metrics.cv_auc_scores.map((s, i) => (
                        <div key={i} style={{
                          flex: 1, textAlign: 'center', fontSize: 10, fontFamily: 'var(--font-mono)',
                          padding: '3px 2px', borderRadius: 4,
                          background: s > 0.55 ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.1)',
                          color: s > 0.55 ? 'var(--accent-green)' : 'var(--text-muted)',
                        }}>{s}</div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div style={{ color: 'var(--text-muted)', fontSize: 12, padding: '8px 0' }}>
                No model trained yet. Click "Retrain All" to start.
              </div>
            )}

            {info.trained_at && (
              <div style={{ marginTop: 8, fontSize: 10, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 5, fontFamily: 'var(--font-mono)' }}>
                <Clock size={10} />
                {new Date(info.trained_at).toLocaleString()}
              </div>
            )}

            <button
              onClick={() => triggerRetrain(asset)}
              disabled={retraining}
              style={{
                marginTop: 10, width: '100%',
                background: 'var(--bg-elevated)', border: '1px solid var(--border-bright)',
                borderRadius: 7, padding: '6px 0',
                color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', fontSize: 11,
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5,
              }}>
              <RefreshCw size={10} /> RETRAIN {asset}
            </button>
          </div>
        ))}
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
