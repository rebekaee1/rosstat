import { useState, useMemo, useRef, useCallback, useEffect } from 'react';
import { Check, Copy, Code2, Image, ChevronDown, Search, BarChart3, CreditCard, Table2, ScrollText, GitCompare } from 'lucide-react';
import { useIndicators } from '../lib/hooks';
import { CATEGORIES, HIDDEN_FROM_LISTING } from '../lib/categories';
import { cn } from '../lib/format';
import useDocumentMeta from '../lib/useMeta';
import { PERIODS } from '../embed/useEmbedParams';

const WIDGET_TYPES = [
  { key: 'chart', label: 'График', icon: BarChart3, desc: 'Интерактивный AreaChart с данными и прогнозом' },
  { key: 'card', label: 'Карточка', icon: CreditCard, desc: 'Компактная карточка: значение + sparkline' },
  { key: 'table', label: 'Таблица', icon: Table2, desc: 'Последние N значений индикатора' },
  { key: 'ticker', label: 'Тикер', icon: ScrollText, desc: 'Бегущая строка для шапки сайта' },
  { key: 'compare', label: 'Сравнение', icon: GitCompare, desc: 'Два индикатора на одном графике' },
];

const SIZE_PRESETS = [
  { label: 'Малый', w: 360, h: 240 },
  { label: 'Средний', w: 600, h: 400 },
  { label: 'Большой', w: 800, h: 500 },
];

const EMBED_ORIGIN = 'https://forecasteconomy.com';

function IndicatorCombobox({ indicators, value, onChange, dark = false }) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const ref = useRef(null);

  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const grouped = useMemo(() => {
    const q = search.toLowerCase();
    const filtered = indicators?.filter(i =>
      !HIDDEN_FROM_LISTING.has(i.code) &&
      (i.name.toLowerCase().includes(q) || i.code.includes(q) || (i.name_en || '').toLowerCase().includes(q))
    ) || [];
    return CATEGORIES
      .map(cat => ({ ...cat, items: filtered.filter(i => i.category === cat.apiCategory) }))
      .filter(g => g.items.length > 0);
  }, [indicators, search]);

  const selected = indicators?.find(i => i.code === value);

  return (
    <div ref={ref} className="relative">
      <button type="button" onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between gap-2 px-3 py-2.5 rounded-xl border border-border-subtle bg-surface text-sm text-text-primary hover:border-champagne/40 transition-colors text-left">
        <span className="truncate">{selected?.name || 'Выберите индикатор…'}</span>
        <ChevronDown className={cn('w-4 h-4 text-text-tertiary transition-transform', open && 'rotate-180')} />
      </button>
      {open && (
        <div className="absolute z-50 left-0 right-0 mt-1 bg-surface border border-border-subtle rounded-xl shadow-2xl overflow-hidden" style={{ maxHeight: 340 }}>
          <div className="p-2 border-b border-border-subtle">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-tertiary" />
              <input type="text" value={search} onChange={e => setSearch(e.target.value)}
                placeholder="Поиск…" autoFocus
                className="w-full pl-8 pr-3 py-2 bg-obsidian-lighter rounded-lg text-sm text-text-primary placeholder:text-text-tertiary border-none outline-none focus:ring-1 focus:ring-champagne/30" />
            </div>
          </div>
          <div className="overflow-y-auto" style={{ maxHeight: 280 }}>
            {grouped.map(cat => (
              <div key={cat.slug}>
                <div className="px-3 py-1.5 text-[10px] uppercase tracking-widest text-text-tertiary font-medium bg-obsidian/50 sticky top-0">
                  {cat.name}
                </div>
                {cat.items.map(ind => (
                  <button key={ind.code} type="button"
                    onClick={() => { onChange(ind.code); setOpen(false); setSearch(''); }}
                    className={cn(
                      'w-full text-left px-3 py-2 text-sm hover:bg-champagne/5 transition-colors flex items-center justify-between',
                      ind.code === value && 'bg-champagne/10 text-champagne'
                    )}>
                    <span className="truncate">{ind.name}</span>
                    {ind.code === value && <Check className="w-3.5 h-3.5 text-champagne flex-shrink-0" />}
                  </button>
                ))}
              </div>
            ))}
            {grouped.length === 0 && (
              <div className="px-3 py-6 text-center text-sm text-text-tertiary">Ничего не найдено</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [text]);

  return (
    <button type="button" onClick={handleCopy}
      className={cn(
        'inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all',
        copied
          ? 'bg-positive/10 text-positive'
          : 'bg-champagne/10 text-champagne hover:bg-champagne/20'
      )}>
      {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
      {copied ? 'Скопировано' : 'Копировать код'}
    </button>
  );
}

export default function EmbedBuilder() {
  useDocumentMeta({
    title: 'Конструктор виджетов — встраиваемые графики',
    description: 'Создайте виджет с экономическими данными России и встройте его на ваш сайт. Бесплатно.',
    path: '/widgets',
  });

  const { data: indicators } = useIndicators();

  const [type, setType] = useState('chart');
  const [code, setCode] = useState('cpi');
  const [codeB, setCodeB] = useState('key-rate');
  const [period, setPeriod] = useState('1y');
  const [theme, setTheme] = useState('light');
  const [sizePreset, setSizePreset] = useState(1);
  const [customW, setCustomW] = useState(600);
  const [customH, setCustomH] = useState(400);
  const [showTitle, setShowTitle] = useState(true);
  const [showForecast, setShowForecast] = useState(false);
  const [limit, setLimit] = useState(12);
  const [tickerCodes, setTickerCodes] = useState('usd-rub,key-rate,cpi');
  const [speed, setSpeed] = useState('normal');
  const [codeTab, setCodeTab] = useState('iframe');

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
  }, [type, code, codeB, period, theme, w, h, showTitle, showForecast, limit, tickerCodes, speed]);

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
        title = `${name} — Forecast Economy`;
        break;
      case 'card':
        src = `${EMBED_ORIGIN}/embed/card/${code}?${prodParams}`;
        iframeW = 320; iframeH = 200;
        title = `${name} — Forecast Economy`;
        break;
      case 'table':
        prodParams.set('limit', limit.toString());
        src = `${EMBED_ORIGIN}/embed/table/${code}?${prodParams}`;
        iframeW = w; iframeH = Math.max(200, limit * 40 + 80);
        title = `${name} — таблица`;
        break;
      case 'ticker':
        prodParams.set('codes', tickerCodes);
        prodParams.set('speed', speed);
        src = `${EMBED_ORIGIN}/embed/ticker?${prodParams}`;
        iframeW = '100%'; iframeH = 40;
        title = 'Экономические индикаторы — Forecast Economy';
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
      return `<!-- ${title} -->\n<iframe src="${src}"\n  ${widthAttr} height="${iframeH}" frameborder="0"\n  style="border: none; border-radius: 12px; overflow: hidden;"\n  title="${title}" loading="lazy"\n  allow="clipboard-write"></iframe>`;
    }
    if (codeTab === 'markdown') {
      if (type === 'chart' || type === 'compare') return `[![${title}](${EMBED_ORIGIN}/api/v1/embed/spark/${code}.svg?period=${period}&w=600&h=100)](${EMBED_ORIGIN}/indicator/${code})`;
      return `[![${title}](${EMBED_ORIGIN}/api/v1/embed/card/${code}.svg?theme=${theme})](${EMBED_ORIGIN}/indicator/${code})`;
    }
    if (codeTab === 'svg') {
      if (type === 'card') return `<a href="${EMBED_ORIGIN}/indicator/${code}" target="_blank">\n  <img src="${EMBED_ORIGIN}/api/v1/embed/card/${code}.svg?theme=${theme}&w=${w}&h=${h}"\n    alt="${name}" width="${w}" height="${h}">\n</a>`;
      return `<a href="${EMBED_ORIGIN}/indicator/${code}" target="_blank">\n  <img src="${EMBED_ORIGIN}/api/v1/embed/spark/${code}.svg?period=${period}&w=${w}&h=60"\n    alt="${name}" width="${w}" height="60">\n</a>`;
    }
    return '';
  }, [type, code, codeB, period, theme, w, h, showTitle, showForecast, limit, tickerCodes, speed, codeTab, indicators]);

  const needsSecondIndicator = type === 'compare';
  const needsPeriod = type === 'chart' || type === 'compare';
  const needsSize = type === 'chart' || type === 'table' || type === 'compare';
  const needsLimit = type === 'table';
  const needsTicker = type === 'ticker';
  const needsForecast = type === 'chart';
  const needsIndicator = type !== 'ticker';
  const previewH = type === 'ticker' ? 40 : type === 'card' ? 200 : h;

  return (
    <div className="max-w-7xl mx-auto px-4 pt-24 md:pt-28 pb-16">
      <div className="text-center mb-10">
        <h1 className="text-3xl md:text-4xl font-display font-bold text-text-primary mb-3">
          Конструктор виджетов
        </h1>
        <p className="text-text-secondary max-w-xl mx-auto">
          Встройте графики экономических данных России на&nbsp;ваш сайт. Бесплатно, с&nbsp;обязательной ссылкой на&nbsp;источник.
        </p>
      </div>

      {/* Widget type tabs */}
      <div className="flex gap-2 justify-center mb-8 flex-wrap">
        {WIDGET_TYPES.map(wt => (
          <button key={wt.key} type="button" onClick={() => setType(wt.key)}
            className={cn(
              'flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all border',
              type === wt.key
                ? 'bg-champagne/10 border-champagne/30 text-champagne'
                : 'bg-surface border-border-subtle text-text-secondary hover:border-champagne/20 hover:text-text-primary'
            )}>
            <wt.icon className="w-4 h-4" />
            {wt.label}
          </button>
        ))}
      </div>

      <div className="grid lg:grid-cols-[340px_1fr] gap-6">
        {/* Settings panel */}
        <div className="space-y-5">
          <div className="p-5 rounded-2xl bg-surface border border-border-subtle space-y-4">
            <h2 className="text-xs uppercase tracking-widest text-text-tertiary font-medium">Настройки</h2>

            {/* Indicator selector */}
            {needsIndicator && (
              <div>
                <label className="block text-xs text-text-secondary mb-1.5 font-medium">Индикатор</label>
                <IndicatorCombobox indicators={indicators} value={code} onChange={setCode} />
              </div>
            )}

            {/* Second indicator for compare */}
            {needsSecondIndicator && (
              <div>
                <label className="block text-xs text-text-secondary mb-1.5 font-medium">Второй индикатор</label>
                <IndicatorCombobox indicators={indicators} value={codeB} onChange={setCodeB} />
              </div>
            )}

            {/* Ticker codes */}
            {needsTicker && (
              <div>
                <label className="block text-xs text-text-secondary mb-1.5 font-medium">Коды индикаторов (через запятую)</label>
                <input type="text" value={tickerCodes} onChange={e => setTickerCodes(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-border-subtle bg-obsidian-lighter text-sm text-text-primary font-mono focus:ring-1 focus:ring-champagne/30 outline-none" />
                <div className="flex gap-2 mt-2 flex-wrap">
                  {['slow', 'normal', 'fast'].map(s => (
                    <button key={s} type="button" onClick={() => setSpeed(s)}
                      className={cn('px-3 py-1 rounded-lg text-xs font-medium transition-all', speed === s ? 'bg-champagne/10 text-champagne' : 'text-text-tertiary hover:text-text-secondary')}>
                      {s === 'slow' ? 'Медленно' : s === 'normal' ? 'Обычно' : 'Быстро'}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Period */}
            {needsPeriod && (
              <div>
                <label className="block text-xs text-text-secondary mb-1.5 font-medium">Период</label>
                <div className="flex gap-1 flex-wrap">
                  {PERIODS.map(p => (
                    <button key={p.key} type="button" onClick={() => setPeriod(p.key)}
                      className={cn('px-3 py-1.5 rounded-lg text-xs font-medium transition-all', period === p.key ? 'bg-champagne/10 text-champagne' : 'text-text-tertiary hover:text-text-secondary')}>
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Theme */}
            <div>
              <label className="block text-xs text-text-secondary mb-1.5 font-medium">Тема</label>
              <div className="flex gap-2">
                {[['light', 'Светлая'], ['dark', 'Тёмная']].map(([k, l]) => (
                  <button key={k} type="button" onClick={() => setTheme(k)}
                    className={cn('flex-1 py-2 rounded-xl text-xs font-medium transition-all border', theme === k ? 'bg-champagne/10 border-champagne/30 text-champagne' : 'border-border-subtle text-text-tertiary hover:text-text-secondary')}>
                    {l}
                  </button>
                ))}
              </div>
            </div>

            {/* Size */}
            {needsSize && (
              <div>
                <label className="block text-xs text-text-secondary mb-1.5 font-medium">Размер</label>
                <div className="flex gap-1 flex-wrap mb-2">
                  {SIZE_PRESETS.map((sp, i) => (
                    <button key={i} type="button" onClick={() => setSizePreset(i)}
                      className={cn('px-3 py-1.5 rounded-lg text-xs font-medium transition-all', sizePreset === i ? 'bg-champagne/10 text-champagne' : 'text-text-tertiary hover:text-text-secondary')}>
                      {sp.label}
                    </button>
                  ))}
                  <button type="button" onClick={() => { setSizePreset(-1); setCustomW(w); setCustomH(h); }}
                    className={cn('px-3 py-1.5 rounded-lg text-xs font-medium transition-all', isCustom ? 'bg-champagne/10 text-champagne' : 'text-text-tertiary hover:text-text-secondary')}>
                    Свой
                  </button>
                </div>
                {isCustom && (
                  <div className="flex items-center gap-2">
                    <input type="number" value={customW} onChange={e => setCustomW(Math.max(200, +e.target.value))} min={200} max={1200}
                      className="w-20 px-2 py-1 rounded-lg border border-border-subtle bg-obsidian-lighter text-sm text-text-primary font-mono text-center outline-none focus:ring-1 focus:ring-champagne/30" />
                    <span className="text-text-tertiary text-xs">×</span>
                    <input type="number" value={customH} onChange={e => setCustomH(Math.max(100, +e.target.value))} min={100} max={800}
                      className="w-20 px-2 py-1 rounded-lg border border-border-subtle bg-obsidian-lighter text-sm text-text-primary font-mono text-center outline-none focus:ring-1 focus:ring-champagne/30" />
                    <span className="text-text-tertiary text-xs">px</span>
                  </div>
                )}
              </div>
            )}

            {/* Table limit */}
            {needsLimit && (
              <div>
                <label className="block text-xs text-text-secondary mb-1.5 font-medium">Количество строк</label>
                <input type="number" value={limit} onChange={e => setLimit(Math.max(1, Math.min(50, +e.target.value)))} min={1} max={50}
                  className="w-20 px-2 py-1 rounded-lg border border-border-subtle bg-obsidian-lighter text-sm text-text-primary font-mono text-center outline-none focus:ring-1 focus:ring-champagne/30" />
              </div>
            )}

            {/* Toggles */}
            <div className="space-y-2 pt-2 border-t border-border-subtle">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={showTitle} onChange={e => setShowTitle(e.target.checked)}
                  className="w-4 h-4 rounded border-border-subtle text-champagne focus:ring-champagne/30" />
                <span className="text-xs text-text-secondary">Показать заголовок</span>
              </label>
              {needsForecast && (
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={showForecast} onChange={e => setShowForecast(e.target.checked)}
                    className="w-4 h-4 rounded border-border-subtle text-champagne focus:ring-champagne/30" />
                  <span className="text-xs text-text-secondary">Показать прогноз</span>
                </label>
              )}
            </div>
          </div>

          {/* Terms */}
          <div className="p-4 rounded-xl bg-obsidian-lighter border border-border-subtle">
            <p className="text-[10px] uppercase tracking-widest text-text-tertiary font-medium mb-1">Условия</p>
            <p className="text-xs text-text-secondary leading-relaxed">
              Виджеты бесплатны для любого использования с&nbsp;сохранением ссылки «Данные: Forecast Economy» на&nbsp;источник. Подробнее&nbsp;— <a href="/about" className="text-champagne hover:underline">О&nbsp;проекте</a>.
            </p>
          </div>
        </div>

        {/* Preview + Code panel */}
        <div className="space-y-5">
          {/* Preview */}
          <div className="rounded-2xl bg-surface border border-border-subtle overflow-hidden">
            <div className="flex items-center gap-2 px-4 py-2.5 border-b border-border-subtle bg-obsidian/30">
              <div className="flex gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full bg-red-400/60" />
                <div className="w-2.5 h-2.5 rounded-full bg-yellow-400/60" />
                <div className="w-2.5 h-2.5 rounded-full bg-green-400/60" />
              </div>
              <span className="text-[10px] font-mono text-text-tertiary truncate ml-2">
                {previewUrl.replace(window.location.origin, EMBED_ORIGIN)}
              </span>
            </div>
            <div className="p-4 flex justify-center" style={{ background: theme === 'dark' ? '#111' : '#f5f5f5' }}>
              <iframe
                key={previewUrl}
                src={previewUrl}
                width={type === 'ticker' ? '100%' : Math.min(w, 760)}
                height={previewH}
                frameBorder="0"
                style={{ border: 'none', borderRadius: 12, overflow: 'hidden', maxWidth: '100%' }}
                title="Preview"
                loading="lazy"
              />
            </div>
          </div>

          {/* Code output */}
          <div className="rounded-2xl bg-surface border border-border-subtle overflow-hidden">
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-border-subtle">
              <div className="flex gap-1">
                {[
                  { key: 'iframe', label: 'iframe', icon: Code2 },
                  { key: 'svg', label: 'SVG / IMG', icon: Image },
                  { key: 'markdown', label: 'Markdown', icon: Code2 },
                ].map(tab => (
                  <button key={tab.key} type="button" onClick={() => setCodeTab(tab.key)}
                    className={cn('flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all', codeTab === tab.key ? 'bg-champagne/10 text-champagne' : 'text-text-tertiary hover:text-text-secondary')}>
                    <tab.icon className="w-3 h-3" />
                    {tab.label}
                  </button>
                ))}
              </div>
              <CopyButton text={embedCode} />
            </div>
            <pre className="p-4 text-xs font-mono text-text-secondary leading-relaxed overflow-x-auto bg-ivory/[0.02] whitespace-pre-wrap break-all">
              {embedCode}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}
