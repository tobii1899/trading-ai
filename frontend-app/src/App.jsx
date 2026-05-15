import { useState } from 'react';
import { LayoutDashboard, BarChart2, Cpu, Database, Settings as SettingsIcon, User } from 'lucide-react';
import Header from './components/Header';
import AssetCard from './components/AssetCard';
import BacktestPanel from './components/BacktestPanel';
import ModelPanel from './components/ModelPanel';
import SignalHistory from './components/SignalHistory';
import TopTradeBanner from './components/TopTradeBanner';
import SettingsDrawer from './components/Settings';
import Profile from './components/Profile';
import { CardSkeleton, ErrorCard } from './components/Skeleton';
import { useSignals } from './hooks/useSignals';

const NAV = [
  { id: 'dashboard', label: 'Dashboard',  icon: LayoutDashboard },
  { id: 'signals',   label: 'Signals',    icon: Database },
  { id: 'backtest',  label: 'Backtesting',icon: BarChart2 },
  { id: 'models',    label: 'Models',     icon: Cpu },
  { id: 'profile',   label: 'Profile',    icon: User },
];

const DEFAULT_SETTINGS = {
  accountBalance: 5000,
  riskPerTradePct: 1.0,
  stopLossPct: 0.5,
  minProb: 60,
  refreshInterval: 300,
  feeEur: 2.0,
  feeMultiplier: 3.0,
  horizonBars: 6,
};

const ASSETS = ['XAU/USD', 'GBP/JPY', 'NASDAQ100'];

export default function App() {
  const [tab, setTab]               = useState('dashboard');
  const [settingsOpen, setSettings] = useState(false);
  const [cfg, setCfg]               = useState(DEFAULT_SETTINGS);

  const signalParams = {
    account_balance:    cfg.accountBalance,
    risk_per_trade_pct: cfg.riskPerTradePct,
    stop_loss_pct:      cfg.stopLossPct,
    min_probability:    cfg.minProb,
    fee_eur:            cfg.feeEur,
    fee_multiplier:     cfg.feeMultiplier,
    horizon_bars:       cfg.horizonBars,
  };

  const { signals, topTrade, globalNewsAlert, loading, error, lastUpdated, nextRefreshIn, refresh } =
    useSignals(cfg.refreshInterval, signalParams);

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Header lastUpdated={lastUpdated} nextRefreshIn={nextRefreshIn}
        loading={loading} onRefresh={refresh} globalAlert={globalNewsAlert} />

      {/* Nav */}
      <div style={{ borderBottom: '1px solid var(--border)', padding: '0 24px',
        display: 'flex', alignItems: 'center', gap: 2, background: 'var(--bg-surface)' }}>
        {NAV.map(({ id, label, icon: Icon }) => (
          <button key={id} onClick={() => setTab(id)} style={{
            background: 'transparent', border: 'none',
            borderBottom: tab === id ? '2px solid var(--accent-blue)' : '2px solid transparent',
            color: tab === id ? 'var(--text-primary)' : 'var(--text-muted)',
            padding: '12px 16px', fontSize: 12, fontFamily: 'var(--font-mono)',
            fontWeight: 600, letterSpacing: '0.05em',
            display: 'flex', alignItems: 'center', gap: 6,
            transition: 'var(--transition)', cursor: 'pointer',
          }}>
            <Icon size={13} />{label.toUpperCase()}
          </button>
        ))}
        <div style={{ flex: 1 }} />
        <button onClick={() => setSettings(true)} style={{ background: 'transparent',
          border: 'none', color: 'var(--text-muted)', padding: '10px 12px',
          display: 'flex', alignItems: 'center', gap: 5, fontSize: 12,
          fontFamily: 'var(--font-mono)', cursor: 'pointer' }}>
          <SettingsIcon size={13} /> SETTINGS
        </button>
      </div>

      <main style={{ flex: 1, paddingTop: 24 }}>
        {tab === 'dashboard' && (
          <>
            {!loading && topTrade && <TopTradeBanner trade={topTrade} />}
            <div style={{ padding: '0 24px 40px', display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 16 }}>
              {loading && !signals
                ? ASSETS.map(a => <CardSkeleton key={a} />)
                : error
                  ? <ErrorCard message={error} onRetry={refresh} />
                  : ASSETS.map(asset => (
                    <AssetCard key={asset} asset={asset} signal={signals?.[asset]}
                      isTop={topTrade?.asset === asset} />
                  ))}
            </div>

            {/* Status bar */}
            {signals && !error && (
              <div style={{ margin: '0 24px 24px', padding: '10px 16px',
                background: 'var(--bg-card)', border: '1px solid var(--border)',
                borderRadius: 10, fontSize: 11, color: 'var(--text-muted)',
                display: 'flex', gap: 24, flexWrap: 'wrap', fontFamily: 'var(--font-mono)' }}>
                <span>Account: <strong style={{color:'var(--accent-blue)'}}>€{cfg.accountBalance.toLocaleString()}</strong></span>
                <span>Risk/trade: <strong style={{color:'var(--accent-amber)'}}>{cfg.riskPerTradePct}%</strong></span>
                <span>Stop loss: <strong style={{color:'var(--accent-red)'}}>{cfg.stopLossPct}%</strong></span>
                <span>Min prob: <strong style={{color:'var(--text-secondary)'}}>{cfg.minProb}%</strong></span>
                <span>Fee: <strong style={{color:'var(--text-secondary)'}}>€{cfg.feeEur} × {cfg.feeMultiplier}x min</strong></span>
                <span style={{marginLeft:'auto', fontSize:10}}>⚠ Not financial advice.</span>
              </div>
            )}
          </>
        )}
        {tab === 'signals'   && <SignalHistory />}
        {tab === 'backtest'  && <BacktestPanel />}
        {tab === 'models'    && <ModelPanel />}
        {tab === 'profile'   && <Profile />}
      </main>

      <SettingsDrawer open={settingsOpen} onClose={() => setSettings(false)}
        settings={cfg} onChange={(k, v) => setCfg(s => ({ ...s, [k]: v }))} />
    </div>
  );
}
