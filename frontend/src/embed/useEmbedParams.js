import { useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';

export function useEmbedParams() {
  const [params] = useSearchParams();
  return {
    theme: params.get('theme') === 'dark' ? 'dark' : 'light',
    height: Math.max(100, parseInt(params.get('height')) || 400),
    period: params.get('period') || '5y',
    showTitle: params.get('title') !== 'false',
    showForecast: params.get('forecast') === 'true',
    limit: Math.min(100, Math.max(1, parseInt(params.get('limit')) || 12)),
    codes: (params.get('codes') || '').split(',').filter(Boolean),
    speed: params.get('speed') || 'normal',
    codeA: params.get('a') || '',
    codeB: params.get('b') || '',
  };
}

export function useEmbedImpression(code, type) {
  useEffect(() => {
    try {
      const blob = new Blob(
        [JSON.stringify({ code, type, referrer: document.referrer })],
        { type: 'application/json' },
      );
      navigator.sendBeacon('/api/v1/embed/impression', blob);
    } catch { /* non-critical */ }
  }, [code, type]);
}

export function useEmbedAutoHeight() {
  useEffect(() => {
    const send = () => {
      try {
        window.parent.postMessage(
          { type: 'fe-embed-resize', height: document.body.scrollHeight },
          '*',
        );
      } catch { /* cross-origin, ignore */ }
    };
    send();
    const ro = new ResizeObserver(send);
    ro.observe(document.body);
    return () => ro.disconnect();
  }, []);
}

export const PERIODS = [
  { key: '1m', label: '1М', months: 1 },
  { key: '3m', label: '3М', months: 3 },
  { key: '6m', label: '6М', months: 6 },
  { key: '1y', label: '1Г', months: 12 },
  { key: '5y', label: '5Л', months: 60 },
  { key: 'max', label: 'Макс', months: null },
];

export const THEME_COLORS = {
  light: {
    bg: '#FFFFFF', text: '#1a1a1a', textSecondary: '#666',
    textTertiary: '#999', border: '#e5e5e5', surface: '#f8f8f8',
    grid: 'rgba(0,0,0,0.06)', tick: 'rgba(0,0,0,0.4)',
  },
  dark: {
    bg: '#1a1a1e', text: '#e5e5e5', textSecondary: '#aaa',
    textTertiary: '#666', border: '#333', surface: '#252528',
    grid: 'rgba(255,255,255,0.08)', tick: 'rgba(255,255,255,0.4)',
  },
};
