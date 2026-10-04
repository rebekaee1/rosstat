import { useEffect, useRef, useSyncExternalStore } from 'react';
import { useSearchParams } from 'react-router-dom';
import { deltaTone, indicatorPolarity } from '../lib/deltaTone';

const MQ = typeof window !== 'undefined'
  ? window.matchMedia('(prefers-color-scheme: dark)')
  : null;

function subscribeMQ(cb) {
  MQ?.addEventListener('change', cb);
  return () => MQ?.removeEventListener('change', cb);
}

function getPrefersDark() {
  return MQ?.matches ?? false;
}

export function useEmbedParams() {
  const [params] = useSearchParams();
  const rawTheme = params.get('theme') || 'light';
  const prefersDark = useSyncExternalStore(subscribeMQ, getPrefersDark, () => false);
  const theme = rawTheme === 'dark' ? 'dark'
    : rawTheme === 'auto' && prefersDark ? 'dark'
    : 'light';

  return {
    theme,
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
  const sent = useRef(false);
  useEffect(() => {
    if (sent.current) return;
    sent.current = true;
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

const TONE_COLORS = {
  light: { good: '#15803d', bad: '#b91c1c' },
  dark: { good: '#69D29C', bad: '#F18A8A' },
};

/** Цвет изменения по смыслу показателя: рост инфляции — не зелёный; без понятного смысла — нейтрально. */
export function embedChangeColor(change, theme, colors, ...labels) {
  const tone = deltaTone(change, indicatorPolarity(...labels));
  if (tone === 'good' || tone === 'bad') return TONE_COLORS[theme][tone];
  return colors.textSecondary;
}

export const PERIODS = [
  { key: '1m', labelKey: 'w5.embed.period.1m', months: 1 },
  { key: '3m', labelKey: 'w5.embed.period.3m', months: 3 },
  { key: '6m', labelKey: 'w5.embed.period.6m', months: 6 },
  { key: '1y', labelKey: 'w5.embed.period.1y', months: 12 },
  { key: '5y', labelKey: 'w5.embed.period.5y', months: 60 },
  { key: 'max', labelKey: 'w5.embed.period.max', months: null },
];

export const THEME_COLORS = {
  light: {
    bg: '#F8FAFC', text: '#202A3C', textSecondary: '#526074',
    textTertiary: '#697587', border: '#D5DEE8', surface: '#EEF0F4',
    grid: 'rgba(0,0,0,0.06)', tick: 'rgba(0,0,0,0.4)',
  },
  dark: {
    bg: '#202A3C', text: '#EEF0F4', textSecondary: '#CAD8E5',
    textTertiary: '#A4B1C2', border: '#415064', surface: '#29374A',
    grid: 'rgba(255,255,255,0.08)', tick: 'rgba(255,255,255,0.4)',
  },
};
