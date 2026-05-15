import { useState, useEffect, useRef, useCallback } from 'react';
import { api } from '../utils/api';

export function useSignals(refreshIntervalSec = 300, extraParams = {}) {
  const [signals, setSignals]         = useState(null);
  const [topTrade, setTopTrade]       = useState(null);
  const [globalNewsAlert, setAlert]   = useState(false);
  const [loading, setLoading]         = useState(true);
  const [error, setError]             = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [nextRefreshIn, setNext]      = useState(refreshIntervalSec);
  const timerRef    = useRef(null);
  const countdownRef= useRef(null);

  const fetchSignals = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const data = await api.getAllSignals(extraParams);
      setSignals(data.signals);
      setTopTrade(data.top_trade);
      setAlert(data.global_news_alert);
      setLastUpdated(new Date());
      setNext(refreshIntervalSec);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshIntervalSec, JSON.stringify(extraParams)]);

  useEffect(() => {
    fetchSignals();
    timerRef.current     = setInterval(fetchSignals, refreshIntervalSec * 1000);
    countdownRef.current = setInterval(() => setNext(p => p <= 1 ? refreshIntervalSec : p - 1), 1000);
    return () => { clearInterval(timerRef.current); clearInterval(countdownRef.current); };
  }, [fetchSignals, refreshIntervalSec]);

  return { signals, topTrade, globalNewsAlert, loading, error, lastUpdated, nextRefreshIn, refresh: fetchSignals };
}

export function useBacktest(asset) {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const run = useCallback(async (config) => {
    setLoading(true); setError(null); setResult(null);
    try { setResult(await api.runBacktest(asset, config)); }
    catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }, [asset]);
  return { result, loading, error, run };
}

export function useModelStatus() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const fetch_ = useCallback(async () => {
    setLoading(true);
    try { setStatus(await api.getModelStatus()); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { fetch_(); }, [fetch_]);
  return { status, loading, refresh: fetch_ };
}
