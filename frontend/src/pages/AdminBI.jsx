// Админ-BI /admin/bi (директива владельца 2026-07-05, ревизия «уровень MBA» той же ночью):
// профессиональная многоуровневая визуализация для стратегических решений.
// Принцип: у каждого потока информации СВОЯ геометрия — donut для структуры,
// воронка для конверсионного пути, heatmap 7×24 для ритма недели, treemap для
// состава контента, матрица origin×destination для навигации, Pareto для
// концентрации трафика, scatter-квадранты для двухфакторных решений. Везде
// точные числа (hover + подписи), человеческие названия, содержательный вывод.
// Свежесть: Метрика Logs API отдаёт визиты с задержкой до суток, поэтому
// свежие дни закрывает live-слой собственного счётчика behavior.js.
// Доступ: backend отвечает 404 всем, кроме settings.admin_emails.
import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  ResponsiveContainer, ComposedChart, Line, Area, Bar, BarChart, XAxis, YAxis,
  Tooltip, CartesianGrid, Legend, PieChart, Pie, Cell, LabelList,
  ScatterChart, Scatter, ZAxis, ReferenceLine, Treemap,
} from 'recharts';
import {
  Activity, Users, MousePointerClick, Search, TrendingUp, Route,
  AlertTriangle, Brain, Database, Megaphone, RefreshCw, Filter, LogIn,
  CalendarClock, LayoutGrid, Target, Wrench, ShieldCheck, Globe2,
  SlidersHorizontal, Layers, Info,
} from 'lucide-react';
import EChart from '../components/EChart';
import api, { loginUser } from '../lib/api';
import { useAuth } from '../context/authContext';
import useDocumentMeta from '../lib/useMeta';
import {
  channelLabel, deviceLabel, engineLabel,
  languageLabel, timezoneLabel, cityLabel, geoRegionLabel, blockLabel, pageSectionRu,
  sliceMetricLabel, sliceDimLabel, collapsePhrases,
} from '../lib/biLabels';

const GOLD = '#B8942F';
const INK = '#1A1A2E';
const GREEN = '#16A34A';
const RED = '#DC2626';
const BLUE = '#2563EB';
const PURPLE = '#7C3AED';
const PALETTE = [GOLD, BLUE, GREEN, PURPLE, '#0891B2', '#DB2777', '#EA580C', '#65A30D', INK, '#9333EA', '#0D9488', '#C026D3'];

// Пресеты периода — МСК-сутки (BI 2.1): «Сегодня» = 00:00 МСК → сейчас.
const PERIODS = [
  { id: 'today', label: 'Сегодня' },
  { id: 'yesterday', label: 'Вчера' },
  { id: '7d', label: '7 дней' },
  { id: '30d', label: '30 дней' },
  { id: '90d', label: '90 дней' },
  { id: 'custom', label: 'Период…' },
];


// Человеческие названия бизнес-событий (полный техноним показываем рядом).
const EVENT_RU = {
  register_nudge_view: 'Показ приглашения к регистрации',
  register_nudge_expand: 'Раскрытие приглашения',
  register_nudge_cta: 'Клик «Зарегистрироваться» в приглашении',
  scroll_depth: 'Глубина прокрутки страницы',
  compare_change: 'Смена ряда в сравнении',
  compare_open: 'Открытие сравнения',
  compare_add: 'Добавление ряда в сравнение',
  compare_range: 'Смена периода сравнения',
  compare_search: 'Поиск в сравнении',
  compare_image_download: 'Скачивание картинки сравнения',
  compare_limit_hit: 'Достигнут лимит рядов сравнения',
  regions_map_metric: 'Смена показателя на карте',
  regions_map_select: 'Клик по региону на карте',
  regions_map_timeline: 'Перемотка лет на карте',
  regions_view_toggle: 'Переключение списка и карты регионов',
  region_indicator_view: 'Просмотр показателя региона',
  region_compare_add: 'Регион добавлен в сравнение',
  region_crosslink_click: 'Переход по мосту макро–регионы',
  indicator_view: 'Просмотр карточки индикатора',
  frequency_switch: 'Переключение частоты ряда',
  chart_mode_change: 'Смена режима графика',
  chart_range_change: 'Смена периода графика',
  chart_zoom: 'Масштабирование графика',
  chart_image_download: 'Скачивание картинки графика',
  forecast_toggle: 'Включение прогноза',
  forecast_view: 'Просмотр прогноза',
  calc_mortgage: 'Расчёт ипотеки',
  calc_compound: 'Расчёт сложного процента',
  calc_preset: 'Пресет калькулятора',
  calc_share: 'Шеринг расчёта',
  calc_breakdown: 'Детализация расчёта',
  calc_chart_mode: 'Режим графика калькулятора',
  calc_copy_result: 'Копирование результата расчёта',
  home_category_click: 'Клик по категории на главной',
  home_indicator_click: 'Клик по индикатору на главной',
  category_tile_click: 'Клик по плитке категории',
  related_indicator_click: 'Клик по связанному индикатору',
  breadcrumb_click: 'Клик по хлебным крошкам',
  nav_category_open: 'Открытие меню категорий',
  nav_link_click: 'Клик по ссылке меню',
  nav_mobile_toggle: 'Мобильное меню',
  search_query: 'Поиск на сайте',
  search_select: 'Выбор результата поиска',
  search_abandon: 'Поиск брошен без выбора',
  download_csv: 'Скачивание CSV',
  download_excel: 'Скачивание Excel',
  download_ical: 'Подписка на календарь',
  download_limit: 'Достигнут лимит скачиваний',
  signup: 'Регистрация',
  login_success: 'Вход в аккаунт',
  oauth_start: 'Вход через соцсеть',
  newsletter_opt_in: 'Подписка на рассылку',
  newsletter_opt_out: 'Отписка от рассылки',
  header_login_click: 'Клик «Войти» в шапке',
  header_register_click: 'Клик «Регистрация» в шапке',
  feedback_nudge_view: 'Показ виджета обратной связи',
  feedback_nudge_expand: 'Раскрытие виджета обратной связи',
  feedback_nudge_cta: 'Клик в виджете обратной связи',
  feedback_submit: 'Отправка обратной связи',
  faq_toggle: 'Раскрытие вопроса FAQ',
  consent_update: 'Настройка cookie',
  methodology_click: 'Переход к методологии',
  source_link_click: 'Клик по источнику данных',
  outbound_link: 'Переход на внешний сайт',
  contact_email: 'Клик по адресу почты',
  calendar_month_nav: 'Листание календаря',
  calendar_source_filter: 'Фильтр календаря по источнику',
  calendar_day_select: 'Выбор дня в календаре',
  calendar_clear_day: 'Сброс дня в календаре',
  table_search: 'Поиск по таблице данных',
  table_sort: 'Сортировка таблицы',
  table_page: 'Листание таблицы',
  embed_runtime_view: 'Показ встроенного виджета',
  embed_code_copy: 'Копирование кода виджета',
  api_load_error: 'Ошибка загрузки данных',
  api_retry: 'Повторная попытка загрузки',
  error_reload: 'Перезагрузка после ошибки',
  empty_state: 'Показ пустого состояния',
  demographics_chart_type: 'Тип графика демографии',
  demographics_csv: 'CSV демографии',
};
const eventLabel = (name) => EVENT_RU[name] || name;

const DOW_RU = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

const fmtInt = (n) => (n == null ? '—' : Number(n).toLocaleString('ru-RU'));
const fmtPct = (n) => (n == null ? '—' : `${Number(n).toLocaleString('ru-RU')}%`);
const clip = (s, n = 30) => (s && s.length > n ? `${s.slice(0, n - 1)}…` : s || '');

function fetchDashboard(period, from, to) {
  const qs = new URLSearchParams({ period });
  if (period === 'custom' && from) {
    qs.set('from', from);
    if (to) qs.set('to', to);
  }
  return api.get(`/admin/bi/dashboard?${qs}`).then((r) => r.data);
}

/* ---------- Общие примитивы ---------- */

const TT_STYLE = {
  contentStyle: {
    background: '#fff', border: '1px solid rgba(26,26,46,0.12)', borderRadius: 12,
    fontSize: 12, boxShadow: '0 8px 24px rgba(0,0,0,0.10)', padding: '8px 12px',
  },
  labelStyle: { color: 'rgba(26,26,46,0.6)', fontWeight: 600, marginBottom: 2 },
  itemStyle: { color: '#1A1A2E' },
};

// Badge источника данных на карточке: «Метрика» / «наш счётчик» / «оба» —
// каждая цифра BI подписана, откуда она (сверяемость слоёв).
const SOURCE_BADGE = {
  metrika: { label: 'Метрика', cls: 'bg-blue-50 text-blue-700' },
  own: { label: 'наш счётчик', cls: 'bg-purple-50 text-purple-700' },
  both: { label: 'оба слоя', cls: 'bg-amber-50 text-amber-700' },
};

// Переключатель «сравнить с Метрикой» (этап 2в BI 2.1): per-card состояние
// в localStorage; есть только на карточках, где парные данные реально
// существуют (трафик, устройства, гео, источники, поисковики, конверсия).
function useMetrikaCompare(cardId) {
  const key = `bi:cmp:${cardId}`;
  const [on, setOn] = useState(() => {
    try { return localStorage.getItem(key) === '1'; } catch { return false; }
  });
  const toggle = () => setOn((v) => {
    try { localStorage.setItem(key, v ? '0' : '1'); } catch { /* приватный режим */ }
    return !v;
  });
  return [on, toggle];
}

// Тултип методики (этап 4а BI 2.1): ⓘ у драйверов и сложных карточек —
// hover/фокус раскрывает «как считается» (базы расчёта, пороги, слой данных).
function MethodHint({ text }) {
  return (
    <span className="group/hint relative inline-flex shrink-0 align-middle">
      {/* span, не button: подсказка встречается внутри кликабельных шапок
          (DriverNode) — вложенный button невалиден */}
      <span tabIndex={0} role="note" aria-label="Как считается"
        onClick={(e) => e.stopPropagation()}
        className="cursor-help text-text-tertiary hover:text-champagne focus:outline-none">
        <Info size={13} />
      </span>
      <span className="pointer-events-none absolute bottom-full left-1/2 z-30 mb-1.5 hidden w-64 -translate-x-1/2 rounded-xl border border-border-subtle bg-surface p-3 text-left text-[11.5px] font-normal leading-snug text-text-secondary shadow-xl group-hover/hint:block group-focus-within/hint:block">
        {text}
      </span>
    </span>
  );
}

function Card({ title, icon: Icon, insight, children, span, source, window: windowMeta, compare, hint }) {
  const badge = SOURCE_BADGE[source];
  // windowMeta — period.to_meta() витрины: подпись окна, если оно отличается
  // от глобального периода дашборда (например, «Надёжность» = хвост 7 дней).
  const windowLabel = windowMeta?.label
    ? (windowMeta.from === windowMeta.to ? windowMeta.label : `${windowMeta.label} · МСК`)
    : null;
  return (
    <section className={`rounded-2xl bg-surface border border-border-subtle p-5 ${span || ''}`}>
      <h2 className="flex items-center gap-2 text-[15px] font-semibold text-text-primary">
        {Icon && <Icon size={16} className="text-champagne" />}
        <span className="min-w-0 flex-1">
          {title}
          {hint && <span className="ml-1.5 inline-flex align-middle"><MethodHint text={hint} /></span>}
        </span>
        {compare && (
          <button
            type="button" onClick={compare.toggle}
            className={`shrink-0 text-[10px] px-2 py-0.5 rounded-full border transition-colors ${
              compare.on
                ? 'bg-blue-600 text-white border-blue-600'
                : 'bg-transparent text-text-tertiary border-border-subtle hover:text-blue-700 hover:border-blue-300'
            }`}
            title="Наложить данные Яндекс.Метрики для сверки">
            ⇄ Метрика
          </button>
        )}
        {windowLabel && (
          <span className="shrink-0 text-[10px] px-2 py-0.5 rounded-full bg-border-subtle/40 text-text-tertiary font-normal"
            title={`Окно данных: ${windowMeta.from} — ${windowMeta.to} (МСК)`}>
            {windowLabel}
          </span>
        )}
        {badge && (
          <span className={`shrink-0 text-[10px] px-2 py-0.5 rounded-full font-medium ${badge.cls}`}>
            {badge.label}
          </span>
        )}
      </h2>
      {insight && <p className="text-[12.5px] text-text-secondary mt-1 mb-3 leading-snug">{insight}</p>}
      {!insight && <div className="mb-4" />}
      {children}
    </section>
  );
}

// Парный блок сверки: приглушённый повтор диаграммы по данным Метрики.
function MetrikaOverlay({ children }) {
  return (
    <div className="mt-3 pt-3 border-t border-dashed border-blue-200">
      <div className="text-[11px] text-blue-700 mb-2">По Яндекс.Метрике (сверка)</div>
      {children}
    </div>
  );
}

function Empty({ note }) {
  return <p className="text-[13px] text-text-tertiary py-8 text-center">{note || 'Нет данных за период'}</p>;
}

function Kpi({ label, value, sub, series, color = GOLD }) {
  return (
    <div className="rounded-xl bg-surface border border-border-subtle px-4 py-3 relative overflow-hidden">
      <div className="text-[12px] text-text-tertiary">{label}</div>
      <div className="text-xl font-bold text-text-primary tabular-nums">{value}</div>
      {sub && <div className="text-[11px] text-text-tertiary mt-0.5">{sub}</div>}
      {series && series.length > 1 && (
        <div className="absolute inset-x-0 bottom-0 h-8 opacity-40">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={series} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
              <Area type="monotone" dataKey="v" stroke={color} fill={color} fillOpacity={0.18} strokeWidth={1.4} dot={false} isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

// Донат: структура (доли) с центральной суммой и легендой с точными числами.
function Donut({ data, height = 240, centerLabel }) {
  const rows = (data || []).filter((d) => d.value > 0);
  if (!rows.length) return <Empty />;
  const total = rows.reduce((s, d) => s + d.value, 0);
  return (
    <div className="grid grid-cols-[1fr] sm:grid-cols-[minmax(0,180px)_1fr] gap-4 items-center">
      <div className="relative" style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={rows} dataKey="value" nameKey="name" innerRadius="62%" outerRadius="92%" paddingAngle={1.5} stroke="none">
              {rows.map((d, i) => <Cell key={d.name} fill={d.color || PALETTE[i % PALETTE.length]} />)}
            </Pie>
            <Tooltip {...TT_STYLE} formatter={(v, n) => [`${fmtInt(v)} · ${Math.round(v / total * 100)}%`, n]} />
          </PieChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <div className="text-lg font-bold text-text-primary tabular-nums leading-none">{fmtInt(total)}</div>
          <div className="text-[10px] text-text-tertiary mt-0.5">{centerLabel || 'всего'}</div>
        </div>
      </div>
      <ul className="space-y-1.5 min-w-0">
        {rows.map((d, i) => (
          <li key={d.name} className="flex items-center gap-2 text-[12.5px]">
            <span className="w-2.5 h-2.5 rounded-sm shrink-0" style={{ background: d.color || PALETTE[i % PALETTE.length] }} />
            <span className="flex-1 min-w-0 truncate text-text-primary" title={d.name}>{d.name}</span>
            <span className="text-text-secondary tabular-nums shrink-0">{fmtInt(d.value)}</span>
            <span className="w-10 text-right text-text-tertiary tabular-nums shrink-0">{Math.round(d.value / total * 100)}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// Горизонтальные бары-рейтинг с числами у каждого бара.
function HBars({ data, height, color = GOLD, unit = '', valueFmt = fmtInt, labelWidth = 148 }) {
  const rows = (data || []).filter((d) => d.value != null);
  if (!rows.length) return <Empty />;
  const h = height || Math.max(120, rows.length * 30 + 16);
  return (
    <ResponsiveContainer width="100%" height={h}>
      <BarChart layout="vertical" data={rows} margin={{ top: 2, right: 48, bottom: 2, left: 4 }}>
        <XAxis type="number" hide />
        <YAxis
          type="category" dataKey="name" width={labelWidth}
          tick={{ fontSize: 11.5, fill: 'rgba(26,26,46,0.72)' }}
          tickFormatter={(v) => clip(v, Math.floor(labelWidth / 6.6))} interval={0}
        />
        <Tooltip {...TT_STYLE} cursor={{ fill: 'rgba(184,148,47,0.06)' }} formatter={(v) => [`${valueFmt(v)}${unit}`, 'значение']} />
        <Bar dataKey="value" fill={color} radius={[0, 4, 4, 0]} maxBarSize={22}>
          <LabelList dataKey="value" position="right" formatter={(v) => `${valueFmt(v)}${unit}`} style={{ fontSize: 11, fill: 'rgba(26,26,46,0.65)' }} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// Клиентская пагинация длинных списков (волна 2, п. 3): сервер отдаёт
// увеличенные лимиты, владелец долистывает до конца любой таблицы.
function usePager(rows, pageSize = 25) {
  const [page, setPage] = useState(0);
  const total = rows?.length || 0;
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const cur = Math.min(page, pages - 1);
  return {
    slice: (rows || []).slice(cur * pageSize, (cur + 1) * pageSize),
    cur, pages, total, pageSize, setPage,
  };
}

function Pager({ p }) {
  if (p.pages <= 1) return null;
  const from = p.cur * p.pageSize + 1;
  const to = Math.min((p.cur + 1) * p.pageSize, p.total);
  return (
    <div className="flex items-center justify-between gap-3 mt-3 text-[12px] text-text-secondary">
      <span className="tabular-nums">{fmtInt(from)}–{fmtInt(to)} из {fmtInt(p.total)}</span>
      <div className="flex items-center gap-1">
        <button type="button" disabled={p.cur === 0} onClick={() => p.setPage(p.cur - 1)}
          className="px-2.5 py-1 rounded-lg border border-border-subtle disabled:opacity-35 hover:text-text-primary">
          ← Назад
        </button>
        <span className="px-2 tabular-nums">{p.cur + 1} / {p.pages}</span>
        <button type="button" disabled={p.cur >= p.pages - 1} onClick={() => p.setPage(p.cur + 1)}
          className="px-2.5 py-1 rounded-lg border border-border-subtle disabled:opacity-35 hover:text-text-primary">
          Вперёд →
        </button>
      </div>
    </div>
  );
}

// Таблица фраз с числом (этап 4б BI 2.1): бары с count=1 на всю ширину
// обманывали глаз — для редких фраз честнее ранжированная таблица.
// Волна 2, п. 3: листается целиком, а не топ-12.
function PhraseTable({ rows, valueLabel = 'раз', pageSize = 12 }) {
  const pager = usePager(rows || [], pageSize);
  if (!rows?.length) return <Empty />;
  const max = rows[0]?.count || 1;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[12.5px]">
        <tbody>
          {pager.slice.map((r) => (
            <tr key={r.phrase} className="border-b border-border-subtle/40 last:border-0">
              <td className="py-1.5 pr-3 text-text-primary">
                <span className="relative z-10">{r.phrase}</span>
                <span className="block h-0.5 mt-0.5 rounded-full bg-champagne/50" style={{ width: `${Math.max(3, Math.round(r.count / max * 100))}%` }} aria-hidden />
              </td>
              <td className="py-1.5 text-right tabular-nums text-text-secondary whitespace-nowrap align-top">
                {fmtInt(r.count)} <span className="text-text-tertiary text-[11px]">{valueLabel}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <Pager p={pager} />
    </div>
  );
}

const dictToBars = (obj, n = 12, mapName) =>
  Object.entries(obj || {}).sort((a, b) => b[1] - a[1]).slice(0, n)
    .map(([name, value]) => ({ name: mapName ? mapName(name) : name, value }));

function median(arr) {
  const a = (arr || []).filter((v) => v != null && Number.isFinite(v)).sort((x, y) => x - y);
  if (!a.length) return 0;
  const mid = Math.floor(a.length / 2);
  return a.length % 2 ? a[mid] : (a[mid - 1] + a[mid]) / 2;
}

/* ---------- Уникальные геометрии ---------- */

// Пульс недели: сетка 7 дней × 24 часа. Основной слой — визиты Метрики
// (золотой). Клетки, где Метрика пуста, а собственный счётчик видит просмотры
// (свежие часы до её выгрузки), — фиолетовые. Слои НЕ суммируются: визит и
// просмотр — разные единицы, сумма была бы двойным счётом одного посещения.
function WeekPulse({ cells }) {
  const grid = useMemo(() => {
    const m = new Map();
    let maxVisits = 0;
    let maxOwn = 0;
    for (const c of cells || []) {
      const own = c.count || 0;
      const visits = c.visits || 0;
      m.set(`${c.dow}-${c.hour}`, { own, visits });
      if (visits > maxVisits) maxVisits = visits;
      if (own > maxOwn) maxOwn = own;
    }
    return { m, maxVisits, maxOwn };
  }, [cells]);
  if (!grid.maxVisits && !grid.maxOwn) return <Empty />;

  const CELL = 30; const GAP = 3; const LEFT = 34; const TOP = 20;
  const width = LEFT + 24 * (CELL + GAP);
  const height = TOP + 7 * (CELL + GAP);
  return (
    <div className="overflow-x-auto">
      <svg width={width} height={height} className="block" role="img" aria-label="Активность по дням недели и часам">
        {Array.from({ length: 24 }, (_, h) => (
          h % 3 === 0 && (
            <text key={`h${h}`} x={LEFT + h * (CELL + GAP) + CELL / 2} y={12} textAnchor="middle" fontSize={10} fill="rgba(26,26,46,0.5)">
              {h}:00
            </text>
          )
        ))}
        {DOW_RU.map((d, dow) => (
          <text key={d} x={0} y={TOP + dow * (CELL + GAP) + CELL / 2 + 4} fontSize={11} fill="rgba(26,26,46,0.65)">{d}</text>
        ))}
        {Array.from({ length: 7 }, (_, dow) => Array.from({ length: 24 }, (_, hour) => {
          // Основной слой — НАШИ сессии (BI 2.1); клетки, куда собственный
          // счётчик ещё не дотянулся, дозаполняет Метрика (фиолетовый).
          const c = grid.m.get(`${dow}-${hour}`) || { own: 0, visits: 0 };
          const metrikaOnly = !c.own && c.visits > 0;
          const t = metrikaOnly
            ? (grid.maxVisits ? c.visits / grid.maxVisits : 0)
            : (grid.maxOwn ? c.own / grid.maxOwn : 0);
          const shown = metrikaOnly ? c.visits : c.own;
          const fill = shown
            ? (metrikaOnly ? `rgba(124,58,237,${0.12 + t * 0.6})` : `rgba(184,148,47,${0.12 + t * 0.78})`)
            : 'rgba(26,26,46,0.045)';
          return (
            <g key={`${dow}-${hour}`}>
              <rect
                x={LEFT + hour * (CELL + GAP)} y={TOP + dow * (CELL + GAP)}
                width={CELL} height={CELL} rx={4} fill={fill}
              >
                <title>{`${DOW_RU[dow]}, ${hour}:00–${hour + 1}:00 — сессии нашего счётчика: ${fmtInt(c.own)}, визиты Метрики: ${fmtInt(c.visits)}`}</title>
              </rect>
              {shown > 0 && (
                <text
                  x={LEFT + hour * (CELL + GAP) + CELL / 2} y={TOP + dow * (CELL + GAP) + CELL / 2 + 3.5}
                  textAnchor="middle" fontSize={9.5} pointerEvents="none"
                  fill={t > 0.55 ? '#fff' : 'rgba(26,26,46,0.65)'}
                >
                  {shown > 999 ? `${Math.round(shown / 100) / 10}k` : shown}
                </text>
              )}
            </g>
          );
        }))}
      </svg>
      <div className="flex items-center gap-2 mt-2 text-[11px] text-text-tertiary flex-wrap">
        <span>меньше</span>
        {[0.15, 0.35, 0.55, 0.75, 0.9].map((t) => (
          <span key={t} className="w-4 h-4 rounded" style={{ background: `rgba(184,148,47,${t})` }} />
        ))}
        <span>больше — сессии нашего счётчика</span>
        <span className="w-4 h-4 rounded ml-2" style={{ background: 'rgba(124,58,237,0.5)' }} />
        <span>только Метрика (наш слой ещё не накопился) · время московское</span>
      </div>
    </div>
  );
}

// Treemap-плитка с именем, числом и долей.
function TreemapCell({ x, y, width, height, name, views, share, index }) {
  if (width < 4 || height < 4) return null;
  const showText = width > 78 && height > 40;
  return (
    <g>
      <rect x={x} y={y} width={width} height={height} rx={6}
        fill={PALETTE[index % PALETTE.length]} fillOpacity={0.82} stroke="#fff" strokeWidth={2} />
      {showText && (
        <>
          <text x={x + 8} y={y + 18} fontSize={12} fontWeight={600} fill="#fff">{clip(name, Math.floor(width / 7.5))}</text>
          <text x={x + 8} y={y + 34} fontSize={11} fill="rgba(255,255,255,0.9)">{fmtInt(views)} · {share}%</text>
        </>
      )}
    </g>
  );
}

// Матрица переходов: строки — откуда, колонки — куда, клетка — число переходов.
function TransitionMatrix({ transitions }) {
  const { rows, cols, cell, max } = useMemo(() => {
    const fromC = new Map(); const toC = new Map(); const m = new Map();
    let mx = 0;
    for (const t of transitions || []) {
      fromC.set(t.from, (fromC.get(t.from) || 0) + t.count);
      toC.set(t.to, (toC.get(t.to) || 0) + t.count);
      m.set(`${t.from}→${t.to}`, t.count);
      if (t.count > mx) mx = t.count;
    }
    const top = (map) => [...map.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8).map(([k]) => k);
    return { rows: top(fromC), cols: top(toC), cell: m, max: mx };
  }, [transitions]);

  if (!rows.length) return <Empty />;
  return (
    <div className="overflow-x-auto">
      <table className="text-[11.5px] border-separate" style={{ borderSpacing: 3 }}>
        <thead>
          <tr>
            <th className="text-left text-text-tertiary font-medium pr-2 align-bottom pb-1">откуда \ куда</th>
            {cols.map((c) => (
              <th key={c} className="text-text-tertiary font-normal px-1 pb-1 max-w-24 align-bottom">
                <div className="truncate w-24" title={c}>{clip(c, 16)}</div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r}>
              <td className="text-text-primary pr-2 max-w-44"><div className="truncate w-44" title={r}>{clip(r, 28)}</div></td>
              {cols.map((c) => {
                const v = cell.get(`${r}→${c}`) || 0;
                const t = max ? v / max : 0;
                return (
                  <td key={c}>
                    <div
                      className="w-24 h-8 rounded flex items-center justify-center tabular-nums"
                      style={{
                        background: v ? `rgba(184,148,47,${0.1 + t * 0.75})` : 'rgba(26,26,46,0.035)',
                        color: t > 0.45 ? '#fff' : 'rgba(26,26,46,0.75)',
                      }}
                      title={`${r} → ${c}: ${fmtInt(v)} переходов`}
                    >
                      {v || '·'}
                    </div>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ---------- Вкладки ---------- */

function OverviewTab({ d }) {
  const kpi = useMemo(() => d.kpi_daily || [], [d.kpi_daily]);
  const totals = useMemo(() => {
    const t = { visits: 0, visitors: 0, ad: 0, reg: 0, dl: 0, err: 0, ev: 0, srch: 0, own: 0 };
    for (const r of kpi) {
      t.visits += r.visits; t.visitors += r.visitors; t.ad += r.ad_visits;
      t.reg += r.registrations; t.dl += r.downloads; t.err += r.errors;
      t.ev += r.events; t.srch += r.searches; t.own += r.own_sessions || 0;
    }
    return t;
  }, [kpi]);
  const spark = (key) => kpi.map((r) => ({ v: r[key] }));
  // Метрика отдаёт данные с лагом до суток: линию рисуем только когда точек
  // достаточно (иначе одна-две точки дают обманчивую диагональ).
  const metrikaPoints = kpi.filter((r) => r.visits > 0).length;
  const [cmpTraffic, toggleCmpTraffic] = useMetrikaCompare('traffic-daily');
  const showMetrikaLine = cmpTraffic && metrikaPoints >= 3;
  const [cmpSources, toggleCmpSources] = useMetrikaCompare('sources-overview');
  const srcDonut = Object.entries(d.own_acquisition?.channels || {})
    .map(([k, v]) => ({ name: channelLabel(k), value: v }));
  const metrikaSrcDonut = Object.entries(d.acquisition?.sources || {})
    .map(([k, v]) => ({ name: channelLabel(k), value: v }));

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">
        <Kpi label="Сессии (наш счётчик)" value={fmtInt(totals.own)} series={spark('own_sessions')} />
        <Kpi label="Посетители (наш счётчик)" value={fmtInt(d.metric_tree?.north_star?.visitors_total ?? 0)} series={spark('own_visitors')} color={INK} />
        <Kpi label="Визиты (Метрика)" value={fmtInt(totals.visits)} series={spark('visits')} color={PURPLE} />
        <Kpi label="Из рекламы" value={fmtInt(totals.ad)} sub={totals.visits ? fmtPct(Math.round(totals.ad / totals.visits * 100)) : null} series={spark('ad_visits')} color={BLUE} />
        <Kpi label="Регистрации" value={fmtInt(totals.reg)} sub={`всего ${fmtInt(d.users?.total)}`} series={spark('registrations')} color={GREEN} />
        <Kpi label="Скачивания" value={fmtInt(totals.dl)} series={spark('downloads')} color={PURPLE} />
        <Kpi label="Поиски на сайте" value={fmtInt(totals.srch)} series={spark('searches')} color={BLUE} />
        <Kpi label="Ошибки фронта" value={fmtInt(totals.err)} series={spark('errors')} color={RED} />
      </div>

      <Card title="Трафик по дням" icon={Activity} source="own"
        compare={{ on: cmpTraffic, toggle: toggleCmpTraffic }}
        insight="Столбцы — сессии и посетители нашего счётчика без ботов и своей активности (реальное время). Переключатель «Метрика» накладывает пунктирную линию визитов Яндекс.Метрики: она отдаёт данные с задержкой до суток и рисуется только при достаточном числе точек."
        hint="Столбцы — сессии и уникальные посетители по нашему серверному счётчику (сессионизация каждые 15 минут, правило 30 минут, боты и своя активность исключены). Пунктир — визиты Метрики за те же МСК-сутки. Читать: форма кривых должна совпадать; расхождение уровней — разные фильтры ботов.">
        <ResponsiveContainer width="100%" height={290}>
          <ComposedChart data={kpi} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
            <XAxis dataKey="date" tick={{ fontSize: 11, fill: 'rgba(26,26,46,0.5)' }} tickFormatter={(v) => v.slice(5)} />
            <YAxis tick={{ fontSize: 11, fill: 'rgba(26,26,46,0.5)' }} width={40} />
            <Tooltip {...TT_STYLE} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar dataKey="own_sessions" name="Сессии (наш счётчик)" fill={GOLD} fillOpacity={0.8} radius={[3, 3, 0, 0]} maxBarSize={26} />
            <Bar dataKey="own_visitors" name="Посетители (наш счётчик)" fill={INK} fillOpacity={0.45} radius={[3, 3, 0, 0]} maxBarSize={26} />
            {showMetrikaLine && (
              <Line type="monotone" dataKey="visits" name="Визиты (Метрика)" stroke={PURPLE} strokeWidth={1.6} dot={false} strokeDasharray="5 3" />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </Card>

      <Card title="Пульс недели: когда аудитория на сайте" icon={CalendarClock} source="own"
        hint="Матрица «день недели × час»: каждая клетка — число небот-сессий нашего счётчика, начавшихся в этот час (московское время), суммарно за выбранный период. Палитра масштабируется по максимальной клетке."
        insight="Активность по дням недели и часам (московское время): сессии нашего счётчика без ботов; слой Метрики — для сверки. Тёмные зоны — пиковые окна: под них планируются публикации, реклама и релизы.">
        <WeekPulse cells={d.activity_heatmap} />
      </Card>

      <div className="grid lg:grid-cols-3 gap-5">
        <Card title="Структура источников" icon={Megaphone} span="lg:col-span-1" source="own"
          compare={{ on: cmpSources, toggle: toggleCmpSources }}
          insight="Каналы сессий нашего счётчика за период (без ботов). Канал определяется по рекламным меткам, UTM и сайту-источнику перехода."
        hint="Каждая небот-сессия нашего счётчика получает канал: рекламные метки (yclid/UTM) → реклама или кампания, сайт перехода → поиск/соцсети/сайты, без признаков — прямой заход. Читать: доля платного трафика против бесплатного.">
          <Donut data={srcDonut} centerLabel="сессий" />
          {cmpSources && (
            <MetrikaOverlay>
              <Donut data={metrikaSrcDonut} height={170} centerLabel="визитов" />
            </MetrikaOverlay>
          )}
        </Card>
        <Card title="Конверсии и ошибки по дням" icon={TrendingUp} span="lg:col-span-2" source="own" insight="Регистрации и скачивания — целевые действия по нашему счётчику. Красная линия ошибок не должна расти вместе с трафиком."
        hint="Регистрации — новые аккаунты (таблица пользователей), скачивания — события выгрузок нашего счётчика, ошибки — JS-ошибки фронта. По дням МСК. Читать: конверсии должны расти с трафиком, ошибки — нет.">
          <ResponsiveContainer width="100%" height={240}>
            <ComposedChart data={kpi}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: 'rgba(26,26,46,0.5)' }} tickFormatter={(v) => v.slice(5)} />
              <YAxis tick={{ fontSize: 11, fill: 'rgba(26,26,46,0.5)' }} width={30} allowDecimals={false} />
              <Tooltip {...TT_STYLE} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="registrations" name="Регистрации" fill={GREEN} radius={[3, 3, 0, 0]} maxBarSize={26} />
              <Bar dataKey="downloads" name="Скачивания" fill={PURPLE} radius={[3, 3, 0, 0]} maxBarSize={26} />
              <Line type="monotone" dataKey="errors" name="Ошибки" stroke={RED} strokeWidth={1.6} dot={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </Card>
      </div>
    </div>
  );
}

function AcquisitionTab({ d }) {
  const a = d.acquisition || {};
  const own = d.own_acquisition || {};
  const aud = d.audience || {};
  const srcDonut = Object.entries(own.channels || {}).map(([k, v]) => ({ name: channelLabel(k), value: v }));
  const metrikaSrcDonut = Object.entries(a.sources || {}).map(([k, v]) => ({ name: channelLabel(k), value: v }));
  const devDonut = Object.entries(aud.devices || {}).map(([k, v]) => ({ name: deviceLabel(k), value: v }));
  const metrikaDevDonut = Object.entries(a.devices || {}).map(([k, v]) => ({ name: deviceLabel(k), value: v }));
  const ads = (a.ad_campaigns || []).filter((c) => c.visits > 0)
    .map((c) => ({ ...c, x: c.visits, y: c.goal_rate_pct, z: Math.max(c.bounce_pct, 1) }));
  // Поисковики: наш счётчик + сверка с Метрикой по переключателю.
  const metrikaEngines = a.search_engines || {};
  const engineBars = dictToBars(own.search_engines, 8);
  const ownCities = dictToBars(aud.cities, 8, cityLabel);
  const [cmpSrc, toggleCmpSrc] = useMetrikaCompare('sources-acq');
  const [cmpEng, toggleCmpEng] = useMetrikaCompare('engines-acq');
  const [cmpDev, toggleCmpDev] = useMetrikaCompare('devices-acq');
  const [cmpGeo, toggleCmpGeo] = useMetrikaCompare('geo-acq');

  return (
    <div className="grid lg:grid-cols-2 gap-5">
      <Card title="Структура источников трафика" icon={Megaphone} source="own"
        compare={{ on: cmpSrc, toggle: toggleCmpSrc }}
        insight="Каналы сессий нашего счётчика (без ботов): баланс платного и органического трафика — основа стоимости привлечения."
        hint="Каналы небот-сессий нашего счётчика за период: канал определяется по рекламным меткам первого перехода, сайту-источнику или отсутствию признаков (прямой заход). Кнопка «⇄ Метрика» накладывает те же доли по визитам Метрики для сверки.">
        <Donut data={srcDonut} centerLabel="сессий" />
        {cmpSrc && (
          <MetrikaOverlay>
            <Donut data={metrikaSrcDonut} height={170} centerLabel="визитов" />
          </MetrikaOverlay>
        )}
      </Card>
      <Card title="Поисковые системы" icon={Search} source={engineBars.length ? 'own' : 'metrika'}
        compare={{ on: cmpEng, toggle: toggleCmpEng }}
        insight="Из каких поисковиков приходит органический трафик: сессии нашего счётчика; пока собственный слой не накопился — данные Метрики."
        hint="Из какого поисковика пришла сессия — по домену перехода (yandex.*, google.* и т. д.). Источник — наш счётчик; сверка — Метрика. Читать: баланс Яндекс/Google показывает, под какую выдачу оптимизировать в первую очередь.">
        {engineBars.length
          ? <HBars data={engineBars} color={BLUE} />
          : <HBars data={dictToBars(metrikaEngines, 8, engineLabel)} color={BLUE} />}
        {cmpEng && engineBars.length > 0 && (
          <MetrikaOverlay>
            <HBars data={dictToBars(metrikaEngines, 8, engineLabel)} color={PURPLE} />
          </MetrikaOverlay>
        )}
      </Card>

      <Card title="Партнёрские сети: объём, конверсия и отказы" icon={Megaphone} span="lg:col-span-2" source="metrika"
        insight="По горизонтали — визиты, по вертикали — конверсия в цель, размер точки — доля отказов. Правый верх — эффективные кампании; крупные точки внизу справа расходуют бюджет впустую."
        hint="Только визиты Метрики с каналом «реклама», сгруппированы по UTM-метке кампании. Конверсия — доля визитов с business-целью (регистрация, скачивание). Читать: кампании внизу справа тратят бюджет без отдачи.">
        {/* Скаттер с 1–2 точками не читается: до трёх кампаний — компактный список. */}
        {ads.length > 0 && ads.length < 3 && (
          <div className="space-y-2">
            {ads.map((c) => (
              <div key={c.campaign} className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-[12.5px]">
                <span className="font-medium text-text-primary">{c.campaign}</span>
                <span className="tabular-nums text-text-secondary">{fmtInt(c.visits)} визитов</span>
                <span className="tabular-nums text-text-secondary">с целью {fmtInt(c.goal_visits)} ({c.goal_rate_pct}%)</span>
                <span className="tabular-nums text-text-tertiary">отказы {c.bounce_pct}% · среднее время {c.avg_duration_sec} с</span>
              </div>
            ))}
            <p className="text-[11.5px] text-text-tertiary pt-1">Диаграмма-скаттер включится, когда кампаний станет три и больше.</p>
          </div>
        )}
        {ads.length >= 3 ? (
          <ResponsiveContainer width="100%" height={300}>
            <ScatterChart margin={{ top: 10, right: 20, bottom: 20, left: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
              <XAxis type="number" dataKey="x" name="Визиты" tick={{ fontSize: 11, fill: 'rgba(26,26,46,0.5)' }}
                label={{ value: 'визиты', position: 'insideBottom', offset: -8, fontSize: 11, fill: 'rgba(26,26,46,0.5)' }} />
              <YAxis type="number" dataKey="y" name="Конверсия, %" unit="%" tick={{ fontSize: 11, fill: 'rgba(26,26,46,0.5)' }} width={44} />
              <ZAxis type="number" dataKey="z" range={[60, 500]} name="Отказы, %" />
              <Tooltip {...TT_STYLE} cursor={{ strokeDasharray: '3 3' }}
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const p = payload[0].payload;
                  return (
                    <div style={TT_STYLE.contentStyle}>
                      <div style={{ fontWeight: 600, marginBottom: 2 }}>{p.campaign}</div>
                      <div>Визиты: {fmtInt(p.visits)} · с целью: {fmtInt(p.goal_visits)} ({p.goal_rate_pct}%)</div>
                      <div>Отказы: {p.bounce_pct}% · среднее время: {p.avg_duration_sec} с</div>
                    </div>
                  );
                }} />
              <Scatter data={ads} fill={GOLD} fillOpacity={0.6}>
                {ads.map((c, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
                <LabelList dataKey="campaign" position="top" formatter={(v) => clip(v, 16)} style={{ fontSize: 10, fill: 'rgba(26,26,46,0.6)' }} />
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>
        ) : null}
        {ads.length === 0 && <Empty note="Платных кампаний за период нет. Расход и цена клика появятся после подключения рекламного кабинета (РСЯ / партнёрские сети)." />}
      </Card>

      <Card title="Поисковые фразы, с которых пришли" icon={Search} source="metrika" insight="Реальные запросы, приведшие посетителей из поиска. Близкие недопечатки схлопнуты в полную фразу."
        hint="Повизитные данные Метрики за завершённые дни: точная фраза запроса, приведшего визит. Близкие недопечатки схлопнуты. Читать: это реальный спрос — фразы без страницы под них — идеи контента.">
        {(a.top_phrases && Object.keys(a.top_phrases).length) ? (
          <PhraseTable rows={collapsePhrases(a.top_phrases, { limit: 200 })} valueLabel="визитов" />
        ) : <Empty note={a.today_live
          ? 'Фразы Метрика отдаёт повизитно за завершённый день — появятся завтра после утреннего синка.'
          : undefined} />}
      </Card>
      <div className="space-y-5">
        <Card title="Устройства" icon={Users} source={devDonut.length ? 'own' : 'metrika'}
          compare={{ on: cmpDev, toggle: toggleCmpDev }}
          insight="Сессии нашего счётчика по типу устройства (боты исключены)."
        hint="Тип устройства каждой небот-сессии нашего счётчика: из паспорта сессии, а при его отсутствии — по касаниям экрана и ширине окна. Сверка — Метрика по кнопке «⇄».">
          <Donut data={devDonut.length ? devDonut : metrikaDevDonut} height={180} centerLabel={devDonut.length ? 'сессий' : 'визитов'} />
          {cmpDev && devDonut.length > 0 && (
            <MetrikaOverlay>
              <Donut data={metrikaDevDonut} height={150} centerLabel="визитов" />
            </MetrikaOverlay>
          )}
        </Card>
        <Card title="География: города" icon={Users} source={ownCities.length ? 'own' : 'metrika'}
          compare={{ on: cmpGeo, toggle: toggleCmpGeo }}
          insight="Города по сессиям нашего счётчика (гео по IP без хранения адреса); ретро-история до запуска гео-слоя видна только в Метрике."
        hint="Город определяется по IP-адресу на нашем сервере в момент сессии (адрес не сохраняется, база DB-IP). Читать: концентрация в столицах — норма; всплеск в неожиданном городе — проверka на ботов.">
          <HBars data={ownCities.length ? ownCities : dictToBars(a.top_cities, 8, cityLabel)} color={PURPLE} />
          {cmpGeo && ownCities.length > 0 && (
            <MetrikaOverlay>
              <HBars data={dictToBars(a.top_cities, 8, cityLabel)} color={BLUE} />
            </MetrikaOverlay>
          )}
        </Card>
      </div>
    </div>
  );
}

function FunnelTab({ d }) {
  const f = d.funnel || {};
  const bySource = (f.by_source || []).filter((s) => s.visits > 0);

  const stack = bySource.map((s) => ({
    name: channelLabel(s.source),
    goal: s.goal_visits,
    engaged: Math.max(s.engaged - s.goal_visits, 0),
    bounced: Math.max(s.visits - s.engaged, 0),
    visits: s.visits,
    goal_pct: s.goal_pct,
    engaged_pct: s.engaged_pct,
  }));

  const landPager = usePager(f.top_landings || [], 14);
  const landings = landPager.slice;
  const maxLandingVisits = Math.max(1, ...(f.top_landings || []).map((l) => l.visits));

  return (
    <div className="space-y-5">
      {/* Легаси «Общая воронка визита» удалена (этап 2б BI 2.1):
          её заменила «Истинная конверсия» на нашем счётчике. */}
      <div className="grid lg:grid-cols-1 gap-5">
        <Card title="Качество каналов" icon={TrendingUp} source="metrika" insight="Состав каждого канала: дошли до business-цели (зелёное), вовлеклись (золотое), отсеялись (серое). Целью считаются только конверсионные действия — регистрация, подписка, скачивание; скролл и навигация не в счёт. Наведите — точные числа."
        hint="Каждая полоса — канал по визитам Метрики за период, нормирован к 100%. Зелёное — визиты с business-целью, золотое — вовлечённые без цели (2+ страницы или 30+ секунд), серое — отсев. Читать: канал с большим серым — трафик не находит ценности.">
          {stack.length ? (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart layout="vertical" data={stack} margin={{ top: 2, right: 12, bottom: 2, left: 4 }} stackOffset="expand">
                <XAxis type="number" hide domain={[0, 1]} />
                <YAxis type="category" dataKey="name" width={150} tick={{ fontSize: 11.5, fill: 'rgba(26,26,46,0.72)' }} tickFormatter={(v) => clip(v, 21)} interval={0} />
                <Tooltip {...TT_STYLE}
                  content={({ active, payload }) => {
                    if (!active || !payload?.length) return null;
                    const p = payload[0].payload;
                    return (
                      <div style={TT_STYLE.contentStyle}>
                        <div style={{ fontWeight: 600, marginBottom: 2 }}>{p.name}</div>
                        <div>Визиты: {fmtInt(p.visits)}</div>
                        <div>Вовлечены: {fmtInt(p.goal + p.engaged)} ({p.engaged_pct}%)</div>
                        <div>Достигли цели: {fmtInt(p.goal)} ({p.goal_pct}%)</div>
                      </div>
                    );
                  }} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="goal" name="Цель" stackId="s" fill={GREEN} maxBarSize={26} />
                <Bar dataKey="engaged" name="Вовлечён" stackId="s" fill={GOLD} maxBarSize={26} />
                <Bar dataKey="bounced" name="Отсеялся" stackId="s" fill="rgba(26,26,46,0.14)" maxBarSize={26} />
              </BarChart>
            </ResponsiveContainer>
          ) : <Empty note={d.metrika_live_today
            ? 'Повизитные разрезы Метрики доступны за завершённые дни — за сегодня появятся завтра после утреннего синка.'
            : undefined} />}
        </Card>
      </div>

      <Card title="Посадочные страницы: объём входа и конверсия" icon={Route} source="metrika"
        insight="Отсортировано по визитам. Длина полосы — визиты, цвет и метка справа — конверсия в business-цель на этой точке входа. Большая полоса с серой меткой — трафик без отдачи."
        hint="Первая страница визита по данным Метрики. Длина полосы — визиты, метка справа — доля визитов с business-целью. Меньше 10 визитов — «мало данных» вместо процента. Читать: большая полоса с серой меткой — точка входа без отдачи.">
        {landings.length ? (
          <div className="space-y-1.5">
            {landings.map((l) => {
              const w = Math.max(2, Math.round(l.visits / maxLandingVisits * 100));
              // Порог малой выборки (этап 4б): % конверсии от <10 визитов —
              // статистический шум, вместо процента честная плашка.
              const small = l.visits < 10;
              const good = !small && l.goal_pct >= 10;
              const mid = !small && l.goal_pct >= 3 && l.goal_pct < 10;
              return (
                <div key={l.page} className="flex items-center gap-3" title={`${l.page}: ${fmtInt(l.visits)} визитов, ${fmtInt(l.goal_visits)} с целью${small ? '' : ` (${l.goal_pct}%)`}`}>
                  <span className="w-56 shrink-0 truncate text-[12.5px] text-text-primary" title={l.page}>{l.page}</span>
                  <div className="flex-1 h-5 rounded bg-obsidian-light/60 overflow-hidden relative">
                    <div
                      className="absolute inset-y-0 left-0 rounded"
                      style={{ width: `${w}%`, background: good ? 'rgba(22,163,74,0.75)' : mid ? 'rgba(184,148,47,0.75)' : 'rgba(26,26,46,0.28)' }}
                    />
                    <span className="absolute inset-y-0 left-2 flex items-center text-[11px] tabular-nums" style={{ color: w > 22 ? '#fff' : 'rgba(26,26,46,0.7)' }}>
                      {fmtInt(l.visits)}
                    </span>
                  </div>
                  <span className={`w-24 shrink-0 text-right text-[12px] tabular-nums font-medium ${good ? 'text-positive' : mid ? 'text-champagne' : 'text-text-tertiary'}`}>
                    {small ? 'мало данных' : `${l.goal_pct}% · ${fmtInt(l.goal_visits)}`}
                  </span>
                </div>
              );
            })}
            <div className="flex items-center gap-4 pt-2 text-[11px] text-text-tertiary">
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded" style={{ background: 'rgba(22,163,74,0.75)' }} /> конверсия ≥ 10%</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded" style={{ background: 'rgba(184,148,47,0.75)' }} /> 3–10%</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded" style={{ background: 'rgba(26,26,46,0.28)' }} /> &lt; 3%</span>
            </div>
            <Pager p={landPager} />
          </div>
        ) : <Empty note={d.metrika_live_today
          ? 'Повизитные посадочные Метрика отдаёт за завершённый день — появятся завтра после утреннего синка.'
          : undefined} />}
      </Card>
    </div>
  );
}

// Универсальная когортная таблица-heatmap: строки — когорты, колонки — смещения.
function CohortTable({ rows, keyField, offsetsField, cols, colPrefix }) {
  if (!rows?.length) return <Empty />;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[13px]">
        <thead>
          <tr className="text-left text-text-tertiary border-b border-border-subtle">
            <th className="py-1.5 pr-3 font-medium">Когорта</th>
            <th className="py-1.5 pr-3 font-medium">Размер</th>
            {cols.map((c) => <th key={c} className="py-1.5 pr-2 font-medium text-center">{colPrefix}{c}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((c) => (
            <tr key={c[keyField]} className="border-b border-border-subtle/50 last:border-0">
              <td className="py-1.5 pr-3 text-text-primary tabular-nums">{c[keyField]}</td>
              <td className="py-1.5 pr-3 text-text-secondary tabular-nums">{fmtInt(c.size)}</td>
              {cols.map((k) => {
                const v = c[offsetsField]?.[String(k)] || 0;
                const pct = c.size ? v / c.size : 0;
                return (
                  <td key={k} className="py-1 pr-2 text-center">
                    <span
                      className="inline-block min-w-9 rounded px-1.5 py-0.5 text-[12px] tabular-nums"
                      style={{ background: `rgba(184,148,47,${Math.min(0.85, pct * 2 + (v ? 0.08 : 0))})`, color: pct > 0.25 ? '#fff' : 'rgba(26,26,46,0.7)' }}
                      title={`${v} чел. = ${Math.round(pct * 100)}% когорты`}
                    >
                      {v || '·'}
                    </span>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RetentionTab({ d }) {
  const r = d.retention || {};
  const cohorts = useMemo(() => r.cohorts || [], [r.cohorts]);
  const dayCohorts = useMemo(() => r.day_cohorts || [], [r.day_cohorts]);

  // Кривая возвратов по ДНЯМ — рабочий масштаб молодого продукта.
  const dayCurve = useMemo(() => {
    const acc = {};
    for (const c of dayCohorts) {
      for (let i = 1; i <= 14; i += 1) {
        const v = c.day_plus?.[String(i)] || 0;
        if (!acc[i]) acc[i] = { ret: 0, size: 0 };
        acc[i].ret += v; acc[i].size += c.size;
      }
    }
    return Array.from({ length: 14 }, (_, i) => {
      const k = i + 1; const a = acc[k] || { ret: 0, size: 0 };
      return { day: `+${k}`, pct: a.size ? Math.round(a.ret / a.size * 1000) / 10 : 0 };
    });
  }, [dayCohorts]);
  const dayCols = Array.from({ length: 10 }, (_, i) => i + 1);
  const weekCols = [1, 2, 3, 4, 5, 6, 7, 8];
  const hasWeekData = cohorts.some((c) => Object.keys(c.week_plus || {}).length > 0);

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <Kpi label="Уникальных посетителей" value={fmtInt(r.unique_visitors)} sub="вся история наблюдений" />
        <Kpi label="Вернувшиеся (активны более одного дня)" value={fmtInt(r.returning_visitors)} color={GREEN} />
        <Kpi label="Доля возвратов" value={fmtPct(r.returning_pct)} color={GOLD} />
      </div>
      <Card title="Кривая возвратов по дням" icon={TrendingUp}
        insight="Средний по дневным когортам процент посетителей, вернувшихся через N дней после первого визита. Для молодого продукта дневной масштаб — основной; недельные когорты накопятся со временем."
        hint="Каждая точка — доля посетителей когорты дня, вернувшихся через N дней (данные Метрики по постоянному идентификатору). Читать: кривая, падающая к нулю за 2–3 дня, — продукт «одного визита»; полка — ядро постоянной аудитории.">
        <ResponsiveContainer width="100%" height={220}>
          <ComposedChart data={dayCurve} margin={{ top: 6, right: 12, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="gRet" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={GOLD} stopOpacity={0.25} />
                <stop offset="100%" stopColor={GOLD} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
            <XAxis dataKey="day" tick={{ fontSize: 11, fill: 'rgba(26,26,46,0.5)' }}
              label={{ value: 'дней после первого визита', position: 'insideBottom', offset: -2, fontSize: 10.5, fill: 'rgba(26,26,46,0.45)' }} />
            <YAxis unit="%" tick={{ fontSize: 11, fill: 'rgba(26,26,46,0.5)' }} width={40} />
            <Tooltip {...TT_STYLE} formatter={(v) => [`${v}%`, 'вернулись']} />
            <Area type="monotone" dataKey="pct" stroke={GOLD} fill="url(#gRet)" strokeWidth={2}>
              <LabelList dataKey="pct" position="top" formatter={(v) => (v ? `${v}%` : '')} style={{ fontSize: 10, fill: 'rgba(26,26,46,0.55)' }} />
            </Area>
          </ComposedChart>
        </ResponsiveContainer>
      </Card>
      <Card title="Когорты по дню первого визита" icon={Users}
        insight="Строка — новые посетители конкретного дня, столбцы — сколько из них вернулось через N дней. Насыщенность — доля вернувшихся (наведите для процента)."
        hint="Строка — день первого визита посетителя, колонки — процент вернувшихся через 1, 2, 3… дня (Метрика). Читать по диагонали: устойчиво зелёные колонки — привычка пользоваться продуктом формируется.">
        <CohortTable rows={dayCohorts} keyField="cohort_day" offsetsField="day_plus" cols={dayCols} colPrefix="+" />
      </Card>
      <Card title="Когорты по неделе первого визита" icon={Users}
        insight={hasWeekData
          ? 'Строка — когорта новых посетителей, столбцы — недели спустя. Насыщенность клетки — доля вернувшихся.'
          : 'Недельный масштаб станет информативным, когда истории наблюдений будет больше месяца — пока все посетители внутри первых недель.'}
        hint="То же, что дневные когорты, но по неделям — сглаживает шум малых чисел и показывает тренд удержания на горизонте месяцев.">
        <CohortTable rows={cohorts} keyField="cohort_week" offsetsField="week_plus" cols={weekCols} colPrefix="+" />
      </Card>
    </div>
  );
}

function PagesTab({ d }) {
  const pages = useMemo(() => (d.pages || []).map((p) => ({
    ...p,
    dwell: p.avg_dwell_sec ?? 0,
    problems: (p.dead_clicks || 0) + (p.rage_clicks || 0),
  })), [d.pages]);
  const medViews = median(pages.map((p) => p.pageviews));
  const medDwell = median(pages.filter((p) => p.dwell > 0).map((p) => p.dwell));

  // Pareto: какие страницы дают 80% просмотров.
  const pareto = useMemo(() => {
    const sorted = [...pages].sort((a, b) => b.pageviews - a.pageviews).slice(0, 20);
    const total = sorted.reduce((s, p) => s + p.pageviews, 0) || 1;
    return sorted.reduce((acc, p) => {
      const cum = (acc.length ? acc[acc.length - 1].cum_views : 0) + p.pageviews;
      acc.push({ name: p.page, views: p.pageviews, cum_views: cum, cum_pct: Math.round(cum / total * 100) });
      return acc;
    }, []);
  }, [pages]);

  const sections = (d.content_structure?.sections || []).filter((s) => s.views > 0);
  const totalSectionViews = sections.reduce((s, x) => s + x.views, 0) || 1;
  const treeData = sections.map((s, i) => ({
    name: s.name, views: s.views, share: Math.round(s.views / totalSectionViews * 100), index: i,
  }));

  const problem = pages.filter((p) => p.problems > 0)
    .sort((a, b) => b.problems - a.problems).slice(0, 10)
    .map((p) => ({ name: p.page, value: p.problems }));

  return (
    <div className="space-y-5">
      <Card title="Из чего состоит потребление контента" icon={LayoutGrid}
        insight="Площадь плитки — просмотры раздела за период. Видно, какие продуктовые блоки несут трафик, а какие простаивают."
        hint="Просмотры страниц нашего счётчика, сгруппированные в разделы сайта, за период. Площадь — доля просмотров. Читать: какие продукты реально несут трафик.">
        {treeData.length ? (
          <>
            <ResponsiveContainer width="100%" height={300}>
              <Treemap data={treeData} dataKey="views" nameKey="name" content={<TreemapCell />} isAnimationActive={false}>
                <Tooltip {...TT_STYLE}
                  content={({ active, payload }) => {
                    if (!active || !payload?.length) return null;
                    const p = payload[0].payload;
                    const sec = sections.find((s) => s.name === p.name);
                    return (
                      <div style={TT_STYLE.contentStyle}>
                        <div style={{ fontWeight: 600, marginBottom: 2 }}>{p.name}</div>
                        <div>{fmtInt(p.views)} просмотров · {p.share}%</div>
                        {sec?.top_pages?.slice(0, 3).map((tp) => (
                          <div key={tp.page} style={{ color: 'rgba(26,26,46,0.6)' }}>{clip(tp.page, 34)} — {fmtInt(tp.views)}</div>
                        ))}
                      </div>
                    );
                  }} />
              </Treemap>
            </ResponsiveContainer>
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-1 mt-3">
              {sections.slice(0, 6).map((s, i) => (
                <div key={s.name} className="text-[12px] text-text-secondary flex items-center gap-1.5 min-w-0">
                  <span className="w-2 h-2 rounded-sm shrink-0" style={{ background: PALETTE[i % PALETTE.length] }} />
                  <span className="truncate">{s.name}</span>
                  <span className="tabular-nums text-text-tertiary shrink-0">{fmtInt(s.views)}</span>
                </div>
              ))}
            </div>
          </>
        ) : <Empty />}
      </Card>

      <Card title="Концентрация трафика: правило 80/20" icon={TrendingUp}
        insight="Столбцы — просмотры страниц (топ-20), линия — накопленная доля от их суммы. Где линия пересекает 80% — столько страниц несут основную нагрузку."
        hint="Страницы отсортированы по просмотрам (наш счётчик), линия — накопленная доля. Читать: если 20% страниц дают 80% трафика — усиливать топ и подтягивать хвост перелинковкой.">
        {pareto.length ? (
          <ResponsiveContainer width="100%" height={280}>
            <ComposedChart data={pareto} margin={{ top: 6, right: 44, bottom: 40, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
              <XAxis dataKey="name" tick={{ fontSize: 9.5, fill: 'rgba(26,26,46,0.55)', angle: -35, textAnchor: 'end' }} interval={0} height={58} tickFormatter={(v) => clip(v, 18)} />
              <YAxis yAxisId="l" tick={{ fontSize: 11, fill: 'rgba(26,26,46,0.5)' }} width={40} />
              <YAxis yAxisId="r" orientation="right" unit="%" domain={[0, 100]} tick={{ fontSize: 11, fill: 'rgba(26,26,46,0.5)' }} width={42} />
              <Tooltip {...TT_STYLE} formatter={(v, n) => [n === 'Накопленная доля' ? `${v}%` : fmtInt(v), n]} />
              <ReferenceLine yAxisId="r" y={80} stroke="rgba(220,38,38,0.35)" strokeDasharray="4 4" label={{ value: '80%', fontSize: 10, fill: 'rgba(220,38,38,0.7)', position: 'right' }} />
              <Bar yAxisId="l" dataKey="views" name="Просмотры" fill={GOLD} radius={[3, 3, 0, 0]} maxBarSize={26} />
              <Line yAxisId="r" type="monotone" dataKey="cum_pct" name="Накопленная доля" stroke={INK} strokeWidth={1.8} dot={{ r: 2.5 }} />
            </ComposedChart>
          </ResponsiveContainer>
        ) : <Empty />}
      </Card>

      <Card title="Карта качества: просмотры и вовлечённость" icon={Activity}
        insight="По горизонтали — просмотры, по вертикали — среднее время на странице. Правый низ (много просмотров, мало времени) — популярные «тонкие» страницы, кандидаты на доработку. Пунктир — медианы."
        hint="Каждая точка — страница: по горизонтали просмотры (наш счётчик), по вертикали активное время чтения. Читать: правый низ — популярные, но не удерживающие страницы, кандидаты на переработку.">
        {pages.length ? (
          <ResponsiveContainer width="100%" height={320}>
            <ScatterChart margin={{ top: 10, right: 20, bottom: 20, left: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
              <XAxis type="number" dataKey="pageviews" name="Просмотры" tick={{ fontSize: 11, fill: 'rgba(26,26,46,0.5)' }}
                label={{ value: 'просмотры', position: 'insideBottom', offset: -8, fontSize: 11, fill: 'rgba(26,26,46,0.5)' }} />
              <YAxis type="number" dataKey="dwell" name="Время, с" unit="с" tick={{ fontSize: 11, fill: 'rgba(26,26,46,0.5)' }} width={48} />
              <ZAxis type="number" dataKey="problems" range={[50, 480]} name="Проблемные клики" />
              {medViews > 0 && <ReferenceLine x={medViews} stroke="rgba(26,26,46,0.25)" strokeDasharray="4 4" />}
              {medDwell > 0 && <ReferenceLine y={medDwell} stroke="rgba(26,26,46,0.25)" strokeDasharray="4 4" />}
              <Tooltip {...TT_STYLE} cursor={{ strokeDasharray: '3 3' }}
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const p = payload[0].payload;
                  return (
                    <div style={TT_STYLE.contentStyle}>
                      <div style={{ fontWeight: 600, marginBottom: 2 }}>{p.page}</div>
                      <div>Просмотры: {fmtInt(p.pageviews)}</div>
                      <div>Время: {p.avg_dwell_sec ?? '—'} с · прокрутка {p.avg_scroll_pct ?? '—'}%</div>
                      <div>Пустые клики: {fmtInt(p.dead_clicks)} · серии: {fmtInt(p.rage_clicks)} · отказы {p.bounce_pct ?? '—'}%</div>
                    </div>
                  );
                }} />
              <Scatter data={pages} fill={GOLD} fillOpacity={0.5} />
            </ScatterChart>
          </ResponsiveContainer>
        ) : <Empty />}
      </Card>

      <Card title="Страницы с проблемными кликами" icon={AlertTriangle}
        insight="Пустые клики (без реакции интерфейса) и серии раздражённых кликов — прямые кандидаты на исправление UX."
        hint="Страницы с наибольшим числом пустых (без реакции интерфейса) и раздражённых (серии быстрых) кликов из потока поведения. Читать: сверху — самые болезненные точки UX.">
        <HBars data={problem} color={RED} labelWidth={190} />
      </Card>
    </div>
  );
}

function DemandTab({ d }) {
  const dem = d.demand || {};
  const s = d.onsite_search || {};
  const wm = (dem.webmaster_queries || []).filter((q) => q.impressions > 0 && q.avg_position != null);
  const CTX_RU = {
    global: 'Глобальный поиск (⌘K)',
    'compare-macro': 'Поиск в сравнении',
    'regions-map': 'Поиск показателя карты',
    regions: 'Поиск по регионам',
  };

  return (
    <div className="space-y-5">
      <Card title="Карта возможностей в поиске Яндекса: показы и позиция" icon={Search} source="metrika"
        insight={`Данные Яндекс.Вебмастера. По горизонтали — показы, по вертикали — средняя позиция (выше = лучше, ось перевёрнута), размер точки — клики. Правый низ (много показов, слабая позиция) — запросы с наибольшим потенциалом роста трафика.${
          dem.webmaster_window?.fallback ? ` Вебмастер отдаёт статистику с лагом — показано последнее доступное окно: ${dem.webmaster_window.from} — ${dem.webmaster_window.to}.` : ''
        }`}
        hint="Запросы из Яндекс.Вебмастера: показы в выдаче, средняя позиция, размер точки — клики. Вебмастер отдаёт данные с лагом в несколько дней. Читать: правый низ — большой спрос при слабой позиции, главные кандидаты на SEO-работу.">
        {wm.length ? (
          <ResponsiveContainer width="100%" height={340}>
            <ScatterChart margin={{ top: 10, right: 20, bottom: 20, left: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
              <XAxis type="number" dataKey="impressions" name="Показы" tick={{ fontSize: 11, fill: 'rgba(26,26,46,0.5)' }}
                label={{ value: 'показы', position: 'insideBottom', offset: -8, fontSize: 11, fill: 'rgba(26,26,46,0.5)' }} />
              <YAxis type="number" dataKey="avg_position" name="Позиция" reversed tick={{ fontSize: 11, fill: 'rgba(26,26,46,0.5)' }} width={40} />
              <ZAxis type="number" dataKey="clicks" range={[50, 480]} name="Клики" />
              <ReferenceLine y={10} stroke="rgba(22,163,74,0.4)" strokeDasharray="4 4" label={{ value: 'первая страница выдачи', fontSize: 10, fill: 'rgba(22,163,74,0.7)', position: 'insideTopLeft' }} />
              <Tooltip {...TT_STYLE} cursor={{ strokeDasharray: '3 3' }}
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const p = payload[0].payload;
                  return (
                    <div style={TT_STYLE.contentStyle}>
                      <div style={{ fontWeight: 600, marginBottom: 2 }}>{p.query}</div>
                      <div>Показы: {fmtInt(p.impressions)} · клики: {fmtInt(p.clicks)}</div>
                      <div>Средняя позиция: {p.avg_position}</div>
                    </div>
                  );
                }} />
              <Scatter data={wm} fill={BLUE} fillOpacity={0.55} />
            </ScatterChart>
          </ResponsiveContainer>
        ) : <Empty note="Данные Вебмастера за период отсутствуют — Яндекс отдаёт статистику запросов с задержкой в несколько дней." />}
      </Card>
      <div className="grid lg:grid-cols-2 gap-5">
        <Card title="Поиски на сайте без результата" icon={AlertTriangle} source="own"
          insight="Прямая карта пробелов каталога: что ищут, но не находят. Приоритет на добавление. Недопечатки схлопнуты, односимвольный мусор отброшен."
        hint="Запросы во внутренний поиск (наше событие search_query), на которые каталог не вернул ни одного результата. Читать: прямой список того, что аудитория ждёт от платформы, — приоритет на добавление.">
          <PhraseTable rows={collapsePhrases(s.zero_results, { limit: 200 })} valueLabel="поисков" />
        </Card>
        <Card title="Фразы прихода из поиска" icon={Search} source="metrika" insight="Реальный органический спрос, приведший визиты за период."
        hint="Поисковые фразы визитов по повизитным данным Метрики за завершённые дни периода. Читать: чем разнообразнее хвост, тем шире органический охват.">
          <PhraseTable
            rows={collapsePhrases(
              Object.fromEntries((dem.metrika_phrases || []).map((p) => [p.phrase, p.visits])),
              { limit: 200 },
            )}
            valueLabel="визитов"
          />
        </Card>
      </div>
      <Card title="Что ищут внутри сайта — по полям поиска" icon={Search}
        insight={`Каждое поле поиска сайта — отдельный срез спроса. Всего запросов за период: ${fmtInt(s.total_queries)}.`}
        hint="Внутренние запросы нашего счётчика, разбитые по месту ввода: глобальный поиск, поиск сравнения, карта регионов. Читать: спрос в каждом контексте свой — глобальный поиск ищет индикаторы, карта — показатели регионов.">
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {Object.entries(s.by_context || {}).map(([ctx, counter]) => (
            <div key={ctx}>
              <div className="text-[12px] font-medium text-text-secondary mb-2">{CTX_RU[ctx] || ctx}</div>
              <HBars data={dictToBars(counter, 6)} height={Math.max(90, Math.min(6, Object.keys(counter).length) * 28)} />
            </div>
          ))}
          {!Object.keys(s.by_context || {}).length && <Empty />}
        </div>
      </Card>
    </div>
  );
}

function NavigationTab({ d }) {
  const n = d.navigation || {};
  const b = d.behavior_issues || {};
  return (
    <div className="space-y-5">
      <Card title="Матрица переходов: откуда и куда перетекает трафик" icon={Route}
        insight="Строки — страница-источник, столбцы — страница-назначение, насыщенность клетки — число переходов. Читается по строке: куда уходит посетитель с ключевой страницы."
        hint="Переходы между разделами внутри сессий нашего счётчика: строка — откуда, столбец — куда, насыщенность — число переходов. Читать по строке: куда уходит посетитель с ключевой страницы; пустая строка — тупик.">
        <TransitionMatrix transitions={n.top_transitions} />
      </Card>
      <div className="grid lg:grid-cols-2 gap-5">
        <Card title="Точки входа" icon={LogIn} insight="С каких страниц начинаются сессии."
        hint="Первая страница сессии по нашему счётчику. Читать: что реально приводит людей — эти страницы должны загружаться быстро и вести вглубь.">
          <HBars data={dictToBars(n.top_entries, 10)} color={GREEN} labelWidth={190} />
        </Card>
        <Card title="Точки выхода" icon={Route} insight="Где сессии обрываются — кандидаты на усиление перелинковки и призывов к действию."
        hint="Последняя страница сессии по нашему счётчику. Читать: страницы с большим выходом — кандидаты на усиление перелинковки и призывов к действию.">
          <HBars data={dictToBars(n.top_exits, 10)} color={RED} labelWidth={190} />
        </Card>
        <Card title="Пустые клики: элементы без реакции" icon={MousePointerClick} insight="Пользователь кликает, интерфейс не отвечает. Каждая строка — конкретный элемент на конкретной странице."
        hint="Клики из потока поведения, после которых интерфейс не изменился (dead click). Указан элемент и страница. Читать: сверху — элементы, которые выглядят кликабельными, но не работают.">
          {(b.dead || []).length ? (
            <ul className="space-y-1.5">
              {(b.dead || []).map((x, i) => (
                <li key={i} className="flex items-baseline gap-2 text-[12.5px]">
                  <span className="tabular-nums font-semibold text-negative w-8 shrink-0 text-right">{fmtInt(x.count)}</span>
                  <span className="min-w-0">
                    <span className="text-text-primary">{clip(x.page, 32)}</span>
                    <span className="text-text-tertiary font-mono text-[11px] block truncate" title={x.element}>{clip(x.element, 52)}</span>
                  </span>
                </li>
              ))}
            </ul>
          ) : <Empty />}
        </Card>
        <Card title="Серии раздражённых кликов" icon={MousePointerClick} insight="Многократные быстрые клики в одно место — признак «не работает» или «слишком медленно»."
        hint="Три и более быстрых клика в одну точку (rage click) — признак «не работает» или «слишком медленно». Читать: каждая строка — конкретное место фрустрации.">
          {(b.rage || []).length ? (
            <ul className="space-y-1.5">
              {(b.rage || []).map((x, i) => (
                <li key={i} className="flex items-baseline gap-2 text-[12.5px]">
                  <span className="tabular-nums font-semibold text-negative w-8 shrink-0 text-right">{fmtInt(x.count)}</span>
                  <span className="min-w-0">
                    <span className="text-text-primary">{clip(x.page, 32)}</span>
                    <span className="text-text-tertiary font-mono text-[11px] block truncate" title={x.element}>{clip(x.element, 52)}</span>
                  </span>
                </li>
              ))}
            </ul>
          ) : <Empty />}
        </Card>
      </div>
    </div>
  );
}

const deviceRu = deviceLabel;

// Парная сверка «наш счётчик vs Метрика»: два рейтинга одного среза рядом.
function PairedBars({ own, metrika, ownLabel = 'Наш счётчик', metrikaLabel = 'Метрика', mapName = (x) => x, n = 8 }) {
  const ownRows = dictToBars(own, n).map((r) => ({ ...r, name: mapName(r.name) }));
  const mRows = dictToBars(metrika, n).map((r) => ({ ...r, name: mapName(r.name) }));
  if (!ownRows.length && !mRows.length) return <Empty />;
  return (
    <div className="grid sm:grid-cols-2 gap-5">
      <div>
        <div className="text-[12px] font-medium text-text-secondary mb-2">{ownLabel}</div>
        {ownRows.length ? <HBars data={ownRows} color={PURPLE} labelWidth={130} /> : <Empty note="Собственный счётчик ещё копит данные" />}
      </div>
      <div>
        <div className="text-[12px] font-medium text-text-secondary mb-2">{metrikaLabel}</div>
        {mRows.length ? <HBars data={mRows} color={GOLD} labelWidth={130} /> : <Empty note="Метрика не отдала срез за период" />}
      </div>
    </div>
  );
}

function AudienceTab({ d }) {
  const a = d.audience || {};
  const ref = a.metrika_reference || {};
  const devOwn = Object.entries(a.devices || {}).filter(([k]) => k !== 'bot')
    .map(([k, v]) => ({ name: deviceRu(k), value: v }));
  const devMetrika = Object.entries(ref.devices || {}).map(([k, v]) => ({ name: deviceRu(k), value: v }));

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        <Kpi label="Сессии (наш счётчик)" value={fmtInt(a.own_sessions_total)} color={PURPLE} sub="все небот-сессии за период" />
        <Kpi label="С полным портретом" value={fmtInt(a.portraits_total)} color={BLUE}
          sub={a.portrait_coverage_pct != null ? `${a.portrait_coverage_pct}% сессий — база для браузеров и ОС` : 'база для браузеров и ОС'} />
        <Kpi label="Сессии зарегистрированных" value={fmtInt(a.own_authed_sessions)} color={GREEN} />
        <Kpi label="Визиты (Метрика, сверка)" value={fmtInt(ref.visits_total)} />
        <Kpi
          label="Расхождение слоёв"
          value={a.own_sessions_total && ref.visits_total
            ? fmtPct(Math.round(Math.abs(a.own_sessions_total - ref.visits_total) / ref.visits_total * 100))
            : '—'}
          color={INK}
          sub="сессии ≠ визиты по определению; большой разрыв — сигнал"
        />
      </div>

      <Card title="Устройства: наш счётчик и Метрика" icon={Users} source="both"
        hint="Слева — все небот-сессии нашего счётчика за период (тип устройства определяется по паспорту сессии, а при его отсутствии — по касаниям и ширине окна из потока событий). Справа — визиты Метрики за тот же период."
        insight="Один и тот же срез из двух независимых источников. Сходство подтверждает качество собственного сбора; расхождение — повод проверить, кого мы не видим (например, посетителей без JavaScript).">
        <div className="grid sm:grid-cols-2 gap-5">
          <div>
            <div className="text-[12px] font-medium text-text-secondary mb-2">Наш счётчик</div>
            <Donut data={devOwn} height={180} centerLabel="сессий" />
          </div>
          <div>
            <div className="text-[12px] font-medium text-text-secondary mb-2">Метрика</div>
            <Donut data={devMetrika} height={180} centerLabel="визитов" />
          </div>
        </div>
      </Card>

      <Card title="Браузеры" icon={LayoutGrid} source="both"
        hint={`Наш срез строится из паспортов сессий (User-Agent), покрытие — ${a.portrait_coverage_pct != null ? `${a.portrait_coverage_pct}%` : 'растёт'} сессий периода; справа — референс Метрики по визитам. Доли сопоставимы, абсолютные числа — нет.`}
        insight="Чем пользуется аудитория — приоритет тестирования интерфейса. Слева — наши данные с точными версиями, справа — референс Метрики.">
        <PairedBars own={a.browsers} metrika={ref.browsers} />
        {Object.keys(a.browser_versions || {}).length > 0 && (
          <div className="mt-4">
            <div className="text-[12px] font-medium text-text-secondary mb-2">Точные версии (наш счётчик)</div>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(a.browser_versions).map(([k, v]) => (
                <span key={k} className="inline-flex items-center gap-1 rounded-full bg-obsidian-light/70 px-2 py-0.5 text-[11.5px]">
                  <span className="text-text-secondary">{k}</span>
                  <span className="tabular-nums font-medium text-text-primary">{fmtInt(v)}</span>
                </span>
              ))}
            </div>
          </div>
        )}
      </Card>

      <Card title="Операционные системы" icon={LayoutGrid}
        insight="Наши данные включают версию системы — точнее, чем агрегат Метрики."
        hint="Наш срез — из паспортов сессий (User-Agent с версией системы); справа — референс Метрики по визитам. Читать: доли важнее абсолютных чисел — базы разные.">
        <PairedBars own={a.os} metrika={ref.os} />
      </Card>

      <div className="grid lg:grid-cols-2 gap-5">
        <Card title="Экраны" icon={LayoutGrid}
          insight="Физические разрешения экранов — под какие размеры проектировать интерфейс и графики."
        hint="Физическое разрешение экрана из паспортов сессий нашего счётчика. Читать: под верхние 2–3 разрешения проектируются графики и таблицы.">
          <HBars data={dictToBars(a.screens, 10)} color={BLUE} labelWidth={110} />
        </Card>
        <Card title="Ширина окна браузера" icon={LayoutGrid}
          insight="Реальная ширина рабочей области — важнее разрешения экрана: окна бывают свёрнуты."
        hint="Фактическая ширина окна (viewport) при входе — по всем сессиям, где она известна. Читать: именно под неё, а не под разрешение экрана, вёрстка должна быть удобной.">
          <HBars data={dictToBars(a.viewports, 10)} color={BLUE} labelWidth={110} />
        </Card>
        <Card title="Языки и часовые пояса" icon={Users}
          insight="Язык браузера и таймзона — география и локализация аудитории без сбора персональных данных."
        hint="Язык браузера и часовой пояс из паспортов сессий — косвенная география и локализация без сбора персональных данных.">
          <div className="grid grid-cols-2 gap-4">
            <HBars data={dictToBars(a.languages, 8, languageLabel)} color={GREEN} labelWidth={90} />
            <HBars data={dictToBars(a.timezones, 8, timezoneLabel)} color={GREEN} labelWidth={130} />
          </div>
        </Card>
        <Card title="Сайты-источники переходов" icon={Route}
          insight="Домены, с которых пришли сессии по данным собственного счётчика."
        hint="Домены, с которых пришли сессии по нашему счётчику (свой домен исключён). Читать: живые упоминания и партнёрские ссылки; новый домен в топе — повод посмотреть, кто сослался.">
          <HBars data={dictToBars(a.referrer_hosts, 10)} color={PURPLE} labelWidth={160} />
        </Card>
      </div>
    </div>
  );
}

function EventsTab({ d }) {
  const all = Object.entries(d.events || {})
    .map(([name, v]) => ({ name, label: eventLabel(name), authed: v.authed, guest: v.guest, total: v.total }))
    .sort((a, b) => b.total - a.total);
  const rows = all.slice(0, 24);
  return (
    <div className="space-y-5">
      <Card title="Бизнес-события: гости и зарегистрированные" icon={Activity}
        insight="Каждая полоса — действие на сайте (тёмный сегмент — зарегистрированные, золотой — гости). Видно, какие действия делают авторизованные пользователи, а какие — случайные посетители."
        hint="Каждое срабатывание бизнес-событий нашего счётчика за период, разрез гость/аккаунт. Читать: действия, которые совершают только зарегистрированные, — ценность аккаунта; полный список — в реестре ниже.">
        {rows.length ? (
          <ResponsiveContainer width="100%" height={Math.max(260, rows.length * 27)}>
            <BarChart layout="vertical" data={rows} margin={{ top: 2, right: 48, bottom: 2, left: 4 }}>
              <XAxis type="number" hide />
              <YAxis type="category" dataKey="label" width={230} tick={{ fontSize: 11, fill: 'rgba(26,26,46,0.72)' }} tickFormatter={(v) => clip(v, 34)} interval={0} />
              <Tooltip {...TT_STYLE}
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const p = payload[0].payload;
                  return (
                    <div style={TT_STYLE.contentStyle}>
                      <div style={{ fontWeight: 600, marginBottom: 2 }}>{p.label}</div>
                      <div style={{ color: 'rgba(26,26,46,0.55)', fontFamily: 'monospace', fontSize: 11 }}>{p.name}</div>
                      <div>Всего: {fmtInt(p.total)} · зарегистрированные: {fmtInt(p.authed)} · гости: {fmtInt(p.guest)}</div>
                    </div>
                  );
                }} />
              <Legend wrapperStyle={{ fontSize: 11 }} formatter={(v) => (v === 'authed' ? 'Зарегистрированные' : 'Гости')} />
              <Bar dataKey="authed" name="authed" stackId="e" fill={INK} maxBarSize={20} />
              <Bar dataKey="guest" name="guest" stackId="e" fill={GOLD} maxBarSize={20} radius={[0, 4, 4, 0]}>
                <LabelList dataKey="total" position="right" formatter={fmtInt} style={{ fontSize: 10.5, fill: 'rgba(26,26,46,0.6)' }} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        ) : <Empty />}
      </Card>
      <EventsRegistryCard all={all} />
    </div>
  );
}

function EventsRegistryCard({ all }) {
  const pager = usePager(all, 25);
  return (
    <Card title="Полный реестр событий за период" icon={Database} source="own"
      hint="Каждая строка — тип бизнес-события нашего счётчика (track.js) с числом срабатываний за выбранный период. «Зарегистр.» — события от авторизованных пользователей, «Гости» — от анонимных посетителей. Список листается до конца."
      insight="Все события с точными числами — включая редкие, которых не видно на графике.">
      {all.length ? (
        <div className="overflow-x-auto">
          <table className="w-full text-[12.5px]">
            <thead>
              <tr className="text-left text-text-tertiary border-b border-border-subtle">
                <th className="py-1.5 pr-3 font-medium">Событие</th>
                <th className="py-1.5 pr-3 font-medium">Техноним</th>
                <th className="py-1.5 pr-3 font-medium text-right">Всего</th>
                <th className="py-1.5 pr-3 font-medium text-right">Зарегистр.</th>
                <th className="py-1.5 pr-3 font-medium text-right">Гости</th>
              </tr>
            </thead>
            <tbody>
              {pager.slice.map((e) => (
                <tr key={e.name} className="border-b border-border-subtle/50 last:border-0">
                  <td className="py-1 pr-3 text-text-primary">{e.label}</td>
                  <td className="py-1 pr-3 text-text-tertiary font-mono text-[11px]">{e.name}</td>
                  <td className="py-1 pr-3 text-right tabular-nums text-text-primary font-medium">{fmtInt(e.total)}</td>
                  <td className="py-1 pr-3 text-right tabular-nums text-text-secondary">{fmtInt(e.authed)}</td>
                  <td className="py-1 pr-3 text-right tabular-nums text-text-secondary">{fmtInt(e.guest)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <Pager p={pager} />
        </div>
      ) : <Empty />}
    </Card>
  );
}

function HypothesesTab({ d, onOpenSlices }) {
  const rows = d.hypotheses || [];
  if (!rows.length) {
    return <Card title="Гипотезы Пульс-аналитика" icon={Brain}
        hint="Проверяемые гипотезы, которые ежедневно формулирует и проверяет LLM-аналитик по данным платформы. Статус: подтверждена / опровергнута / открыта, с уверенностью."><p className="text-[13px] text-text-tertiary">Гипотез пока нет — Пульс формулирует их ежедневно после утреннего отчёта.</p></Card>;
  }
  return (
    <div className="space-y-3">
      {rows.map((h) => (
        <div key={h.id} className="rounded-2xl bg-surface border border-border-subtle p-4">
          <div className="flex items-start gap-3">
            <span className={`mt-0.5 shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ${
              h.verdict === true ? 'bg-positive/10 text-positive'
                : h.verdict === false ? 'bg-negative/10 text-negative'
                  : 'bg-champagne/10 text-champagne'
            }`}
            >
              {h.verdict === true ? 'подтверждена' : h.verdict === false ? 'опровергнута' : 'открыта'}
            </span>
            <div className="min-w-0 flex-1">
              <div className="text-[14px] text-text-primary">{h.statement}</div>
              {h.rationale && <div className="text-[12px] text-text-secondary mt-1">{h.rationale}</div>}
              <div className="text-[11px] text-text-tertiary mt-1">
                {h.confidence != null && `уверенность ${Math.round(h.confidence * 100)}% · `}
                {h.source} · {h.updated_at?.slice(0, 10)}
              </div>
            </div>
            {onOpenSlices && (
              <button
                type="button" onClick={onOpenSlices}
                className="shrink-0 text-[11px] text-champagne hover:underline whitespace-nowrap"
                title="Открыть OLAP-конструктор и проверить гипотезу произвольным срезом"
              >
                проверить в Срезах →
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

// Порядок и названия полей инвентаризации — раскрываем ВСЁ содержимое слоёв.
const DATASET_FIELD_RU = {
  rows: 'строк',
  columns: 'колонок таблицы',
  event_names: 'типов событий',
  distinct_phrases: 'уникальных фраз',
  from: 'с',
  to: 'по',
  users: 'пользователей',
  indicator_points: 'точек макрорядов',
  region_points: 'точек регионов',
};
const DATASET_TITLE_RU = {
  behavior_events: 'Поведенческий поток (клики, прокрутка, курсор)',
  behavior_sessions: 'Портреты сессий (браузер, устройство, экран)',
  frontend_events: 'Бизнес-события интерфейса',
  raw_metrika_visits: 'Повизитная выгрузка Метрики',
  metrika_search_phrases: 'Поисковые фразы (Метрика)',
  metrika_daily_page_metrics: 'Дневные метрики страниц (Метрика)',
  metrika_report_snapshots: 'Снапшоты отчётов Метрики',
  webmaster_search_queries: 'Запросы из поиска (Вебмастер)',
  telegram_outbox: 'Архив исходящих Telegram',
  hypotheses: 'Гипотезы (слой знаний)',
  core: 'Продуктовое ядро',
};

function DatasetTab({ d }) {
  const inv = d.dataset || {};
  const sections = inv.sections || {};
  const totals = inv.totals || {};
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <Kpi label="Всего строк в датасете" value={fmtInt(totals.rows)} />
        <Kpi label="Всего параметров (колонки + ключи + типы)" value={fmtInt(totals.parameters)} color={BLUE} />
        <Kpi label="Слоёв данных" value={fmtInt(Object.keys(sections).length)} color={GREEN} />
      </div>
      <Card title="Инвентаризация: каждый слой с полным составом" icon={Database}
        insight="Всё, что копится в хранилище: объёмы, окна времени, фактические ключи JSON-полей и разбивки по типам. Данные пересчитываются из БД при каждом обновлении."
        hint="Автоматическая опись всех слоёв данных платформы: сколько строк, какие поля, какие ключи JSON. Читать: это карта того, что вообще можно спросить у данных.">
        <div className="grid sm:grid-cols-2 gap-4">
          {Object.entries(sections).map(([name, s]) => {
            if (typeof s !== 'object' || s == null) return null;
            const scalars = Object.entries(s).filter(([k, v]) => typeof v !== 'object' && k !== 'title');
            const dicts = Object.entries(s).filter(([, v]) => v && typeof v === 'object' && !Array.isArray(v));
            const lists = Object.entries(s).filter(([, v]) => Array.isArray(v));
            return (
              <div key={name} className="rounded-xl border border-border-subtle p-4">
                <div className="text-[13px] font-semibold text-text-primary mb-0.5">{DATASET_TITLE_RU[name] || s.title || name}</div>
                <div className="text-[10.5px] text-text-tertiary font-mono mb-2">{name}</div>
                <div className="flex flex-wrap gap-x-4 gap-y-1 mb-2">
                  {scalars.map(([k, v]) => (
                    <span key={k} className="text-[12px] text-text-secondary">
                      <span className="text-text-tertiary">{DATASET_FIELD_RU[k] || k}:</span>{' '}
                      <span className="tabular-nums font-medium text-text-primary">
                        {typeof v === 'number' ? fmtInt(v) : String(v).slice(0, 16)}
                      </span>
                    </span>
                  ))}
                </div>
                {dicts.map(([k, obj]) => (
                  <div key={k} className="mb-2">
                    <div className="text-[11px] text-text-tertiary mb-1">{k === 'by_type' ? 'по типам событий' : k === 'by_kind' ? 'по видам отправок' : k === 'by_verdict' ? 'по вердиктам' : k === 'report_types' ? 'по типам отчётов' : k}</div>
                    <div className="flex flex-wrap gap-1">
                      {Object.entries(obj).map(([kk, vv]) => (
                        <span key={kk} className="inline-flex items-center gap-1 rounded-full bg-obsidian-light/70 px-2 py-0.5 text-[11px]">
                          <span className="text-text-secondary">{kk}</span>
                          <span className="tabular-nums font-medium text-text-primary">{fmtInt(vv)}</span>
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
                {lists.map(([k, arr]) => (
                  <div key={k}>
                    <div className="text-[11px] text-text-tertiary mb-1">{k === 'json_keys' ? `ключи JSON-полей (${arr.length})` : k}</div>
                    <div className="flex flex-wrap gap-1 max-h-28 overflow-y-auto">
                      {arr.map((kk) => (
                        <span key={kk} className="rounded bg-obsidian-light/50 px-1.5 py-0.5 text-[10.5px] font-mono text-text-secondary">{kk}</span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}

/* ---------- Аналитика 2.0: executive-вкладки ---------- */

const STATUS_COLOR = { green: GREEN, yellow: '#D97706', red: RED };
const STATUS_RU = { green: 'в норме', yellow: 'ниже цели', red: 'критично' };
const TIER_RU = { macro: 'Макро', micro: 'Микро', intent: 'Намерение', engagement: 'Вовлечение', technical: 'Технические' };
const TIER_COLOR = { macro: GREEN, micro: BLUE, intent: PURPLE, engagement: GOLD, technical: 'rgba(26,26,46,0.35)' };

function fmtDriverValue(node) {
  if (node.format === 'pct') return `${Number(node.value).toLocaleString('ru-RU')}%`;
  return fmtInt(Math.round(node.value));
}

// Методика драйверов дерева (этап 4а BI 2.1): что стоит за каждым числом.
const DRIVER_HINTS = {
  acquisition: 'Сессии нашего счётчика за выбранный период — без ботов и собственной активности. Канал определяется по рекламным меткам (yclid/UTM) и сайту-источнику первого перехода сессии; заход без всяких признаков — «Прямые заходы».',
  engagement: 'Доля вовлечённых сессий среди небот-сессий за период. Вовлечённой считается сессия с активным временем на странице больше 15 секунд, скроллом глубже 50% или просмотром двух и более страниц.',
  conversion: 'Доля сессий с бизнес-целью нашей таксономии: макро (регистрация, подписка) и микро (выгрузка, сравнение, интент связи). Навигация, скролл и телеметрия целями не считаются.',
  retention: 'Доля посетителей, вернувшихся на сайт в другой календарный день внутри окна. Идентификация — по постоянному идентификатору посетителя нашего счётчика, когорты — по дню первой сессии.',
};

// Узел дерева метрик: значение, target, статус-цвет, прогресс-бар, раскрытие.
function DriverNode({ node }) {
  const [open, setOpen] = useState(false);
  const color = STATUS_COLOR[node.status] || GOLD;
  const progress = node.target ? Math.min(node.value / node.target * 100, 100) : 0;
  const det = node.detail || {};
  return (
    <div className="rounded-2xl bg-surface border border-border-subtle p-4">
      <button type="button" onClick={() => setOpen((v) => !v)} className="w-full text-left">
        <div className="flex items-center justify-between gap-2">
          <span className="flex items-center gap-1.5 text-[12.5px] text-text-tertiary">
            {node.label}
            {DRIVER_HINTS[node.key] && <MethodHint text={DRIVER_HINTS[node.key]} />}
          </span>
          <span className="text-[10px] px-1.5 py-0.5 rounded-full font-medium" style={{ background: `${color}18`, color }}>
            {STATUS_RU[node.status] || node.status}
          </span>
        </div>
        <div className="flex items-baseline gap-2 mt-1">
          <span className="text-2xl font-bold tabular-nums text-text-primary">{fmtDriverValue(node)}</span>
          <span className="text-[11.5px] text-text-tertiary">
            цель {node.format === 'pct' ? `${node.target}%` : fmtInt(node.target)}
          </span>
        </div>
        <div className="mt-2 h-1.5 rounded-full bg-obsidian overflow-hidden">
          <div className="h-full rounded-full transition-all" style={{ width: `${progress}%`, background: color }} />
        </div>
        <div className="text-[10.5px] text-text-tertiary mt-1.5">{open ? 'Скрыть детали ▲' : 'Раскрыть ▼'}</div>
      </button>
      {open && (
        <div className="mt-3 pt-3 border-t border-border-subtle space-y-1 text-[12px] text-text-secondary">
          {node.key === 'acquisition' && (
            <>
              {Object.entries(det.channels || {}).sort((a, b) => b[1] - a[1]).map(([ch, v]) => (
                <div key={ch} className="flex justify-between"><span>{channelLabel(ch)}</span><span className="tabular-nums">{fmtInt(v)}</span></div>
              ))}
              <div className="flex justify-between pt-1 text-text-tertiary">
                <span>Доля поиска</span>
                <span className="tabular-nums">{Math.round((det.search_share || 0) * 100)}% (цель {Math.round((det.search_share_target || 0) * 100)}%)</span>
              </div>
            </>
          )}
          {node.key === 'engagement' && (
            <>
              <div className="flex justify-between"><span>Сессий за 7 дней</span><span className="tabular-nums">{fmtInt(det.sessions)}</span></div>
              <div className="flex justify-between"><span>Из них вовлечённых</span><span className="tabular-nums">{fmtInt(det.engaged)}</span></div>
              <p className="text-text-tertiary pt-1">Вовлечён: активный dwell &gt;15 с, скролл &gt;50% или 2+ страницы.</p>
            </>
          )}
          {node.key === 'conversion' && (
            <>
              <div className="flex justify-between"><span>Микро-цели (сессий)</span><span className="tabular-nums">{fmtInt(det.micro_sessions)} · {det.micro_rate_pct}%</span></div>
              <div className="flex justify-between"><span>Макро-цели (сессий)</span><span className="tabular-nums">{fmtInt(det.macro_sessions)} · {det.macro_rate_pct}%</span></div>
              <div className="flex justify-between text-text-tertiary"><span>Цель макро</span><span className="tabular-nums">{det.macro_target_pct}%</span></div>
            </>
          )}
          {node.key === 'retention' && (
            <>
              <div className="flex justify-between"><span>Посетителей за 14 дней</span><span className="tabular-nums">{fmtInt(det.visitors_14d)}</span></div>
              <div className="flex justify-between"><span>Вернулись (2+ дня)</span><span className="tabular-nums">{fmtInt(det.returned)}</span></div>
              {det.windows && ['d1', 'd7', 'd30'].map((w) => det.windows[w] && (
                <div key={w} className="flex justify-between">
                  <span>Возврат за {w.slice(1)} {w === 'd1' ? 'день' : 'дней'}</span>
                  <span className="tabular-nums">{det.windows[w].rate_pct}% <span className="text-text-tertiary">({fmtInt(det.windows[w].returned)}/{fmtInt(det.windows[w].cohort)})</span></span>
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
}

// Главная BI: North Star + 4 драйвера + операционный обзор ниже.
function MetricTreeTab({ d }) {
  const tree = d.metric_tree || {};
  const ns = tree.north_star || {};
  const milestone = ns.milestone || 10000;
  const nsColor = STATUS_COLOR[ns.status] || GOLD;
  const series = (ns.series || []).map((x) => ({ v: x.visits }));

  // Calendar-heatmap года: НАШИ сессии по дням за 365 дней (tree.calendar),
  // независимо от выбранного периода; палитра автоскейлится по максимуму.
  const calOption = useMemo(() => {
    const src = tree.calendar || ns.series || [];
    const calData = src.map((x) => [x.day, x.visits]);
    const calMax = Math.max(1, ...src.map((x) => x.visits));
    const year = calData.length ? calData[calData.length - 1][0].slice(0, 4) : String(new Date().getFullYear());
    return {
      tooltip: { formatter: (p) => `${p.value[0]}: ${Number(p.value[1]).toLocaleString('ru-RU')} сессий` },
      visualMap: {
        min: 0, max: calMax, orient: 'horizontal', left: 'center', bottom: 0,
        inRange: { color: ['#F4EFE3', GOLD, INK] }, textStyle: { fontSize: 10 },
      },
      calendar: {
        range: year, cellSize: ['auto', 14], left: 40, right: 10, top: 24,
        itemStyle: { borderWidth: 2, borderColor: '#fff', color: '#FAF8F2' },
        splitLine: { lineStyle: { color: 'rgba(26,26,46,0.15)' } },
        dayLabel: { fontSize: 9, nameMap: ['вс', 'пн', 'вт', 'ср', 'чт', 'пт', 'сб'] },
        monthLabel: { fontSize: 10, nameMap: ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'] },
        yearLabel: { show: false },
      },
      series: [{ type: 'heatmap', coordinateSystem: 'calendar', data: calData }],
    };
  }, [tree.calendar, ns.series]);

  return (
    <div className="space-y-5">
      <section className="rounded-2xl bg-surface border border-border-subtle p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="text-[13px] text-text-tertiary">{ns.label || 'Сессии в день'} · North Star · наш счётчик</div>
            <div className="flex items-baseline gap-3 mt-1">
              <span className="text-4xl font-bold tabular-nums text-text-primary">{fmtInt(Math.round(ns.value || 0))}</span>
              {ns.wow_pct != null && (
                <span className={`text-[13px] font-medium tabular-nums ${ns.wow_pct >= 0 ? 'text-positive' : 'text-negative'}`}>
                  {ns.wow_pct >= 0 ? '+' : ''}{ns.wow_pct}% к окну {ns.prev_label || 'ранее'}
                </span>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-2 mt-1.5 text-[12px] text-text-secondary">
              <span className="tabular-nums">{fmtInt(ns.sessions_total || 0)} сессий · {fmtInt(ns.visitors_total || 0)} посетителей за период</span>
              {ns.metrika_visits_total != null && (
                <span className="px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 text-[11px] tabular-nums"
                  title="Сверочный слой: визиты Яндекс.Метрики за тот же период (лаг до суток)">
                  по Метрике: {fmtInt(ns.metrika_visits_total)} визитов
                </span>
              )}
            </div>
            <div className="mt-3 max-w-md">
              <div className="flex justify-between text-[11px] text-text-tertiary mb-1">
                <span>до вехи {fmtInt(milestone)}</span>
                <span className="tabular-nums">{Math.min(Math.round((ns.value || 0) / milestone * 100), 100)}%</span>
              </div>
              <div className="h-2 rounded-full bg-obsidian overflow-hidden">
                <div className="h-full rounded-full" style={{ width: `${Math.min((ns.value || 0) / milestone * 100, 100)}%`, background: nsColor }} />
              </div>
              <div className="flex justify-between text-[10px] text-text-tertiary mt-1">
                {(ns.milestones || []).map((m) => (
                  <span key={m} className={m <= (ns.value || 0) ? 'text-champagne font-medium' : ''}>{fmtInt(m)}</span>
                ))}
              </div>
            </div>
          </div>
          <div className="w-full sm:w-72 h-20">
            {series.length > 1 && (
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={series} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
                  <Area type="monotone" dataKey="v" stroke={GOLD} fill={GOLD} fillOpacity={0.15} strokeWidth={1.6} dot={false} isAnimationActive={false} />
                </ComposedChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </section>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {(tree.drivers || []).map((n) => <DriverNode key={n.key} node={n} />)}
      </div>

      <Card title="Календарь трафика: каждый день года" icon={CalendarClock} source="own"
        insight="Ритм платформы одним взглядом: тёмные клетки — сильные дни (сессии нашего счётчика без ботов, палитра масштабируется по максимуму года). Провалы и всплески видны сразу — к каждому должен находиться источник (публикация, реклама, сезон)."
        hint="Каждая клетка — день (МСК), насыщенность — число сессий нашего счётчика. Читать: сезонность, провалы (инциденты) и всплески (публикации, реклама) видны сразу.">
        <EChart option={calOption} height={180} />
      </Card>

      <OverviewTab d={d} />
    </div>
  );
}

// Горизонтальная воронка со ступенями и конверсией между ними.
function FunnelSteps({ steps, color = GOLD }) {
  const rows = (steps || []).filter((s) => s.count != null);
  if (!rows.length || !rows[0].count) return <Empty />;
  const max = rows[0].count || 1;
  return (
    <div className="space-y-2">
      {rows.map((s, i) => {
        const prev = i > 0 ? rows[i - 1].count : null;
        const conv = prev ? Math.round(s.count / prev * 1000) / 10 : null;
        return (
          <div key={s.step}>
            <div className="flex justify-between text-[12px] mb-0.5">
              <span className="text-text-primary">{s.step}</span>
              <span className="text-text-secondary tabular-nums">
                {fmtInt(s.count)}{conv != null && <span className="text-text-tertiary"> · {conv}% от шага выше</span>}
              </span>
            </div>
            <div className="h-5 rounded-md bg-obsidian overflow-hidden">
              <div className="h-full rounded-md" style={{ width: `${Math.max(s.count / max * 100, 1.5)}%`, background: color, opacity: 1 - i * 0.16 }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

// Сверка конверсий двух счётчиков строка-к-строке (волна 2, п. 6):
// наши business-события против достижений соответствующих целей Метрики.
function GoalReconciliationCard({ d }) {
  const gr = d.goal_reconciliation || {};
  const rows = gr.rows || [];
  const pager = usePager(rows, 20);
  return (
    <Card title="Сверка конверсий: наши события и цели Метрики" icon={Target} source="both"
      hint="Каждая строка — конверсионное действие. «Событий / сессий» — наш счётчик: сколько раз действие совершено и в скольких сессиях. «Визитов с целью» — Метрика: в скольких визитах достигнута цель, замапленная на это событие. Единицы разные, поэтому сравнивать нужно порядок величин, а не точные числа. Прочерк — в Метрике нет цели под это событие."
      insight="Два независимых счётчика об одном и том же: если порядки величин совпадают — конверсия считается честно; расхождение в разы — сигнал (потерянная цель, боты, задержка данных Метрики за последний день).">
      {rows.length ? (
        <div className="overflow-x-auto">
          <table className="w-full text-[12.5px]">
            <thead>
              <tr className="text-left text-text-tertiary border-b border-border-subtle">
                <th className="py-1.5 pr-3 font-medium">Действие</th>
                <th className="py-1.5 pr-3 font-medium">Ярус</th>
                <th className="py-1.5 pr-3 font-medium text-right">Наши события</th>
                <th className="py-1.5 pr-3 font-medium text-right">Наши сессии</th>
                <th className="py-1.5 font-medium text-right">Визиты с целью (Метрика)</th>
              </tr>
            </thead>
            <tbody>
              {pager.slice.map((r) => (
                <tr key={r.event} className="border-b border-border-subtle/50 last:border-0">
                  <td className="py-1.5 pr-3">
                    <span className="text-text-primary">{eventLabel(r.event)}</span>
                    <span className="block text-text-tertiary font-mono text-[10.5px]">{r.event}</span>
                  </td>
                  <td className="py-1.5 pr-3">
                    <span className="inline-flex items-center gap-1.5 text-[11px] text-text-secondary">
                      <span className="w-2 h-2 rounded-full" style={{ background: TIER_COLOR[r.tier] || 'rgba(26,26,46,0.25)' }} />
                      {TIER_RU[r.tier] || r.tier}
                    </span>
                  </td>
                  <td className="py-1.5 pr-3 text-right tabular-nums font-medium text-text-primary">{fmtInt(r.our_events)}</td>
                  <td className="py-1.5 pr-3 text-right tabular-nums text-text-secondary">{fmtInt(r.our_sessions)}</td>
                  <td className="py-1.5 text-right tabular-nums text-text-secondary">
                    {r.metrika_visits == null
                      ? <span className="text-text-tertiary" title="В Метрике нет цели, замапленной на это событие">— нет цели</span>
                      : fmtInt(r.metrika_visits)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <Pager p={pager} />
          {(gr.metrika_only || []).length > 0 && (
            <div className="mt-3 pt-3 border-t border-dashed border-border-subtle text-[12px] text-text-secondary">
              <span className="font-medium">Только в Метрике (без нашего события): </span>
              {gr.metrika_only.map((g) => `${g.goal} — ${fmtInt(g.visits)}`).join(' · ')}
            </div>
          )}
          <p className="text-[11px] text-text-tertiary mt-2">
            Словарь целей Метрики: {fmtInt(gr.goals_dict_size)} целей, из них замаплено на наши события: {fmtInt(gr.mapped_events)}.
            Повизитные цели Метрика отдаёт за завершённые дни — за сегодня её колонка отстаёт.
          </p>
        </div>
      ) : <Empty note="Событий и целей за период нет." />}
    </Card>
  );
}

// Конверсия: собственная realtime-воронка + истинная воронка Метрики + события.
function ConversionTab({ d }) {
  const own = d.own_funnel || {};
  const mk = d.metrika_funnel || {};
  return (
    <div className="space-y-5">
      <div className="grid lg:grid-cols-2 gap-5">
        <Card title="Собственная воронка: сессия → вовлечён → цель" icon={Filter} source="own"
          hint="База — серверные сессии (разрыв активности 30 минут), боты и своя активность исключены. Вовлечён: активное время >15 с, скролл >50% или 2+ страницы. Цель — бизнес-события макро/микро-яруса нашей таксономии."
          insight="Серверные сессии нашего счётчика (правило 30 минут, боты исключены), реальное время. Вовлечён: активное чтение >15 с, скролл >50% или 2+ страницы.">
          <FunnelSteps steps={own.steps} />
          {own.bot_sessions > 0 && (
            <p className="text-[11px] text-text-tertiary mt-3">Отфильтровано бот-сессий: {fmtInt(own.bot_sessions)}</p>
          )}
        </Card>
        <Card title="Истинная конверсия Метрики: только бизнес-цели" icon={Target} source="metrika"
          hint="Повизитные данные Метрики за период: визит засчитан конверсионным, только если среди достигнутых целей есть макро- или микро-цель из нашего словаря. Данные Метрики приходят с лагом до суток."
          insight="«Достиг цели» = только макро- и микро-цели по словарю целей (регистрация, скачивание, сравнение) — скролл и технические события больше не завышают конверсию.">
          <div className="grid grid-cols-3 gap-3 mb-4">
            <Kpi label="Визиты" value={fmtInt(mk.visits)} />
            <Kpi label="С любой целью" value={fmtInt(mk.visits_any_goal)} color={BLUE} />
            <Kpi label="С бизнес-целью" value={fmtInt(mk.visits_business_goal)} sub={`${mk.conversion_pct ?? 0}% конверсия`} color={GREEN} />
          </div>
          {(mk.by_goal || []).length ? (
            <ul className="space-y-1.5">
              {(mk.by_goal || []).slice(0, 10).map((g) => (
                <li key={g.goal} className="flex items-center gap-2 text-[12.5px]">
                  <span className="w-2 h-2 rounded-full shrink-0" style={{ background: TIER_COLOR[g.tier] || 'rgba(26,26,46,0.25)' }} />
                  <span className="flex-1 min-w-0 truncate text-text-primary" title={g.goal}>{eventLabel(g.goal)}</span>
                  {g.tier && <span className="text-[10px] text-text-tertiary shrink-0">{TIER_RU[g.tier] || g.tier}</span>}
                  <span className="text-text-secondary tabular-nums shrink-0">{fmtInt(g.visits)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <Empty note={mk.today_live
              ? 'Сводные визиты за сегодня — живые (Reporting API); повизитные цели Метрика отдаёт за завершённый день, появятся завтра после утреннего синка.'
              : mk.goals_dict_size === 0 ? 'Словарь целей Метрики синхронизируется ежедневно — появится после первого прогона.' : undefined} />
          )}
        </Card>
      </div>
      <GoalReconciliationCard d={d} />
      <FunnelTab d={d} />
      <EventsTab d={d} />
    </div>
  );
}

// Поведение: sankey-навигация + sunburst контента + контент/навигация/блоки.
function BehaviorTab({ d }) {
  const sankeyOption = useMemo(() => {
    const transitions = d.navigation?.top_transitions || [];
    if (!transitions.length) return null;
    // Читаемость (этап 4б): страницы группируются в разделы сайта, потоки
    // агрегируются, берётся топ-15 с порогом минимального объёма — вместо
    // «спагетти» из десятков одиночных переходов.
    const flows = new Map();
    for (const t of transitions) {
      const from = pageSectionRu(t.from);
      const to = pageSectionRu(t.to);
      const key = `${from}→${to}`;
      flows.set(key, (flows.get(key) || 0) + t.count);
    }
    const top = [...flows.entries()]
      .map(([key, count]) => { const [from, to] = key.split('→'); return { from, to, count }; })
      .filter((f) => f.count >= 2)
      .sort((a, b) => b.count - a.count)
      .slice(0, 15);
    if (!top.length) return null;
    // Двудольный граф «откуда → куда»: узлы источника и назначения разводятся
    // в разные множества — иначе циклы (A→B, B→A) ломают sankey.
    const nodes = new Map();
    const links = top.map((t) => {
      const s = `Из: ${t.from}`;
      const e = `В: ${t.to}`;
      nodes.set(s, { name: s, itemStyle: { color: GOLD } });
      nodes.set(e, { name: e, itemStyle: { color: INK } });
      return { source: s, target: e, value: t.count };
    });
    return {
      tooltip: { trigger: 'item', textStyle: { fontSize: 11 } },
      series: [{
        type: 'sankey', left: 8, right: 150, nodeWidth: 10, nodeGap: 8,
        data: [...nodes.values()], links,
        label: { fontSize: 11, formatter: (p) => clip(p.name.replace(/^(Из|В): /, ''), 26) },
        lineStyle: { color: 'gradient', opacity: 0.3, curveness: 0.55 },
        emphasis: { focus: 'adjacency' },
      }],
    };
  }, [d.navigation]);

  const sunburstOption = useMemo(() => {
    const sections = d.content_structure?.sections || [];
    if (!sections.length) return null;
    const total = sections.reduce((s, x) => s + (x.views || 0), 0) || 1;
    return {
      tooltip: { formatter: (p) => `${p.name}: ${Number(p.value).toLocaleString('ru-RU')} просмотров`, textStyle: { fontSize: 11 } },
      series: [{
        type: 'sunburst', radius: ['18%', '92%'],
        data: sections.slice(0, 10).map((s, i) => ({
          name: s.name || s.section, value: s.views,
          itemStyle: { color: PALETTE[i % PALETTE.length] },
          children: (s.top_pages || []).slice(0, 5).map((p) => ({
            name: clip(p.page, 26), value: p.views,
          })),
        })),
        // Подписи только у секторов заметнее 3% — микрошрифт на тонких
        // дольках нечитаем и превращает диаграмму в шум (этап 4б).
        label: {
          fontSize: 10, minAngle: 11,
          formatter: (p) => (p.value / total >= 0.03 ? clip(p.name, 16) : ''),
        },
        levels: [{}, { r0: '18%', r: '55%' }, { r0: '55%', r: '92%', label: { rotate: 'tangential' } }],
      }],
    };
  }, [d.content_structure]);

  return (
    <div className="space-y-5">
      <div className="grid lg:grid-cols-2 gap-5">
        <Card title="Потоки навигации: откуда и куда ходят" icon={Route} source="own"
          insight="Переходы между разделами сайта внутри сессии: толщина — число переходов (топ-15 потоков, единичные скрыты). Видно магистральные маршруты и куда «стекает» аудитория; постраничная детализация — в матрице переходов ниже."
        hint="Диаграмма Санкей по переходам внутри сессий нашего счётчика: слева — раздел-источник, справа — назначение, толщина — объём. Читать: главные маршруты аудитории; тонкие обрывы — недоиспользованные связки.">
          {sankeyOption ? <EChart option={sankeyOption} height={360} /> : <Empty />}
        </Card>
        <Card title="Структура потребления контента" icon={LayoutGrid} source="own"
          insight="Sunburst: внутреннее кольцо — разделы, внешнее — конкретные страницы внутри. Клик по сектору — детализация."
        hint="Sunburst по просмотрам нашего счётчика: внутреннее кольцо — разделы, внешнее — страницы внутри. Читать: соотношение колец показывает глубину каждого раздела.">
          {sunburstOption ? <EChart option={sunburstOption} height={360} /> : <Empty />}
        </Card>
      </div>

      <Card title="Внимание по блокам страниц" icon={MousePointerClick} source="own"
        insight="Сколько раз блок реально увидели (IntersectionObserver ≥50% площади ≥1 с) и сколько секунд он был на экране. Блоки с высоким вниманием — расширять, с нулевым — поднимать выше или переделывать."
        hint="Видимость блоков страницы (IntersectionObserver): сколько раз блок попал в экран и как долго удерживал внимание. Читать: блоки внизу списка аудитория не доскролливает.">
        {(d.blocks?.blocks || []).length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-[12.5px]">
              <thead>
                <tr className="text-left text-text-tertiary border-b border-border-subtle">
                  <th className="py-1.5 pr-3 font-medium">Раздел</th>
                  <th className="py-1.5 pr-3 font-medium">Блок</th>
                  <th className="py-1.5 pr-3 font-medium text-right">Показов</th>
                  <th className="py-1.5 font-medium text-right">Среднее время видимости</th>
                </tr>
              </thead>
              <tbody>
                {(d.blocks.blocks || []).slice(0, 25).map((b, i) => (
                  <tr key={i} className="border-b border-border-subtle/50">
                    <td className="py-1.5 pr-3 text-text-secondary">{b.section}</td>
                    <td className="py-1.5 pr-3 text-text-primary" title={b.block}>{blockLabel(b.block)}</td>
                    <td className="py-1.5 pr-3 text-right tabular-nums">{fmtInt(b.views)}</td>
                    <td className="py-1.5 text-right tabular-nums">{b.avg_visible_sec} с</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <Empty note="Блочная разметка собирается — данные появятся после деплоя фронта." />}
      </Card>

      <PagesTab d={d} />
      <NavigationTab d={d} />
    </div>
  );
}

// Досье «Люди»: посетители со скорингом ценности. Вместо hex-хэша — номер
// «Посетитель #N» (техноним в title); пустые по всему списку колонки скрыты.
function PeopleCard({ d }) {
  const people = d.people?.people || [];
  const pager = usePager(people, 30);
  const hasPortrait = people.some((p) => p.device || p.browser || p.city || p.channel);
  const hasInterests = people.some((p) => (p.interests || []).length > 0);
  return (
    <Card title="Люди: досье посетителей со скорингом" icon={Users} source="own"
      hint="Скоринг — сумма весов действий посетителя за окно; вес каждого типа события учитывается максимум 3 раза, чтобы серийные авто-события (скролл, просмотры) не перевешивали реальную ценность (регистрацию, выгрузку). Показаны посетители с двумя и более сессиями или хотя бы одной целью."
      insight="Каждая строка — человек (постоянный идентификатор, кросс-девайс через аккаунт). Скоринг — сумма весов его действий: регистрация 100, скачивание 25, просмотр 1. Сверху — самые ценные.">
      {people.length ? (
        <div className="overflow-x-auto">
          <table className="w-full text-[12px]">
            <thead>
              <tr className="text-left text-text-tertiary border-b border-border-subtle">
                <th className="py-1.5 pr-2 font-medium">Посетитель</th>
                <th className="py-1.5 pr-2 font-medium text-right">Скоринг</th>
                <th className="py-1.5 pr-2 font-medium text-right">Сессий</th>
                <th className="py-1.5 pr-2 font-medium text-right">Страниц</th>
                <th className="py-1.5 pr-2 font-medium text-right">Активных минут</th>
                <th className="py-1.5 pr-2 font-medium text-right">Целей (микро/макро)</th>
                {hasPortrait && <th className="py-1.5 pr-2 font-medium">Портрет</th>}
                {hasInterests && <th className="py-1.5 font-medium">Интересы</th>}
              </tr>
            </thead>
            <tbody>
              {pager.slice.map((p, i) => (
                <tr key={p.visitor} className="border-b border-border-subtle/50">
                  <td className="py-1.5 pr-2">
                    <span className="text-text-primary" title={`идентификатор ${p.visitor}`}>Посетитель #{pager.cur * pager.pageSize + i + 1}</span>
                    {p.user_id && <span className="ml-1.5 text-[9.5px] px-1.5 py-0.5 rounded-full bg-green-50 text-green-700 font-medium">аккаунт</span>}
                  </td>
                  <td className="py-1.5 pr-2 text-right tabular-nums font-semibold text-champagne">{fmtInt(p.score)}</td>
                  <td className="py-1.5 pr-2 text-right tabular-nums">{p.sessions}</td>
                  <td className="py-1.5 pr-2 text-right tabular-nums">{p.pageviews}</td>
                  <td className="py-1.5 pr-2 text-right tabular-nums">{p.active_min}</td>
                  <td className="py-1.5 pr-2 text-right tabular-nums">{p.micro_goals}/{p.macro_goals}</td>
                  {hasPortrait && (
                    <td className="py-1.5 pr-2 text-text-secondary">
                      {[p.device && deviceLabel(p.device), p.browser, p.city && cityLabel(p.city), p.channel && channelLabel(p.channel)].filter(Boolean).join(' · ') || '—'}
                    </td>
                  )}
                  {hasInterests && <td className="py-1.5 text-text-secondary">{(p.interests || []).join(', ') || '—'}</td>}
                </tr>
              ))}
            </tbody>
          </table>
          <Pager p={pager} />
        </div>
      ) : <Empty note="Досье строится на серверных сессиях — появится после первого 15-минутного цикла." />}
    </Card>
  );
}

// Аудитория: портреты + гео собственного слоя + досье.
function AudienceFullTab({ d }) {
  const geo = d.geo || {};
  return (
    <div className="space-y-5">
      <AudienceTab d={d} />
      <div className="grid lg:grid-cols-3 gap-5">
        <Card title="География: страны" icon={Globe2} source="own" insight="Наше гео по IP (база обновляется ежемесячно), сам адрес не хранится."
        hint="Страна по IP на нашем сервере (адрес не сохраняется). Читать: доля не-России задаёт требования к скорости из-за рубежа.">
          <HBars data={dictToBars(geo.countries, 8)} color={INK} />
        </Card>
        <Card title="Регионы" icon={Globe2} source="own"
        hint="Субъект РФ по IP-адресу сессии (наш счётчик, база DB-IP).">
          <HBars data={dictToBars(geo.regions, 10, geoRegionLabel)} color={BLUE} />
        </Card>
        <Card title="Города" icon={Globe2} source="own"
        hint="Город по IP-адресу сессии (наш счётчик). Округа в скобках схлопнуты до города.">
          <HBars data={dictToBars(geo.cities, 10, cityLabel)} color={PURPLE} />
        </Card>
      </div>
      <PeopleCard d={d} />
    </div>
  );
}

const QUADRANT_COLOR = {
  'Продвигать': GREEN, 'Тиражировать': BLUE, 'Чинить': '#D97706', 'Переработать': RED,
};

// «Что менять»: квадранты, adoption, копируемое, гипотезы.
function ProductLoopTab({ d, onOpenSlices }) {
  const q = d.page_quadrants || {};
  // Лог-шкала по X требует значений > 0; подписи — только у заметных точек
  // (топ-8 по просмотрам), иначе куча текста слипается у нуля (этап 4б).
  const items = (q.sections || []).map((s) => ({ ...s, x: Math.max(s.views, 1), y: s.avg_active_sec }));
  const labelled = new Set(
    [...items].sort((a, b) => b.x - a.x).slice(0, 8).map((s) => s.section),
  );
  const quadrantItems = items.map((s) => ({ ...s, label: labelled.has(s.section) ? s.section : '' }));
  const fa = d.feature_adoption || {};
  const features = (fa.features || []).filter((f) => f.tier !== 'technical');

  return (
    <div className="space-y-5">
      <Card title="Квадранты разделов: трафик × вовлечение" icon={Target} source="own"
        insight="Каждая точка — раздел сайта. Правый верх (много трафика, глубокое чтение) — продвигать; левый верх — тиражировать паттерн; правый низ — чинить вовлечение; левый низ — переработать или понизить приоритет."
        hint="Каждая точка — раздел сайта: по горизонтали просмотры (лог-шкала), по вертикали активное чтение в секундах; пунктир — медианы. Источник — наш счётчик. Читать по квадрантам: продвигать / тиражировать / чинить / переработать.">
        {items.length ? (
          <ResponsiveContainer width="100%" height={340}>
            <ScatterChart margin={{ top: 10, right: 24, bottom: 20, left: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
              <XAxis type="number" dataKey="x" name="Просмотры" scale="log" domain={[1, 'auto']}
                tick={{ fontSize: 11, fill: 'rgba(26,26,46,0.5)' }}
                label={{ value: 'просмотры (лог-шкала)', position: 'insideBottom', offset: -8, fontSize: 11, fill: 'rgba(26,26,46,0.5)' }} />
              <YAxis type="number" dataKey="y" name="Активные секунды" tick={{ fontSize: 11, fill: 'rgba(26,26,46,0.5)' }} width={40}
                label={{ value: 'активное чтение, с', angle: -90, position: 'insideLeft', fontSize: 11, fill: 'rgba(26,26,46,0.5)' }} />
              <ReferenceLine x={Math.max(q.median_views, 1)} stroke="rgba(26,26,46,0.25)" strokeDasharray="4 3" />
              <ReferenceLine y={q.median_engagement} stroke="rgba(26,26,46,0.25)" strokeDasharray="4 3" />
              <Tooltip {...TT_STYLE} content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const p = payload[0].payload;
                return (
                  <div style={TT_STYLE.contentStyle}>
                    <div style={{ fontWeight: 600 }}>{p.section} — {p.quadrant}</div>
                    <div>Просмотры: {fmtInt(p.views)} · активное чтение: {p.avg_active_sec} с</div>
                    <div>Dead-клики: {fmtInt(p.dead_clicks)}</div>
                  </div>
                );
              }} />
              <Scatter data={quadrantItems}>
                {quadrantItems.map((p, i) => <Cell key={i} fill={QUADRANT_COLOR[p.quadrant] || GOLD} />)}
                <LabelList dataKey="label" position="top" style={{ fontSize: 10, fill: 'rgba(26,26,46,0.6)' }} />
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>
        ) : <Empty note="Квадранты строятся на дневных агрегатах страниц — появятся после первого цикла." />}
        <div className="flex flex-wrap gap-3 mt-2">
          {Object.entries(QUADRANT_COLOR).map(([name, color]) => (
            <span key={name} className="flex items-center gap-1.5 text-[11px] text-text-secondary">
              <span className="w-2.5 h-2.5 rounded-full" style={{ background: color }} />{name}
            </span>
          ))}
        </div>
      </Card>

      <div className="grid lg:grid-cols-2 gap-5">
        <Card title="Adoption фич: что реально используют" icon={Wrench} source="own"
          insight="Бизнес-события по ценности: цвет — уровень цели (зелёный — макро, синий — микро, золотой — вовлечение). Фичи без использования — кандидаты на доработку видимости или удаление."
        hint="Число срабатываний каждого бизнес-события за период, цвет — ярус ценности (макро/микро/вовлечение). Читать: фичи с нулём — либо не нужны, либо не видны; проверить видимость перед удалением.">
          {features.length ? (
            <ul className="space-y-1.5">
              {features.slice(0, 18).map((f) => (
                <li key={f.event} className="flex items-center gap-2 text-[12.5px]">
                  <span className="w-2 h-2 rounded-full shrink-0" style={{ background: TIER_COLOR[f.tier] || 'rgba(26,26,46,0.25)' }} />
                  <span className="flex-1 min-w-0 truncate text-text-primary" title={f.event}>{eventLabel(f.event)}</span>
                  <span className="text-[10px] text-text-tertiary shrink-0">{TIER_RU[f.tier] || f.tier}</span>
                  <span className="text-text-secondary tabular-nums shrink-0">{fmtInt(f.count)}</span>
                </li>
              ))}
            </ul>
          ) : <Empty note="Появится после первого дневного агрегата целей." />}
        </Card>
        <Card title="Что уносят руками (copy)" icon={MousePointerClick} source="own"
          insight="Текст, который копируют со страниц, — прямой сигнал ценности: кандидаты на кнопку «поделиться», embed-виджет или экспорт."
        hint="Событие copy нашего счётчика: какой текст копируют со страниц. Читать: топ копируемого — прямой кандидат на кнопку «поделиться», экспорт или embed-виджет.">
          {(fa.top_copied || []).length ? (
            <ul className="space-y-1.5">
              {fa.top_copied.map((c, i) => (
                <li key={i} className="flex items-center gap-2 text-[12.5px]">
                  <span className="flex-1 min-w-0 truncate text-text-primary" title={c.text}>{clip(c.text, 60)}</span>
                  <span className="text-text-secondary tabular-nums shrink-0">{fmtInt(c.count)}</span>
                </li>
              ))}
            </ul>
          ) : <Empty />}
        </Card>
      </div>

      <Card title="A/B-эксперименты: конверсия по вариантам" icon={SlidersHorizontal} source="own"
        insight="Автоанализ experiment_exposure: охват варианта и доля посетителей, дошедших до микро/макро-цели. Карточки появляются с первым запущенным экспериментом."
        hint="Автоанализ событий experiment_exposure: охват каждого варианта и доля посетителей, дошедших до micro/macro-цели в окне эксперимента. Появляется с первым запущенным A/B.">
        {(d.experiments?.experiments || []).length ? (
          <div className="space-y-4">
            {d.experiments.experiments.map((exp) => (
              <div key={exp.experiment}>
                <div className="text-[12.5px] font-semibold text-text-primary mb-1.5">{exp.experiment}</div>
                <ul className="space-y-1">
                  {exp.variants.map((v) => (
                    <li key={v.variant} className="flex items-center gap-2 text-[12.5px]">
                      <span className="w-16 shrink-0 text-text-secondary">{v.variant}</span>
                      <div className="flex-1 h-2 rounded-full bg-black/5 overflow-hidden">
                        <div className="h-full rounded-full" style={{ width: `${Math.min(v.conversion_pct, 100)}%`, background: GOLD }} />
                      </div>
                      <span className="tabular-nums text-text-primary shrink-0">{v.conversion_pct}%</span>
                      <span className="text-[10px] text-text-tertiary tabular-nums shrink-0">{fmtInt(v.visitors)} чел.</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        ) : <Empty note={d.experiments?.note || 'Экспозиций нет — каркас готов к первому A/B.'} />}
      </Card>

      <HypothesesTab d={d} onOpenSlices={onOpenSlices} />
    </div>
  );
}

// «Срезы»: произвольный вопрос к OLAP-слою (метрика × измерения × период).
function SlicesTab() {
  const [metric, setMetric] = useState('sessions');
  const [dim1, setDim1] = useState('channel');
  const [dim2, setDim2] = useState('');
  const [days, setDays] = useState(30);

  const { data: meta } = useQuery({
    queryKey: ['bi-slices-meta'],
    queryFn: () => api.get('/admin/bi/slices/meta').then((r) => r.data),
    staleTime: 10 * 60 * 1000,
    retry: 1,
  });

  const dims = [dim1, dim2].filter(Boolean).join(',');
  const { data: slice, isFetching, isError } = useQuery({
    queryKey: ['bi-slice', metric, dims, days],
    queryFn: () => api.get(`/admin/bi/slices?metric=${metric}&dims=${dims}&days=${days}`).then((r) => r.data),
    enabled: Boolean(meta?.available && metric),
    retry: 0,
  });

  const tablePager = usePager(slice?.rows || [], 50);
  if (meta && !meta.available) {
    return <Empty note={`Слой «Срезы» недоступен: ${meta.reason || 'ClickHouse выключен'}. Включается флагом на сервере.`} />;
  }
  const metricNames = Object.keys(meta?.metrics || {});
  const metricTable = meta?.metrics?.[metric];
  const dimOptions = metricTable ? (meta?.dimensions?.[metricTable] || []) : [];
  const rows = slice?.rows || [];
  // Значения измерений — через словарь ярлыков (канал/устройство/поисковик).
  const dimValue = (dim, v) => (
    dim === 'channel' || dim === 'traffic_source' ? channelLabel(v)
      : dim === 'device' ? deviceLabel(v)
      : dim === 'search_engine' ? engineLabel(v)
      : String(v ?? '') || '(не определён)'
  );
  const chartRows = rows.slice(0, 14).map((r) => ({
    name: [dim1 && dimValue(dim1, r[dim1]), dim2 && dimValue(dim2, r[dim2])].filter(Boolean).join(' · ') || '—',
    value: r.value,
  }));

  return (
    <div className="space-y-5">
      <Card title="Конструктор срезов" icon={SlidersHorizontal} source="own"
        insight={`Любая метрика × до двух измерений × период — считает колоночный OLAP-слой за миллисекунды. ${meta?.sync_age_minutes != null ? `Свежесть данных: синк ${meta.sync_age_minutes} мин назад.` : ''}`}
        hint="Произвольный вопрос к колоночному OLAP-слою (ClickHouse): метрика × до двух измерений × период. Основа — те же сессии и события, что и в остальных вкладках. Читать: инструмент проверки гипотез без выгрузок.">
        <div className="flex flex-wrap gap-3 mb-4">
          <label className="text-[12px] text-text-secondary flex items-center gap-2">
            Метрика
            <select value={metric} onChange={(e) => { setMetric(e.target.value); setDim1(''); setDim2(''); }}
              className="px-2.5 py-1.5 rounded-lg bg-obsidian border border-border-subtle text-[12.5px] text-text-primary">
              {metricNames.map((m) => <option key={m} value={m}>{sliceMetricLabel(m)}</option>)}
            </select>
          </label>
          <label className="text-[12px] text-text-secondary flex items-center gap-2">
            Измерение 1
            <select value={dim1} onChange={(e) => setDim1(e.target.value)}
              className="px-2.5 py-1.5 rounded-lg bg-obsidian border border-border-subtle text-[12.5px] text-text-primary">
              <option value="">—</option>
              {dimOptions.map((x) => <option key={x} value={x}>{sliceDimLabel(x)}</option>)}
            </select>
          </label>
          <label className="text-[12px] text-text-secondary flex items-center gap-2">
            Измерение 2
            <select value={dim2} onChange={(e) => setDim2(e.target.value)}
              className="px-2.5 py-1.5 rounded-lg bg-obsidian border border-border-subtle text-[12.5px] text-text-primary">
              <option value="">—</option>
              {dimOptions.filter((x) => x !== dim1).map((x) => <option key={x} value={x}>{sliceDimLabel(x)}</option>)}
            </select>
          </label>
          <label className="text-[12px] text-text-secondary flex items-center gap-2">
            Дней
            <select value={days} onChange={(e) => setDays(Number(e.target.value))}
              className="px-2.5 py-1.5 rounded-lg bg-obsidian border border-border-subtle text-[12.5px] text-text-primary">
              {[7, 30, 90, 365].map((x) => <option key={x} value={x}>{x}</option>)}
            </select>
          </label>
        </div>
        {isFetching && <p className="text-[13px] text-text-tertiary py-6 text-center">Считаем срез…</p>}
        {isError && <Empty note="Слой недоступен или срез невалиден — синк догонит после подъёма ClickHouse." />}
        {!isFetching && !isError && rows.length > 0 && (
          <>
            {chartRows.length > 1 && <HBars data={chartRows} labelWidth={200} />}
            <div className="overflow-x-auto mt-4">
              <table className="w-full text-[12px]">
                <thead>
                  <tr className="text-left text-text-tertiary border-b border-border-subtle">
                    {Object.keys(rows[0]).map((k) => (
                      <th key={k} className="py-1.5 pr-3 font-medium">
                        {k === 'value' ? sliceMetricLabel(metric) : sliceDimLabel(k)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {tablePager.slice.map((r, i) => (
                    <tr key={i} className="border-b border-border-subtle/50">
                      {Object.entries(r).map(([k, v], j) => (
                        <td key={j} className="py-1 pr-3 tabular-nums text-text-secondary">
                          {typeof v === 'number' ? fmtInt(v)
                            : k === 'channel' || k === 'traffic_source' ? channelLabel(v)
                            : k === 'device' ? deviceLabel(v)
                            : k === 'search_engine' ? engineLabel(v)
                            : String(v ?? '') || '(не определён)'}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              <Pager p={tablePager} />
            </div>
          </>
        )}
        {!isFetching && !isError && rows.length === 0 && slice && <Empty />}
      </Card>
    </div>
  );
}

// «Надёжность»: vitals + ошибки + полнота сбора + датасет.
function ReliabilityTab({ d }) {
  const r = d.reliability || {};
  const cq = d.collection_quality || {};
  const apiPager = usePager(r.api_slowest || [], 15);
  const vitals = r.vitals_p75 || {};
  const VITAL_BUDGET = { LCP: 2500, INP: 200, CLS: 0.1, FCP: 1800, TTFB: 800 };
  const vitalStatus = (m, v) => {
    const b = VITAL_BUDGET[m];
    if (b == null || v == null) return 'rgba(26,26,46,0.4)';
    return v <= b ? GREEN : v <= b * 1.6 ? '#D97706' : RED;
  };

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {['LCP', 'INP', 'CLS', 'FCP', 'TTFB'].map((m) => (
          <div key={m} className="rounded-xl bg-surface border border-border-subtle px-4 py-3">
            <div className="text-[12px] text-text-tertiary">{m} · p75</div>
            <div className="text-xl font-bold tabular-nums" style={{ color: vitalStatus(m, vitals[m]) }}>
              {vitals[m] != null ? (m === 'CLS' ? vitals[m] : `${fmtInt(Math.round(vitals[m]))} мс`) : '—'}
            </div>
            <div className="text-[10.5px] text-text-tertiary">{r.vitals_samples?.[m] ? `${fmtInt(r.vitals_samples[m])} замеров` : 'нет замеров'}</div>
          </div>
        ))}
      </div>

      <div className="grid lg:grid-cols-2 gap-5">
        <Card title="Ошибки JavaScript" icon={AlertTriangle} source="own" window={r.period}
          insight={`Всего за окно: ${fmtInt(r.js_errors_total || 0)}. Свои ошибки — детально сверху (привязаны к версии сборки, регрессия видна по деплою); сторонние скрипты (счётчики, реклама) схлопнуты до домена.`}
        hint="Ошибки фронтенда из потока поведения: свой код — детально (с версией сборки), сторонние скрипты — схлопнуты до домена. Читать: рост своих ошибок после деплоя — регрессия, откатывать.">
          {(r.js_errors_own || []).length || (r.js_errors_third_party || []).length ? (
            <div className="space-y-3">
              {(r.js_errors_own || []).length > 0 && (
                <div>
                  <div className="text-[11px] font-medium text-negative mb-1.5">Наш код</div>
                  <ul className="space-y-1.5">
                    {r.js_errors_own.map((e, i) => (
                      <li key={i} className="flex items-start gap-2 text-[12px]">
                        <span className="text-negative font-semibold tabular-nums shrink-0">{fmtInt(e.count)}×</span>
                        <span className="min-w-0 text-text-secondary font-mono text-[11px] break-all">{e.error}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {(r.js_errors_own || []).length === 0 && <p className="text-[12px] text-positive">В нашем коде ошибок за окно нет.</p>}
              {(r.js_errors_third_party || []).length > 0 && (
                <div className="pt-2 border-t border-border-subtle/60">
                  <div className="text-[11px] font-medium text-text-tertiary mb-1.5">Сторонние скрипты</div>
                  <ul className="space-y-1">
                    {r.js_errors_third_party.map((e, i) => (
                      <li key={i} className="flex items-center gap-2 text-[12px] text-text-tertiary">
                        <span className="tabular-nums shrink-0">{fmtInt(e.count)}×</span>
                        <span className="font-mono text-[11px] truncate">{e.domain}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ) : <Empty note="Ошибок за окно нет — хороший знак." />}
        </Card>
        <Card title="Латентность API глазами клиента" icon={Activity} source="own"
          insight={`p75 по всем вызовам: ${r.api_p75_ms != null ? `${fmtInt(Math.round(r.api_p75_ms))} мс` : '—'}. Сэмпл 1 из 5 вызовов; отсортировано по p75.`}
        hint="Замеры времени ответа API из браузеров реальных посетителей (сэмпл 1 из 5 вызовов), p50/p75/max по endpoint'ам. Читать: p75 выше секунды — заметное пользователю ожидание.">
          {(r.api_slowest || []).length ? (
            <div className="overflow-x-auto">
              <table className="w-full text-[12px]">
                <thead>
                  <tr className="text-left text-text-tertiary border-b border-border-subtle">
                    <th className="py-1.5 pr-3 font-medium">Endpoint</th>
                    <th className="py-1.5 pr-3 font-medium text-right">p50</th>
                    <th className="py-1.5 pr-3 font-medium text-right">p75</th>
                    <th className="py-1.5 pr-3 font-medium text-right">max</th>
                    <th className="py-1.5 font-medium text-right">Вызовов</th>
                  </tr>
                </thead>
                <tbody>
                  {apiPager.slice.map((a) => (
                    <tr key={a.endpoint} className="border-b border-border-subtle/50 last:border-0">
                      <td className="py-1.5 pr-3 font-mono text-[11px] text-text-secondary break-all">{a.endpoint}</td>
                      <td className="py-1.5 pr-3 text-right tabular-nums">{a.p50_ms != null ? `${fmtInt(Math.round(a.p50_ms))} мс` : '—'}</td>
                      <td className="py-1.5 pr-3 text-right tabular-nums font-medium" style={{ color: (a.p75_ms || 0) > 1000 ? RED : (a.p75_ms || 0) > 400 ? '#D97706' : 'inherit' }}>
                        {a.p75_ms != null ? `${fmtInt(Math.round(a.p75_ms))} мс` : '—'}
                      </td>
                      <td className="py-1.5 pr-3 text-right tabular-nums text-text-tertiary">{a.max_ms != null ? `${fmtInt(Math.round(a.max_ms))} мс` : '—'}</td>
                      <td className="py-1.5 text-right tabular-nums text-text-tertiary">{fmtInt(a.calls)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <Pager p={apiPager} />
            </div>
          ) : <Empty />}
        </Card>
      </div>

      <Card title="Полнота сбора: мета-мониторинг качества данных" icon={ShieldCheck} source="own" window={cq.period}
        insight="Насколько полны наши собственные данные: доля сессий с постоянным идентификатором, гео, каналом и мостом к Метрике. Тишина потока при живом трафике — сигнал сломанного сбора (алерт в Telegram)."
        hint="Здоровье самого счётчика: доля сессий с постоянным идентификатором, гео, каналом, мостом к Метрике. Читать: падение любой доли — сломан сбор, а не поведение аудитории.">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <Kpi label="Сессий за окно" value={fmtInt(cq.own_sessions)} />
          <Kpi label="С visitor_id" value={fmtPct(cq.visitor_id_share_pct)} color={cq.visitor_id_share_pct >= 90 ? GREEN : '#D97706'} />
          <Kpi label="С гео" value={fmtPct(cq.geo_share_pct)} color={cq.geo_share_pct >= 80 ? GREEN : '#D97706'} />
          <Kpi label="С каналом" value={fmtPct(cq.channel_share_pct)} color={cq.channel_share_pct >= 90 ? GREEN : '#D97706'} />
          <Kpi label="Мост к Метрике" value={fmtPct(cq.ym_bridge_share_pct)} sub="доля сессий с _ym_uid" color={BLUE} />
          <Kpi label="Доля ботов" value={fmtPct(cq.bot_share_pct)} color={INK} />
          <Kpi label="SSR-просмотры" value={fmtInt(cq.ssr_pageviews)} sub="standalone-сбор жив" color={PURPLE} />
          <Kpi label="Тишина потока" value={cq.stream_silence_minutes != null ? `${cq.stream_silence_minutes} мин` : '—'}
            sub={`лаг Метрики ${r.metrika_lag_hours != null ? `${r.metrika_lag_hours} ч` : '—'}`}
            color={(cq.stream_silence_minutes ?? 0) > 30 ? RED : GREEN} />
        </div>
      </Card>

      <BotnessCard d={d} />

      <DatasetTab d={d} />
    </div>
  );
}

// Витрина роботности: сколько отсеял антибот и калибровка к Метрике (±15%).
function BotnessCard({ d }) {
  const b = d.botness || {};
  const days = b.days || [];
  const inCorridor = (r) => r != null && Math.abs(r - 100) <= 15;
  return (
    <Card title="Роботность: антибот-скоринг сессий" icon={ShieldCheck} source="own" window={b.period}
      hint="Каждая сессия получает балл по эвристикам: webdriver-флаг, отсутствие движений мыши и касаний при одном просмотре, синтетические клики, известные боты по подписи браузера, аномальная частота сессий с одного посетителя. Сумма выше порога — сессия помечается ботом."
      insight={`Порог bot_score ≥ ${b.threshold ?? 60} — сессия исключается из всех витрин. ${b.note || ''}`}>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-4">
        <Kpi label="Сессий за окно" value={fmtInt(b.sessions)} />
        <Kpi label="Отсеяно ботов" value={fmtInt(b.bots)} sub={b.bot_share_pct != null ? `${b.bot_share_pct}% потока` : ''} color={INK} />
        <Kpi label="Люди" value={fmtInt((b.sessions || 0) - (b.bots || 0))} color={GREEN} />
      </div>
      {days.length ? (
        <div className="overflow-x-auto">
          <table className="w-full text-[12px]">
            <thead>
              <tr className="text-text-tertiary text-left">
                <th className="py-1 pr-3 font-medium">День (МСК)</th>
                <th className="py-1 pr-3 font-medium text-right">Люди</th>
                <th className="py-1 pr-3 font-medium text-right">Боты</th>
                <th className="py-1 pr-3 font-medium text-right">Метрика</th>
                <th className="py-1 font-medium text-right">Наши / Метрика</th>
              </tr>
            </thead>
            <tbody>
              {days.map((r) => (
                <tr key={r.day} className="border-t border-border-subtle/60">
                  <td className="py-1 pr-3 text-text-secondary">{r.day}</td>
                  <td className="py-1 pr-3 text-right tabular-nums">{fmtInt(r.humans)}</td>
                  <td className="py-1 pr-3 text-right tabular-nums text-text-tertiary">{fmtInt(r.bots)}</td>
                  <td className="py-1 pr-3 text-right tabular-nums">{r.metrika_visits != null ? fmtInt(r.metrika_visits) : '—'}</td>
                  <td className="py-1 text-right tabular-nums font-medium"
                    style={{ color: r.ratio_pct == null ? 'rgba(26,26,46,0.4)' : inCorridor(r.ratio_pct) ? GREEN : RED }}>
                    {r.ratio_pct != null ? `${r.ratio_pct}%` : 'нет повизитки'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <Empty note="Сессий за окно ещё нет." />}
    </Card>
  );
}

// Привлечение: классика + сегменты + деньги Директа.
function AcquisitionFullTab({ d }) {
  const segs = d.segments?.segments || [];
  const segPager = usePager(segs, 20);
  const costs = d.ad_costs || {};
  return (
    <div className="space-y-5">
      <AcquisitionTab d={d} />

      <Card title="Сегменты: канал × устройство × новизна" icon={Layers}
        source={d.segments?.source === 'own' ? 'own' : 'metrika'}
        insight="Пересечение трёх осей; «с целью» — только конверсионные business-цели (регистрация, подписка, скачивание). За завершённые дни — агрегаты Метрики, за сегодня — сессии нашего счётчика. Где конверсия выше — там усиливать; сегменты с высокими отказами — проверять посадочные."
        hint="Пересечение трёх осей по визитам Метрики (за сегодня — по нашим сессиям): объём, конверсия в business-цель, отказы, время. Читать: сегменты с высокой конверсией — усиливать; с высокими отказами — проверять посадочные.">
        {segs.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-[12px]">
              <thead>
                <tr className="text-left text-text-tertiary border-b border-border-subtle">
                  <th className="py-1.5 pr-3 font-medium">Канал</th>
                  <th className="py-1.5 pr-3 font-medium">Устройство</th>
                  <th className="py-1.5 pr-3 font-medium">Новизна</th>
                  <th className="py-1.5 pr-3 font-medium text-right">Визиты</th>
                  <th className="py-1.5 pr-3 font-medium text-right">С целью</th>
                  <th className="py-1.5 pr-3 font-medium text-right">Конверсия</th>
                  <th className="py-1.5 pr-3 font-medium text-right">Ср. время</th>
                  <th className="py-1.5 font-medium text-right">Отказы</th>
                </tr>
              </thead>
              <tbody>
                {segPager.slice.map((s, i) => (
                  <tr key={i} className="border-b border-border-subtle/50">
                    <td className="py-1.5 pr-3 text-text-primary">{channelLabel(s.channel)}</td>
                    <td className="py-1.5 pr-3 text-text-secondary">{deviceLabel(s.device)}</td>
                    <td className="py-1.5 pr-3 text-text-secondary">{s.is_new ? 'Новые' : 'Вернувшиеся'}</td>
                    <td className="py-1.5 pr-3 text-right tabular-nums">{fmtInt(s.visits)}</td>
                    <td className="py-1.5 pr-3 text-right tabular-nums">{fmtInt(s.goal_visits)}</td>
                    <td className="py-1.5 pr-3 text-right tabular-nums font-medium" style={{ color: s.conversion_pct >= 5 ? GREEN : undefined }}>{s.conversion_pct}%</td>
                    <td className="py-1.5 pr-3 text-right tabular-nums">{s.avg_duration_sec} с</td>
                    <td className="py-1.5 text-right tabular-nums">{s.bounce_pct}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pager p={segPager} />
          </div>
        ) : <Empty note="Сессий за период ещё нет — сегменты появятся с первым трафиком." />}
      </Card>

      <Card title="Деньги рекламы: расход, CPA, ROI" icon={Megaphone} source="metrika"
        insight={costs.connected
          ? `Расход за окно: ${fmtInt(Math.round(costs.total_cost_rub || 0))} ₽ · макро-целей: ${fmtInt(costs.macro_goals_window)} · CPA ${costs.cpa_macro_rub != null ? `${fmtInt(Math.round(costs.cpa_macro_rub))} ₽` : '—'}.`
          : costs.note || 'Коннектор партнёрской сети (РСЯ) включится после передачи API-токена.'}
        hint="Расход кампаний партнёрских сетей (РСЯ) против достигнутых макро-целей: цена одной конверсии (CPA). Появится полностью после подключения токена.">
        {costs.connected && (costs.campaigns || []).length ? (
          <HBars data={costs.campaigns.map((c) => ({ name: c.campaign, value: Math.round(c.cost_rub) }))} unit=" ₽" />
        ) : <Empty note="Каркас готов: таблица расходов и синк ждут токен партнёрской сети (РСЯ)." />}
      </Card>
    </div>
  );
}

/* ---------- Легенда терминов (волна 2, п. 2) ---------- */

// Единый словарь дашборда: «сессии/посетители» — наш счётчик, «визиты» —
// Метрика, «пользователи» — зарегистрированные аккаунты. Раскрываемая
// шпаргалка в шапке, чтобы подписи карточек читались однозначно.
function TermsLegend() {
  const [open, setOpen] = useState(false);
  const TERMS = [
    ['Сессия', 'наш счётчик', 'Непрерывная активность посетителя на сайте: пауза 30 минут и дольше открывает новую сессию (то же правило, что у визита Метрики). Считается нашим сервером в реальном времени, боты и своя активность исключены.'],
    ['Посетитель', 'наш счётчик', 'Уникальный человек по постоянному идентификатору браузера (кросс-девайс — через аккаунт). У одного посетителя может быть много сессий.'],
    ['Визит', 'Метрика', 'Та же 30-минутная логика, но посчитанная Яндекс.Метрикой. Повизитные данные приходят с задержкой до суток, поэтому «сегодня» у Метрики — сводные живые числа. Сессия и визит совпадать не обязаны: разные счётчики, разные фильтры ботов.'],
    ['Пользователь', 'аккаунты', 'Зарегистрированный аккаунт на платформе (вход по e-mail или через соцсети). Не путать с посетителем: большинство посетителей — гости без аккаунта.'],
  ];
  return (
    <div className="mb-5 -mt-2">
      <button type="button" onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 text-[12px] text-text-tertiary hover:text-text-primary">
        <Info size={13} />
        Словарь дашборда: чем сессия отличается от визита
        <span className="text-[10px]">{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="mt-2 grid sm:grid-cols-2 gap-3 rounded-2xl bg-surface border border-border-subtle p-4">
          {TERMS.map(([term, layer, def]) => (
            <div key={term} className="text-[12.5px] leading-snug">
              <span className="font-semibold text-text-primary">{term}</span>
              <span className={`ml-1.5 text-[10px] px-1.5 py-0.5 rounded-full align-middle ${
                layer === 'Метрика' ? 'bg-blue-50 text-blue-700'
                  : layer === 'аккаунты' ? 'bg-green-50 text-green-700' : 'bg-purple-50 text-purple-700'
              }`}>{layer}</span>
              <p className="text-text-secondary mt-0.5">{def}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ---------- Логин-гейт ---------- */

function AdminLogin({ onSuccess }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      const user = await loginUser({ email, password });
      onSuccess(user);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Не удалось войти');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-[60vh] flex items-center justify-center px-4 pt-24">
      <form onSubmit={submit} className="w-full max-w-sm rounded-2xl bg-surface border border-border-subtle p-6 space-y-4">
        <h1 className="text-lg font-semibold text-text-primary">Служебный раздел</h1>
        <p className="text-[13px] text-text-secondary">Доступ по учётной записи администратора.</p>
        <input
          type="email" autoComplete="username" required value={email}
          onChange={(e) => setEmail(e.target.value)} placeholder="E-mail"
          className="w-full px-3.5 py-2.5 rounded-xl bg-obsidian border border-border-subtle text-[14px] outline-none focus:border-border-champagne"
        />
        <input
          type="password" autoComplete="current-password" required value={password}
          onChange={(e) => setPassword(e.target.value)} placeholder="Пароль"
          className="w-full px-3.5 py-2.5 rounded-xl bg-obsidian border border-border-subtle text-[14px] outline-none focus:border-border-champagne"
        />
        {error && <p className="text-[13px] text-negative">{error}</p>}
        <button
          type="submit" disabled={busy}
          className="w-full py-2.5 rounded-xl bg-champagne text-white text-[14px] font-medium disabled:opacity-60"
        >
          {busy ? 'Проверяем…' : 'Войти'}
        </button>
      </form>
    </div>
  );
}

/* ---------- Страница ---------- */

// 10 разделов executive-модели (этап 3.6 «Аналитики 2.0»): «Дерево» — главная;
// справочники (События/Датасет/Гипотезы) живут внутри соответствующих разделов.
const TABS = [
  { id: 'tree', label: 'Дерево', icon: Target, C: MetricTreeTab },
  { id: 'acquisition', label: 'Привлечение', icon: Megaphone, C: AcquisitionFullTab },
  { id: 'audience', label: 'Аудитория', icon: Users, C: AudienceFullTab },
  { id: 'behavior', label: 'Поведение', icon: MousePointerClick, C: BehaviorTab },
  { id: 'conversion', label: 'Конверсия', icon: Filter, C: ConversionTab },
  { id: 'retention', label: 'Удержание', icon: Users, C: RetentionTab },
  { id: 'demand', label: 'Спрос и SEO', icon: Search, C: DemandTab },
  { id: 'product', label: 'Что менять', icon: Wrench, C: ProductLoopTab },
  { id: 'slices', label: 'Срезы', icon: SlidersHorizontal, C: SlicesTab },
  { id: 'reliability', label: 'Надёжность', icon: ShieldCheck, C: ReliabilityTab },
];

export default function AdminBI() {
  const { user, isAuthed, isLoading, setUser } = useAuth();
  const [period, setPeriod] = useState('7d');
  const [customFrom, setCustomFrom] = useState('');
  const [customTo, setCustomTo] = useState('');
  const [tab, setTab] = useState('tree');

  useDocumentMeta({ title: 'BI — служебный раздел', description: '', path: '/admin/bi', robots: 'noindex, nofollow' });

  const isAdmin = Boolean(user?.is_admin);
  // custom без выбранной даты «с» — запрос не шлём (бэкенд упал бы в 30d молча).
  const customReady = period !== 'custom' || Boolean(customFrom);
  const { data, isLoading: biLoading, isError, dataUpdatedAt, refetch, isFetching } = useQuery({
    queryKey: ['admin-bi', period, customFrom, customTo],
    queryFn: () => fetchDashboard(period, customFrom, customTo),
    enabled: isAdmin && customReady,
    refetchInterval: 15 * 60 * 1000,
    staleTime: 14 * 60 * 1000,
    retry: 1,
  });

  if (isLoading) return null;
  if (!isAuthed) return <AdminLogin onSuccess={setUser} />;
  if (!isAdmin) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <p className="text-text-tertiary text-[15px]">404 — страница не найдена</p>
      </div>
    );
  }

  const Active = TABS.find((t) => t.id === tab)?.C || MetricTreeTab;
  const openSlices = () => setTab('slices');

  return (
    <div className="max-w-[1400px] mx-auto px-4 sm:px-6 pt-24 pb-10">
      <div className="flex flex-wrap items-center gap-3 mb-5">
        <h1 className="text-xl font-bold text-text-primary">BI-аналитика платформы</h1>
        <div className="flex items-center gap-1 rounded-full bg-surface border border-border-subtle p-1">
          {PERIODS.map((p) => (
            <button
              key={p.id} type="button" onClick={() => setPeriod(p.id)}
              className={`px-3 py-1 rounded-full text-[12px] transition-colors ${
                period === p.id ? 'bg-champagne text-white' : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
        {period === 'custom' && (
          <div className="flex items-center gap-1.5 text-[12px] text-text-secondary">
            <input
              type="date" value={customFrom} max={customTo || undefined}
              onChange={(e) => setCustomFrom(e.target.value)}
              className="rounded-lg border border-border-subtle bg-surface px-2 py-1 text-[12px]"
            />
            <span>—</span>
            <input
              type="date" value={customTo} min={customFrom || undefined}
              onChange={(e) => setCustomTo(e.target.value)}
              className="rounded-lg border border-border-subtle bg-surface px-2 py-1 text-[12px]"
            />
            <span className="text-text-tertiary">МСК</span>
          </div>
        )}
        {data?.period?.label && (
          <span className="text-[12px] text-text-tertiary" title="Окно данных, время московское">
            {data.period.from === data.period.to
              ? `${data.period.label} · ${data.period.from}`
              : `${data.period.label} · ${data.period.from} — ${data.period.to}`}
          </span>
        )}
        <button
          type="button" onClick={() => refetch()}
          className="ml-auto flex items-center gap-1.5 text-[12px] text-text-tertiary hover:text-text-primary"
          title="Обновить сейчас"
        >
          <RefreshCw size={13} className={isFetching ? 'animate-spin' : ''} />
          {dataUpdatedAt ? `обновлено ${new Date(dataUpdatedAt).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}` : ''}
          <span className="hidden sm:inline">· автообновление каждые 15 мин</span>
        </button>
      </div>

      <TermsLegend />

      <div className="flex gap-1.5 overflow-x-auto pb-2 mb-5 scrollbar-hide">
        {TABS.map((t) => (
          <button
            key={t.id} type="button" onClick={() => setTab(t.id)}
            className={`flex items-center gap-1.5 whitespace-nowrap px-3.5 py-1.5 rounded-full text-[13px] border transition-colors ${
              tab === t.id
                ? 'bg-champagne/15 text-champagne border-transparent font-medium'
                : 'bg-surface text-text-secondary border-border-subtle hover:text-text-primary'
            }`}
          >
            <t.icon size={13} />
            {t.label}
          </button>
        ))}
      </div>

      {!customReady && (
        <p className="text-[14px] text-text-tertiary py-10 text-center">Выберите даты периода (московское время).</p>
      )}
      {customReady && biLoading && <p className="text-[14px] text-text-tertiary py-10 text-center">Считаем витрины…</p>}
      {isError && <p className="text-[14px] text-negative py-10 text-center">Не удалось загрузить данные. Попробуйте обновить.</p>}
      {data && <Active d={data} onOpenSlices={openSlices} />}
    </div>
  );
}
