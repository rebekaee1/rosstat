import { useState, useMemo, useRef, useCallback, useEffect, useDeferredValue } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Check, Copy, ChevronDown, Search, BarChart3, CreditCard, Table2, ScrollText, GitCompare, X } from 'lucide-react';
import { useIndicators } from '../lib/hooks';
import { CATEGORIES, isIndicatorListed } from '../lib/categories';
import { cn } from '../lib/format';
import { useElementWidth } from '../lib/chartHooks';
import useMediaQuery from '../lib/useMediaQuery';
import useDocumentMeta from '../lib/useMeta';
import { getPageSeo } from '../lib/pageMeta';
import { PERIODS } from '../embed/useEmbedParams';
import { track, events } from '../lib/track';
import useSearchTracking from '../lib/useSearchTracking';
import { filterSearchOptions } from '../lib/searchSynonyms';
import { SITE_ORIGIN } from '../lib/siteOrigin';
import { russiaIndicatorPath } from '../lib/sitePaths';
import { useLocale, useT } from '../i18n';
import Breadcrumbs from '../components/Breadcrumbs';
import Button from '../components/Button';
import Chip from '../components/Chip';
import Spinner from '../components/Spinner';
import { toolTrail } from '../lib/breadcrumbs';
import '../styles/platform-pages.css';
import '../styles/w5-tools.css';
import '../styles/w6-g.css';
import '../styles/z8-tools.css';

const WIDGET_TYPES = [
  { key: 'chart', labelKey: 'embed.type.chart', descKey: 'w5.embed.type.chartHint', icon: BarChart3 },
  { key: 'card', labelKey: 'embed.type.card', descKey: 'w5.embed.type.cardHint', icon: CreditCard },
  { key: 'table', labelKey: 'embed.type.table', descKey: 'w5.embed.type.tableHint', icon: Table2 },
  { key: 'ticker', labelKey: 'w5.embed.type.ticker', descKey: 'w5.embed.type.tickerHint', icon: ScrollText },
  { key: 'compare', labelKey: 'embed.type.compare', descKey: 'w5.embed.type.compareHint', icon: GitCompare },
];

// Как вставить: человеческие названия вместо iframe / SVG / Badge.
const CODE_FORMATS = [
  { key: 'iframe', labelKey: 'w5.embed.fmt.iframe', hintKey: 'w5.embed.fmt.iframeHint' },
  { key: 'svg', labelKey: 'w5.embed.fmt.svg', hintKey: 'w5.embed.fmt.svgHint' },
  { key: 'markdown', labelKey: 'w5.embed.fmt.markdown', hintKey: 'w5.embed.fmt.markdownHint' },
  { key: 'badge', labelKey: 'w5.embed.fmt.badge', hintKey: 'w5.embed.fmt.badgeHint' },
];

const SIZE_PRESETS = [
  { labelKey: 'embed.size.small', w: 360, h: 240 },
  { labelKey: 'embed.size.medium', w: 600, h: 400 },
  { labelKey: 'embed.size.large', w: 800, h: 500 },
];

const EMBED_ORIGIN = SITE_ORIGIN;

function escHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function IndicatorCombobox({ indicators, value, onChange, placeholder }) {
  const t = useT();
  const { locale } = useLocale();
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const deferredSearch = useDeferredValue(search);
  const ref = useRef(null);

  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const grouped = useMemo(() => {
    const pool = (indicators || []).filter(isIndicatorListed);
    const filtered = filterSearchOptions(pool, deferredSearch, {
      getSearchItem: (item) => ({ ...item, country_slug: 'russia' }),
    });
    return CATEGORIES
      .map(cat => ({
        ...cat,
        items: filtered.filter((i) => (i.category_ru || i.category) === cat.apiCategory),
      }))
      .filter(g => g.items.length > 0);
  }, [indicators, deferredSearch]);

  const resultCount = useMemo(
    () => grouped.reduce((n, g) => n + g.items.length, 0),
    [grouped],
  );
  useSearchTracking('embed-builder', open ? deferredSearch : '', resultCount);

  const selected = indicators?.find(i => i.code === value);

  return (
    <div ref={ref} className="relative">
      <button type="button" onClick={() => setOpen(o => !o)}
        aria-haspopup="listbox" aria-expanded={open}
        className="fe-tap fe-press w-full min-h-11 flex items-center justify-between gap-2 px-3 py-2.5 rounded-xl text-sm text-text-primary transition-colors text-left fe-glass-2">
        <span className="truncate">{selected?.name || placeholder || t('w6g.embed.pickIndicator')}</span>
        <ChevronDown className={cn('w-4 h-4 text-text-secondary transition-transform', open && 'rotate-180')} />
      </button>
      {open && (
        <div className="absolute z-50 left-0 right-0 mt-1 rounded-xl shadow-2xl overflow-hidden fe-glass-pop" style={{ maxHeight: 340 }}>
          <div className="p-2 fe-divider-b">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-secondary" />
              <input type="text" value={search} onChange={e => setSearch(e.target.value)}
                placeholder={t('embed.search')} autoFocus
                className="w-full pl-8 pr-3 py-2 bg-obsidian-lighter rounded-lg text-sm text-text-primary placeholder:text-text-tertiary border-none outline-none" />
            </div>
          </div>
          <div className="overflow-y-auto" style={{ maxHeight: 280 }}>
            {grouped.map(cat => (
              <div key={cat.slug}>
                <div className="px-3 py-1.5 text-xs text-text-secondary font-semibold bg-surface-hover sticky top-0">
                  {locale === 'en' && cat.nameEn ? cat.nameEn : cat.name}
                </div>
                {cat.items.map(ind => (
                  <button key={ind.code} type="button"
                    onClick={() => { onChange(ind.code); setOpen(false); setSearch(''); }}
                    className={cn(
                      'fe-tap w-full text-left px-3 py-2 text-sm hover:bg-champagne/5 transition-colors flex items-center justify-between',
                      ind.code === value && 'bg-champagne/10 text-champagne-ink'
                    )}>
                    <span className="truncate">{ind.name}</span>
                    {ind.code === value && <Check className="w-3.5 h-3.5 text-champagne-ink flex-shrink-0" />}
                  </button>
                ))}
              </div>
            ))}
            {grouped.length === 0 && (
              <div className="px-3 py-6 text-center text-sm text-text-secondary">{t('embed.nothingFound')}</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function CopyButton({ text, onCopy }) {
  const t = useT();
  // 'idle' | 'copied' | 'failed' — итог виден глазами и озвучивается через aria-live.
  const [state, setState] = useState('idle');
  const timerRef = useRef(null);
  useEffect(() => () => clearTimeout(timerRef.current), []);
  const settle = useCallback((next) => {
    setState(next);
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setState('idle'), next === 'copied' ? 2500 : 4000);
  }, []);
  const handleCopy = useCallback(() => {
    const write = navigator.clipboard?.writeText
      ? navigator.clipboard.writeText(text)
      : Promise.reject(new Error('clipboard unavailable'));
    write.then(() => {
      settle('copied');
      onCopy?.();
    }).catch(() => settle('failed'));
  }, [text, onCopy, settle]);

  const copied = state === 'copied';
  return (
    <div className="flex flex-col items-start gap-2">
      <Button
        variant={copied ? 'secondary' : 'primary'}
        onClick={handleCopy}
        className={copied ? 'fe-ink-pos' : undefined}
      >
        {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
        {copied ? t('embed.copied') : t('embed.copyCode')}
      </Button>
      <span role="status" aria-live="polite" className={state === 'failed' ? 'max-w-[14rem] text-xs fe-ink-neg' : 'sr-only'}>
        {state === 'failed' ? t('pgui.embed.copyFailed') : (copied ? t('embed.copied') : '')}
      </span>
    </div>
  );
}

export default function EmbedBuilder() {
  const { locale } = useLocale();
  const t = useT();
  const widgetsSeo = getPageSeo('widgets', locale);
  useDocumentMeta({
    title: widgetsSeo.title,
    description: widgetsSeo.description,
    path: widgetsSeo.path,
  });

  const { data: indicators } = useIndicators();
  const [searchParams] = useSearchParams();
  const compactPreview = useMediaQuery('(max-width: 1023px)');

  const [type, setType] = useState('chart');
  // С карточки показателя приходят по «Встроить» с ?code=…; без него показываем понятный пример: курс доллара.
  const [code, setCode] = useState(() => {
    const fromUrl = (searchParams.get('code') || '').trim().toLowerCase();
    return /^[a-z0-9-]{2,64}$/.test(fromUrl) ? fromUrl : 'usd-rub';
  });
  const [codeB, setCodeB] = useState('eur-rub');
  const [period, setPeriod] = useState('1y');
  const [theme, setTheme] = useState('light');
  const [sizePreset, setSizePreset] = useState(1);
  const [customW, setCustomW] = useState(600);
  const [customH, setCustomH] = useState(400);
  const [showTitle, setShowTitle] = useState(true);
  const [showForecast, setShowForecast] = useState(false);
  const [limit, setLimit] = useState(12);
  const [tickerList, setTickerList] = useState(['usd-rub', 'key-rate', 'cpi']);
  const tickerCodes = tickerList.join(',');
  const [speed, setSpeed] = useState('normal');
  const [codeTab, setCodeTab] = useState('iframe');
  // На телефоне закреплённый предпросмотр можно свернуть до одной строки: под ним остаётся место для настроек.
  const [previewOpen, setPreviewOpen] = useState(true);

  const isCustom = sizePreset === -1;
  const w = isCustom ? customW : SIZE_PRESETS[sizePreset]?.w || 600;
  const h = isCustom ? customH : SIZE_PRESETS[sizePreset]?.h || 400;

  const previewUrl = useMemo(() => {
    const base = window.location.origin;
    const params = new URLSearchParams();
    params.set('theme', theme);
    params.set('title', showTitle.toString());

    switch (type) {
      case 'chart':
        params.set('period', period);
        params.set('height', h.toString());
        params.set('forecast', showForecast.toString());
        return `${base}/embed/chart/${code}?${params}`;
      case 'card':
        return `${base}/embed/card/${code}?${params}`;
      case 'table':
        params.set('limit', limit.toString());
        return `${base}/embed/table/${code}?${params}`;
      case 'ticker':
        params.set('codes', tickerCodes);
        params.set('speed', speed);
        return `${base}/embed/ticker?${params}`;
      case 'compare':
        params.set('a', code);
        params.set('b', codeB);
        params.set('period', period);
        params.set('height', h.toString());
        return `${base}/embed/compare?${params}`;
      default:
        return '';
    }
  }, [type, code, codeB, period, theme, h, showTitle, showForecast, limit, tickerCodes, speed]);

  const embedCode = useMemo(() => {
    const meta = indicators?.find(i => i.code === code);
    const name = meta?.name || code;
    const prodParams = new URLSearchParams();
    prodParams.set('theme', theme);
    prodParams.set('title', showTitle.toString());

    let src, iframeW, iframeH, title;

    switch (type) {
      case 'chart':
        prodParams.set('period', period);
        prodParams.set('height', h.toString());
        prodParams.set('forecast', showForecast.toString());
        src = `${EMBED_ORIGIN}/embed/chart/${code}?${prodParams}`;
        iframeW = w; iframeH = h;
        title = `${name} — forecasteconomy`;
        break;
      case 'card':
        src = `${EMBED_ORIGIN}/embed/card/${code}?${prodParams}`;
        iframeW = 320; iframeH = 200;
        title = `${name} — forecasteconomy`;
        break;
      case 'table':
        prodParams.set('limit', limit.toString());
        src = `${EMBED_ORIGIN}/embed/table/${code}?${prodParams}`;
        iframeW = w; iframeH = Math.max(200, limit * 40 + 80);
        title = t('embed.tableTitle', { name });
        break;
      case 'ticker':
        prodParams.set('codes', tickerCodes);
        prodParams.set('speed', speed);
        src = `${EMBED_ORIGIN}/embed/ticker?${prodParams}`;
        iframeW = '100%'; iframeH = 40;
        title = t('w6g.embed.defaultTitle');
        break;
      case 'compare': {
        const metaB = indicators?.find(i => i.code === codeB);
        prodParams.set('a', code);
        prodParams.set('b', codeB);
        prodParams.set('period', period);
        prodParams.set('height', h.toString());
        src = `${EMBED_ORIGIN}/embed/compare?${prodParams}`;
        iframeW = w; iframeH = h;
        title = `${name} vs ${metaB?.name || codeB}`;
        break;
      }
      default: src = ''; iframeW = w; iframeH = h; title = '';
    }

    const widthAttr = iframeW === '100%' ? 'width="100%"' : `width="${iframeW}"`;

    if (codeTab === 'iframe') {
      const t = escHtml(title);
      return `<!-- ${t} -->\n<iframe src="${src}"\n  ${widthAttr} height="${iframeH}" frameborder="0"\n  style="border: none; border-radius: 12px; overflow: hidden;"\n  title="${t}" loading="lazy"\n  allow="clipboard-write"></iframe>`;
    }

    if (codeTab === 'markdown') {
      if (type === 'ticker') {
        return tickerCodes.split(',').filter(Boolean).map(c => {
          const n = indicators?.find(i => i.code === c.trim())?.name || c.trim();
          return `[![${n}](${EMBED_ORIGIN}/api/v1/embed/badge/${c.trim()}.svg?theme=${theme})](${EMBED_ORIGIN}${russiaIndicatorPath(c.trim())})`;
        }).join(' ');
      }
      if (type === 'compare') {
        const nameB = indicators?.find(i => i.code === codeB)?.name || codeB;
        return `[![${name}](${EMBED_ORIGIN}/api/v1/embed/spark/${code}.svg?period=${period}&w=300&h=80)](${EMBED_ORIGIN}${russiaIndicatorPath(code)}) [![${nameB}](${EMBED_ORIGIN}/api/v1/embed/spark/${codeB}.svg?period=${period}&w=300&h=80)](${EMBED_ORIGIN}${russiaIndicatorPath(codeB)})`;
      }
      if (type === 'card') return `[![${name}](${EMBED_ORIGIN}/api/v1/embed/card/${code}.svg?theme=${theme})](${EMBED_ORIGIN}${russiaIndicatorPath(code)})`;
      return `[![${name}](${EMBED_ORIGIN}/api/v1/embed/spark/${code}.svg?period=${period}&w=600&h=100)](${EMBED_ORIGIN}${russiaIndicatorPath(code)})`;
    }

    if (codeTab === 'svg') {
      const cw = Math.min(w, 600);
      const ch = Math.min(h, 400);
      if (type === 'card') return `<a href="${EMBED_ORIGIN}${russiaIndicatorPath(code)}" target="_blank">\n  <img src="${EMBED_ORIGIN}/api/v1/embed/card/${code}.svg?theme=${theme}&w=${cw}&h=${ch}"\n    alt="${escHtml(name)}" width="${cw}" height="${ch}">\n</a>`;
      if (type === 'ticker') {
        return tickerCodes.split(',').filter(Boolean).map(c => {
          const n = indicators?.find(i => i.code === c.trim())?.name || c.trim();
          return `<a href="${EMBED_ORIGIN}${russiaIndicatorPath(c.trim())}" target="_blank"><img src="${EMBED_ORIGIN}/api/v1/embed/badge/${c.trim()}.svg?theme=${theme}" alt="${escHtml(n)}"></a>`;
        }).join('\n');
      }
      if (type === 'compare') {
        const nameB = indicators?.find(i => i.code === codeB)?.name || codeB;
        return `<a href="${EMBED_ORIGIN}${russiaIndicatorPath(code)}" target="_blank">\n  <img src="${EMBED_ORIGIN}/api/v1/embed/spark/${code}.svg?period=${period}&w=${cw}&h=60"\n    alt="${escHtml(name)}" width="${cw}" height="60">\n</a>\n<a href="${EMBED_ORIGIN}${russiaIndicatorPath(codeB)}" target="_blank">\n  <img src="${EMBED_ORIGIN}/api/v1/embed/spark/${codeB}.svg?period=${period}&w=${cw}&h=60"\n    alt="${escHtml(nameB)}" width="${cw}" height="60">\n</a>`;
      }
      return `<a href="${EMBED_ORIGIN}${russiaIndicatorPath(code)}" target="_blank">\n  <img src="${EMBED_ORIGIN}/api/v1/embed/spark/${code}.svg?period=${period}&w=${cw}&h=60"\n    alt="${escHtml(name)}" width="${cw}" height="60">\n</a>`;
    }

    if (codeTab === 'badge') {
      if (type === 'ticker') {
        return tickerCodes.split(',').filter(Boolean).map(c => {
          const n = indicators?.find(i => i.code === c.trim())?.name || c.trim();
          return `[![${n}](${EMBED_ORIGIN}/api/v1/embed/badge/${c.trim()}.svg?theme=${theme})](${EMBED_ORIGIN}${russiaIndicatorPath(c.trim())})`;
        }).join('\n');
      }
      if (type === 'compare') {
        const nameB = indicators?.find(i => i.code === codeB)?.name || codeB;
        return `[![${name}](${EMBED_ORIGIN}/api/v1/embed/badge/${code}.svg?theme=${theme})](${EMBED_ORIGIN}${russiaIndicatorPath(code)})\n[![${nameB}](${EMBED_ORIGIN}/api/v1/embed/badge/${codeB}.svg?theme=${theme})](${EMBED_ORIGIN}${russiaIndicatorPath(codeB)})`;
      }
      return `[![${name}](${EMBED_ORIGIN}/api/v1/embed/badge/${code}.svg?theme=${theme})](${EMBED_ORIGIN}${russiaIndicatorPath(code)})`;
    }

    return '';
  }, [type, code, codeB, period, theme, w, h, showTitle, showForecast, limit, tickerCodes, speed, codeTab, indicators, t]);

  const needsSecondIndicator = type === 'compare';
  const needsPeriod = type === 'chart' || type === 'compare';
  const needsSize = type === 'chart' || type === 'table' || type === 'compare';
  const needsLimit = type === 'table';
  const needsTicker = type === 'ticker';
  const needsForecast = type === 'chart';
  const needsIndicator = type !== 'ticker';
  const previewH = type === 'ticker' ? 40 : type === 'card' ? 200 : h;
  const previewBoxW = type === 'ticker' ? '100%' : Math.min(w, 760);
  // Превью целиком вписывается в ширину экрана: виджет рисуется в «настоящей» ширине
  // (не уже 360 px) и масштабируется, а не обрезается справа.
  const [setStageNode, stageWidth] = useElementWidth();
  const availW = Math.max(0, stageWidth);
  const fitsAsIs = typeof previewBoxW === 'string' || availW === 0 || previewBoxW <= availW;
  const renderW = typeof previewBoxW === 'string'
    ? previewBoxW
    : (fitsAsIs ? previewBoxW : Math.min(previewBoxW, Math.max(360, availW)));
  const widthScale = typeof renderW === 'number' && availW > 0 && renderW > availW ? availW / renderW : 1;
  // Закреплённый предпросмотр на телефоне не должен съедать экран: ограничиваем высоту.
  const maxPreviewH = compactPreview ? 84 : Infinity;
  const heightScale = previewH > maxPreviewH ? maxPreviewH / previewH : 1;
  const previewScale = Math.min(widthScale, heightScale);
  const previewW = renderW;
  // Превью грузится в iframe: пока он не сообщил о загрузке, показываем кольцо ожидания.
  // Не загрузился за 12 секунд — понятная ошибка с кнопкой «Повторить», а не пустой прямоугольник.
  const [loadedUrl, setLoadedUrl] = useState('');
  const [failedUrl, setFailedUrl] = useState('');
  const [attempt, setAttempt] = useState(0);
  const previewFailed = failedUrl === previewUrl && loadedUrl !== previewUrl;
  const previewLoading = loadedUrl !== previewUrl && !previewFailed;
  useEffect(() => {
    if (!previewLoading) return undefined;
    const timer = setTimeout(() => setFailedUrl(previewUrl), 12000);
    return () => clearTimeout(timer);
  }, [previewLoading, previewUrl, attempt]);
  const retryPreview = () => {
    setFailedUrl('');
    setAttempt((n) => n + 1);
  };

  const activeFormat = CODE_FORMATS.find((f) => f.key === codeTab) || CODE_FORMATS[0];
  const nameOf = (c) => indicators?.find((i) => i.code === c)?.name || c;
  const stageBg = theme === 'dark' ? '#111' : '#f5f5f5';

  return (
    <div className="fe-data-page fe-gutter w5-embed max-w-6xl mx-auto pt-24 md:pt-28 pb-12 sm:pb-16">
      <Breadcrumbs items={toolTrail(t('w6g.embed.crumb'), widgetsSeo.path)} className="mb-6" />
      <header className="mb-8 max-w-2xl">
        <h1 className="mb-3 font-display text-3xl font-bold text-text-primary md:text-4xl">
          {t('embed.constructor')}
        </h1>
        <p className="text-text-secondary">{t('w5.embed.intro')}</p>
      </header>

      {/* Шаг 1: что вставить */}
      <h2 className="mb-3 text-base font-semibold text-text-primary">{t('w5.embed.step1')}</h2>
      <div className="w5-embed-types" role="group" aria-label={t('w5.embed.step1')}>
        {WIDGET_TYPES.map((wt) => (
          <button
            key={wt.key}
            type="button"
            aria-pressed={type === wt.key}
            className={cn('w5-embed-type fe-press', type === wt.key && 'is-active')}
            onClick={() => { setType(wt.key); track(events.EMBED_TYPE_CHANGE, { type: wt.key }); }}
          >
            <wt.icon className="w5-embed-type__icon" aria-hidden="true" />
            <span className="w5-embed-type__name">{t(wt.labelKey)}</span>
            <span className="w5-embed-type__hint">{t(wt.descKey)}</span>
          </button>
        ))}
      </div>

      <div className="fe-w6g-embed-grid">
        {/* Предпросмотр закреплён сверху: изменения видно сразу */}
        <section className={cn('w5-embed-preview fe-w6g-embed-preview', !previewOpen && 'is-collapsed')} aria-label={t('w5.embed.previewHeading')}>
            <div className="w5-embed-preview__head">
              <h2 className="text-base font-semibold text-text-primary">{t('w5.embed.previewHeading')}</h2>
              <div className="flex items-center gap-2">
                <CopyButton text={embedCode} onCopy={() => track(events.EMBED_CODE_COPY, { format: codeTab })} />
                <button
                  type="button"
                  className="fe-w7p-preview-toggle fe-press"
                  aria-expanded={previewOpen}
                  aria-label={previewOpen ? t('w7p.embed.collapse') : t('w7p.embed.expand')}
                  onClick={() => setPreviewOpen((v) => !v)}
                >
                  <ChevronDown className={cn('h-4 w-4 transition-transform', previewOpen && 'rotate-180')} aria-hidden="true" />
                </button>
              </div>
            </div>
            <div ref={setStageNode} className="w5-embed-preview__stage" style={{ background: stageBg }}>
              <div
                className="relative"
                style={previewScale < 1
                  ? { width: previewW * previewScale, height: previewH * previewScale }
                  : { width: previewW, height: previewH, maxWidth: '100%' }}
              >
                <div
                  className="absolute left-0 top-0"
                  style={previewScale < 1
                    ? { width: previewW, height: previewH, transform: `scale(${previewScale})`, transformOrigin: 'top left' }
                    : { width: '100%', height: '100%' }}
                >
                <iframe
                  key={`${previewUrl}#${attempt}`}
                  src={previewUrl}
                  width="100%"
                  height="100%"
                  frameBorder="0"
                  style={{ border: 'none', borderRadius: 12, overflow: 'hidden', maxWidth: '100%' }}
                  title={t('pgui.embed.previewTitle')}
                  onLoad={() => { setLoadedUrl(previewUrl); setFailedUrl(''); }}
                />
                </div>
                {(previewLoading || previewFailed) && (
                  <div
                    className={cn('w5-embed-preview__state', theme === 'dark' && 'is-dark')}
                    role={previewFailed ? 'alert' : 'status'}
                  >
                    {previewFailed ? (
                      <>
                        <p className="max-w-xs text-sm font-medium">{t('y1.embed.previewFailed')}</p>
                        <p className="max-w-xs text-xs opacity-80">{t('y1.embed.previewFailedHint')}</p>
                        <Button variant="secondary" size="sm" onClick={retryPreview}>{t('y1.embed.previewRetry')}</Button>
                      </>
                    ) : (
                      <>
                        <Spinner size={22} />
                        <span className="text-sm">{t('pgui.embed.previewLoading')}</span>
                      </>
                    )}
                  </div>
                )}
              </div>
            </div>
        </section>

        {/* Шаг 2: настройки */}
        <div className="space-y-5 fe-w6g-embed-settings">
          <div className="space-y-5 rounded-3xl p-5 fe-glass-lite">
            <h2 className="text-base font-semibold text-text-primary">{t('w5.embed.step2')}</h2>

            {needsIndicator && (
              <div className="w5-embed-field">
                <span className="w5-embed-label">{t('w6g.embed.indicator')}</span>
                <IndicatorCombobox indicators={indicators} value={code} onChange={(c) => { setCode(c); track(events.EMBED_INDICATOR_SELECT, { code: c }); }} />
              </div>
            )}

            {needsSecondIndicator && (
              <div className="w5-embed-field">
                <span className="w5-embed-label">{t('w6g.embed.indicatorB')}</span>
                <IndicatorCombobox indicators={indicators} value={codeB} onChange={(c) => { setCodeB(c); track(events.EMBED_INDICATOR_SELECT, { code: c, position: 'b' }); }} />
              </div>
            )}

            {needsTicker && (
              <div className="w5-embed-field">
                <span className="w5-embed-label">{t('w5.embed.tickerItems')}</span>
                {tickerList.length > 0 && (
                  <ul className="flex flex-wrap gap-2">
                    {tickerList.map((c) => (
                      <li key={c}>
                        <button
                          type="button"
                          onClick={() => setTickerList((list) => list.filter((x) => x !== c))}
                          aria-label={t('w5.embed.tickerRemove', { name: nameOf(c) })}
                          className="fe-chip fe-press is-active max-w-full gap-1.5"
                        >
                          <span className="truncate">{nameOf(c)}</span>
                          <X className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
                <IndicatorCombobox
                  indicators={indicators}
                  value=""
                  placeholder={t('w5.embed.tickerAdd')}
                  onChange={(c) => { setTickerList((list) => (list.includes(c) ? list : [...list, c].slice(0, 12))); track(events.EMBED_INDICATOR_SELECT, { code: c, position: 'ticker' }); }}
                />
                <div className="w5-embed-seg">
                  {['slow', 'normal', 'fast'].map((sp) => (
                    <Chip key={sp} active={speed === sp} onClick={() => setSpeed(sp)}>
                      {sp === 'slow' ? t('embed.speed.slow') : sp === 'normal' ? t('embed.speed.normal') : t('embed.speed.fast')}
                    </Chip>
                  ))}
                </div>
              </div>
            )}

            {needsPeriod && (
              <div className="w5-embed-field">
                <span className="w5-embed-label">{t('embed.period')}</span>
                <div className="w5-embed-seg">
                  {PERIODS.map((pr) => (
                    <Chip key={pr.key} active={period === pr.key} onClick={() => { setPeriod(pr.key); track(events.EMBED_PERIOD_CHANGE, { period: pr.key }); }}>
                      {t(pr.labelKey)}
                    </Chip>
                  ))}
                </div>
              </div>
            )}

            <div className="w5-embed-field">
              <span className="w5-embed-label">{t('w5.embed.look')}</span>
              <div className="w5-embed-seg">
                {[['light', t('embed.theme.light')], ['dark', t('embed.theme.dark')], ['auto', t('embed.theme.auto')]].map(([k, l]) => (
                  <Chip key={k} active={theme === k} onClick={() => { setTheme(k); track(events.EMBED_THEME_CHANGE, { theme: k }); }}>
                    {l}
                  </Chip>
                ))}
              </div>
            </div>

            {needsSize && (
              <div className="w5-embed-field">
                <span className="w5-embed-label">{t('embed.size')}</span>
                <div className="w5-embed-seg w5-embed-seg--4">
                  {SIZE_PRESETS.map((sp, i) => (
                    <Chip key={i} active={sizePreset === i} onClick={() => { setSizePreset(i); track(events.EMBED_SIZE_CHANGE, { size: SIZE_PRESETS[i].labelKey }); }}>
                      {t(sp.labelKey)}
                    </Chip>
                  ))}
                  <Chip active={isCustom} onClick={() => { setSizePreset(-1); setCustomW(w); setCustomH(h); }}>
                    {t('embed.size.custom')}
                  </Chip>
                </div>
                {isCustom && (
                  <div className="flex items-center gap-2">
                    <input type="number" inputMode="numeric" value={customW} onChange={(e) => setCustomW(Math.max(200, +e.target.value))} min={200} max={1200}
                      aria-label={t('w5.embed.width')}
                      className="fe-tap w-24 rounded-xl px-2 py-1 text-center text-sm text-text-primary outline-none fe-glass-2" />
                    <span className="text-xs text-text-secondary" aria-hidden="true">×</span>
                    <input type="number" inputMode="numeric" value={customH} onChange={(e) => setCustomH(Math.max(100, +e.target.value))} min={100} max={800}
                      aria-label={t('w5.embed.height')}
                      className="fe-tap w-24 rounded-xl px-2 py-1 text-center text-sm text-text-primary outline-none fe-glass-2" />
                    <span className="text-xs text-text-secondary">px</span>
                  </div>
                )}
              </div>
            )}

            {needsLimit && (
              <div className="w5-embed-field">
                <span className="w5-embed-label">{t('embed.rowCount')}</span>
                <input type="number" inputMode="numeric" value={limit} onChange={(e) => setLimit(Math.max(1, Math.min(50, +e.target.value)))} min={1} max={50}
                  aria-label={t('embed.rowCount')}
                  className="fe-tap w-24 rounded-xl px-2 py-1 text-center text-sm text-text-primary outline-none fe-glass-2" />
              </div>
            )}

            <div className="space-y-1 pt-3 fe-divider">
              <label className="w5-check">
                <input type="checkbox" checked={showTitle} onChange={(e) => { setShowTitle(e.target.checked); track(events.EMBED_OPTION_TOGGLE, { option: 'title', value: e.target.checked }); }} />
                <span>{t('embed.showTitle')}</span>
              </label>
              {needsForecast && (
                <label className="w5-check">
                  <input type="checkbox" checked={showForecast} onChange={(e) => { setShowForecast(e.target.checked); track(events.EMBED_OPTION_TOGGLE, { option: 'forecast', value: e.target.checked }); }} />
                  <span>{t('embed.showForecast')}</span>
                </label>
              )}
            </div>
          </div>

          <div className="rounded-2xl p-4 fe-glass-lite">
            <p className="mb-1 text-sm font-semibold text-text-primary">{t('w5.embed.terms')}</p>
            <p className="text-sm leading-relaxed text-text-secondary">
              {t('embed.termsBody')} <Link to="/about" className="text-champagne-ink underline underline-offset-2">{t('embed.termsAbout')}</Link>.
            </p>
          </div>
        </div>

        {/* Код для вставки */}
        <section className="w5-embed-code fe-w6g-embed-code" aria-label={t('w5.embed.step3')}>
            <div className="w5-embed-code__head">
              <div>
                <h2 className="text-base font-semibold text-text-primary">{t('w5.embed.step3')}</h2>
                <p className="mt-1 text-sm text-text-secondary">{t('w5.embed.step3Hint')}</p>
              </div>
            </div>
            <div className="space-y-2 px-4 pb-4">
              <span className="w5-embed-label">{t('w5.embed.fmt.title')}</span>
              <div className="w5-embed-seg w5-embed-seg--fmt">
                {CODE_FORMATS.map((f) => (
                  <Chip key={f.key} active={codeTab === f.key} onClick={() => { setCodeTab(f.key); track(events.EMBED_CODE_TAB, { tab: f.key }); }}>
                    {t(f.labelKey)}
                  </Chip>
                ))}
              </div>
              <p className="text-sm text-text-secondary">{t(activeFormat.hintKey)}</p>
            </div>
            <details open className="">
              <summary className="flex min-h-12 cursor-pointer items-center justify-between gap-2 px-4 text-sm font-semibold text-champagne-ink">
                {t('w6g.embed.codeSummary')}
                <ChevronDown className="h-4 w-4" aria-hidden="true" />
              </summary>
              <pre className="w5-embed-code__pre">{embedCode}</pre>
            </details>
        </section>
      </div>
    </div>
  );
}
