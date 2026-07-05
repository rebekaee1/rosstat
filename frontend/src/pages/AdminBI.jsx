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
  ScatterChart, Scatter, ZAxis, ReferenceLine, FunnelChart, Funnel, Treemap,
} from 'recharts';
import {
  Activity, Users, MousePointerClick, Search, TrendingUp, Route,
  AlertTriangle, Brain, Database, Megaphone, RefreshCw, Filter, LogIn,
  CalendarClock, LayoutGrid,
} from 'lucide-react';
import api, { loginUser } from '../lib/api';
import { useAuth } from '../context/authContext';
import useDocumentMeta from '../lib/useMeta';

const GOLD = '#B8942F';
const INK = '#1A1A2E';
const GREEN = '#16A34A';
const RED = '#DC2626';
const BLUE = '#2563EB';
const PURPLE = '#7C3AED';
const PALETTE = [GOLD, BLUE, GREEN, PURPLE, '#0891B2', '#DB2777', '#EA580C', '#65A30D', INK, '#9333EA', '#0D9488', '#C026D3'];

const PERIODS = [
  { days: 1, label: 'Сутки' },
  { days: 7, label: 'Неделя' },
  { days: 30, label: 'Месяц' },
  { days: 90, label: 'Квартал' },
  { days: 365, label: 'Год' },
];

const SOURCE_RU = {
  ad: 'Реклама (Директ)',
  organic: 'Поисковые системы',
  direct: 'Прямые заходы',
  referral: 'Переходы с сайтов',
  link: 'Переходы с сайтов',
  internal: 'Внутренние переходы',
  recommend: 'Рекомендательные системы',
  social: 'Социальные сети',
  saved: 'Сохранённые страницы',
  unknown: 'Источник не определён',
};

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

function fetchDashboard(days) {
  return api.get(`/admin/bi/dashboard?days=${days}`).then((r) => r.data);
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

function Card({ title, icon: Icon, insight, children, span }) {
  return (
    <section className={`rounded-2xl bg-surface border border-border-subtle p-5 ${span || ''}`}>
      <h2 className="flex items-center gap-2 text-[15px] font-semibold text-text-primary">
        {Icon && <Icon size={16} className="text-champagne" />}
        {title}
      </h2>
      {insight && <p className="text-[12.5px] text-text-secondary mt-1 mb-3 leading-snug">{insight}</p>}
      {!insight && <div className="mb-4" />}
      {children}
    </section>
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

const dictToBars = (obj, n = 12) =>
  Object.entries(obj || {}).sort((a, b) => b[1] - a[1]).slice(0, n).map(([name, value]) => ({ name, value }));

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
          const c = grid.m.get(`${dow}-${hour}`) || { own: 0, visits: 0 };
          const ownOnly = !c.visits && c.own > 0;
          const t = ownOnly
            ? (grid.maxOwn ? c.own / grid.maxOwn : 0)
            : (grid.maxVisits ? c.visits / grid.maxVisits : 0);
          const shown = ownOnly ? c.own : c.visits;
          const fill = shown
            ? (ownOnly ? `rgba(124,58,237,${0.12 + t * 0.6})` : `rgba(184,148,47,${0.12 + t * 0.78})`)
            : 'rgba(26,26,46,0.045)';
          return (
            <g key={`${dow}-${hour}`}>
              <rect
                x={LEFT + hour * (CELL + GAP)} y={TOP + dow * (CELL + GAP)}
                width={CELL} height={CELL} rx={4} fill={fill}
              >
                <title>{`${DOW_RU[dow]}, ${hour}:00–${hour + 1}:00 — визиты Метрики: ${fmtInt(c.visits)}, просмотры нашего счётчика: ${fmtInt(c.own)}`}</title>
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
        <span>больше — визиты Метрики</span>
        <span className="w-4 h-4 rounded ml-2" style={{ background: 'rgba(124,58,237,0.5)' }} />
        <span>только наш счётчик (Метрика ещё не отдала час) · время московское</span>
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
    const t = { visits: 0, visitors: 0, ad: 0, reg: 0, dl: 0, err: 0, ev: 0, srch: 0, live: 0 };
    for (const r of kpi) {
      t.visits += r.visits; t.visitors += r.visitors; t.ad += r.ad_visits;
      t.reg += r.registrations; t.dl += r.downloads; t.err += r.errors;
      t.ev += r.events; t.srch += r.searches; t.live += r.live_sessions || 0;
    }
    return t;
  }, [kpi]);
  const spark = (key) => kpi.map((r) => ({ v: r[key] }));
  const srcDonut = Object.entries(d.acquisition?.sources || {}).map(([k, v]) => ({ name: SOURCE_RU[k] || k, value: v }));

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">
        <Kpi label="Визиты (Метрика)" value={fmtInt(totals.visits)} series={spark('visits')} />
        <Kpi label="Сессии (наш счётчик)" value={fmtInt(totals.live)} series={spark('live_sessions')} color={PURPLE} />
        <Kpi label="Посетители" value={fmtInt(totals.visitors)} series={spark('visitors')} color={INK} />
        <Kpi label="Из рекламы" value={fmtInt(totals.ad)} sub={totals.visits ? fmtPct(Math.round(totals.ad / totals.visits * 100)) : null} series={spark('ad_visits')} color={BLUE} />
        <Kpi label="Регистрации" value={fmtInt(totals.reg)} sub={`всего ${fmtInt(d.users?.total)}`} series={spark('registrations')} color={GREEN} />
        <Kpi label="Скачивания" value={fmtInt(totals.dl)} series={spark('downloads')} color={PURPLE} />
        <Kpi label="Поиски на сайте" value={fmtInt(totals.srch)} series={spark('searches')} color={BLUE} />
        <Kpi label="Ошибки фронта" value={fmtInt(totals.err)} series={spark('errors')} color={RED} />
      </div>

      <Card title="Трафик по дням: Метрика и собственный счётчик" icon={Activity}
        insight="Столбцы — сессии нашего счётчика (реальное время, без задержки). Площадь и линии — Яндекс.Метрика: она отдаёт визиты с задержкой до суток, поэтому свежие дни у неё могут быть пустыми — смотрите на столбцы.">
        <ResponsiveContainer width="100%" height={290}>
          <ComposedChart data={kpi} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="gVisits" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={GOLD} stopOpacity={0.28} />
                <stop offset="100%" stopColor={GOLD} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
            <XAxis dataKey="date" tick={{ fontSize: 11, fill: 'rgba(26,26,46,0.5)' }} tickFormatter={(v) => v.slice(5)} />
            <YAxis tick={{ fontSize: 11, fill: 'rgba(26,26,46,0.5)' }} width={40} />
            <Tooltip {...TT_STYLE} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar dataKey="live_sessions" name="Сессии (наш счётчик, live)" fill={PURPLE} fillOpacity={0.30} radius={[3, 3, 0, 0]} maxBarSize={26} />
            <Area type="monotone" dataKey="visits" name="Визиты (Метрика)" stroke={GOLD} fill="url(#gVisits)" strokeWidth={2} />
            <Line type="monotone" dataKey="visitors" name="Посетители (Метрика)" stroke={INK} strokeWidth={1.6} dot={false} />
            <Line type="monotone" dataKey="ad_visits" name="Из рекламы" stroke={BLUE} strokeWidth={1.4} dot={false} strokeDasharray="4 3" />
          </ComposedChart>
        </ResponsiveContainer>
      </Card>

      <Card title="Пульс недели: когда аудитория на сайте" icon={CalendarClock}
        insight="Активность по дням недели и часам (московское время): визиты Метрики плюс просмотры собственного счётчика. Тёмные зоны — пиковые окна: под них планируются публикации, реклама и релизы.">
        <WeekPulse cells={d.activity_heatmap} />
      </Card>

      <div className="grid lg:grid-cols-3 gap-5">
        <Card title="Структура источников" icon={Megaphone} span="lg:col-span-1" insight="Откуда приходят визиты за период.">
          <Donut data={srcDonut} centerLabel="визитов" />
        </Card>
        <Card title="Конверсии и ошибки по дням" icon={TrendingUp} span="lg:col-span-2" insight="Регистрации и скачивания — целевые действия. Красная линия ошибок не должна расти вместе с трафиком.">
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
  const srcDonut = Object.entries(a.sources || {}).map(([k, v]) => ({ name: SOURCE_RU[k] || k, value: v }));
  const devDonut = Object.entries(a.devices || {}).map(([k, v]) => ({ name: k === 'desktop' ? 'Компьютеры' : k === 'mobile' ? 'Смартфоны' : k === 'tablet' ? 'Планшеты' : k, value: v }));
  const ads = (a.ad_campaigns || []).filter((c) => c.visits > 0)
    .map((c) => ({ ...c, x: c.visits, y: c.goal_rate_pct, z: Math.max(c.bounce_pct, 1) }));

  return (
    <div className="grid lg:grid-cols-2 gap-5">
      <Card title="Структура источников трафика" icon={Megaphone} insight="Баланс платного и органического трафика — основа стоимости привлечения.">
        <Donut data={srcDonut} centerLabel="визитов" />
      </Card>
      <Card title="Поисковые системы" icon={Search} insight="Из каких поисковиков приходит органический трафик.">
        <HBars data={dictToBars(a.search_engines, 8)} color={BLUE} />
      </Card>

      <Card title="Кампании Директа: объём, конверсия и отказы" icon={Megaphone} span="lg:col-span-2"
        insight="По горизонтали — визиты, по вертикали — конверсия в цель, размер точки — доля отказов. Правый верх — эффективные кампании; крупные точки внизу справа расходуют бюджет впустую.">
        {ads.length ? (
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
        ) : <Empty note="Платных кампаний за период нет. Расход и цена клика появятся после подключения Яндекс.Директа." />}
      </Card>

      <Card title="Поисковые фразы, с которых пришли" icon={Search} insight="Реальные запросы, приведшие посетителей из поиска.">
        <HBars data={dictToBars(a.top_phrases, 12)} labelWidth={190} />
      </Card>
      <div className="space-y-5">
        <Card title="Устройства" icon={Users}>
          <Donut data={devDonut} height={180} centerLabel="визитов" />
        </Card>
        <Card title="География: города" icon={Users}>
          <HBars data={dictToBars(a.top_cities, 8)} color={PURPLE} />
        </Card>
      </div>
    </div>
  );
}

function FunnelTab({ d }) {
  const f = d.funnel || {};
  const bySource = (f.by_source || []).filter((s) => s.visits > 0);
  const totals = bySource.reduce((t, s) => ({
    visits: t.visits + s.visits, engaged: t.engaged + s.engaged, goal: t.goal + s.goal_visits,
  }), { visits: 0, engaged: 0, goal: 0 });
  const funnelData = [
    { name: 'Визиты', value: totals.visits, fill: GOLD },
    { name: 'Вовлечённые', value: totals.engaged, fill: BLUE },
    { name: 'Достигли цели', value: totals.goal, fill: GREEN },
  ].filter((s) => s.value > 0);
  const engRate = totals.visits ? Math.round(totals.engaged / totals.visits * 100) : 0;
  const goalRate = totals.visits ? Math.round(totals.goal / totals.visits * 100) : 0;

  const stack = bySource.map((s) => ({
    name: SOURCE_RU[s.source] || s.source,
    goal: s.goal_visits,
    engaged: Math.max(s.engaged - s.goal_visits, 0),
    bounced: Math.max(s.visits - s.engaged, 0),
    visits: s.visits,
    goal_pct: s.goal_pct,
    engaged_pct: s.engaged_pct,
  }));

  const landings = (f.top_landings || []).slice(0, 14);
  const maxLandingVisits = Math.max(1, ...landings.map((l) => l.visits));

  return (
    <div className="space-y-5">
      <div className="grid lg:grid-cols-2 gap-5">
        <Card title="Общая воронка визита" icon={Filter} insight={`Из всех визитов вовлекается ${engRate}%, до целевого действия доходит ${goalRate}%. Цели: регистрация, вход, подписка, скачивание данных, обратная связь.`}>
          {funnelData.length ? (
            <ResponsiveContainer width="100%" height={260}>
              <FunnelChart>
                <Tooltip {...TT_STYLE} formatter={(v) => [fmtInt(v), 'визитов']} />
                <Funnel dataKey="value" data={funnelData} isAnimationActive>
                  <LabelList position="right" fill="#1A1A2E" stroke="none" dataKey="name" style={{ fontSize: 12 }} />
                  <LabelList position="left" fill="rgba(26,26,46,0.55)" stroke="none" dataKey="value" formatter={fmtInt} style={{ fontSize: 11 }} />
                </Funnel>
              </FunnelChart>
            </ResponsiveContainer>
          ) : <Empty />}
        </Card>
        <Card title="Качество каналов" icon={TrendingUp} insight="Состав каждого канала: дошли до цели (зелёное), вовлеклись (золотое), отсеялись (серое). Наведите — точные числа.">
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
          ) : <Empty />}
        </Card>
      </div>

      <Card title="Посадочные страницы: объём входа и конверсия" icon={Route}
        insight="Отсортировано по визитам. Длина полосы — визиты, цвет и метка справа — конверсия в цель на этой точке входа. Большая полоса с серой меткой — трафик без отдачи.">
        {landings.length ? (
          <div className="space-y-1.5">
            {landings.map((l) => {
              const w = Math.max(2, Math.round(l.visits / maxLandingVisits * 100));
              const good = l.goal_pct >= 10;
              const mid = l.goal_pct >= 3 && l.goal_pct < 10;
              return (
                <div key={l.page} className="flex items-center gap-3" title={`${l.page}: ${fmtInt(l.visits)} визитов, ${fmtInt(l.goal_visits)} с целью (${l.goal_pct}%)`}>
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
                    {l.goal_pct}% · {fmtInt(l.goal_visits)}
                  </span>
                </div>
              );
            })}
            <div className="flex items-center gap-4 pt-2 text-[11px] text-text-tertiary">
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded" style={{ background: 'rgba(22,163,74,0.75)' }} /> конверсия ≥ 10%</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded" style={{ background: 'rgba(184,148,47,0.75)' }} /> 3–10%</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded" style={{ background: 'rgba(26,26,46,0.28)' }} /> &lt; 3%</span>
            </div>
          </div>
        ) : <Empty />}
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
        insight="Средний по дневным когортам процент посетителей, вернувшихся через N дней после первого визита. Для молодого продукта дневной масштаб — основной; недельные когорты накопятся со временем.">
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
        insight="Строка — новые посетители конкретного дня, столбцы — сколько из них вернулось через N дней. Насыщенность — доля вернувшихся (наведите для процента).">
        <CohortTable rows={dayCohorts} keyField="cohort_day" offsetsField="day_plus" cols={dayCols} colPrefix="+" />
      </Card>
      <Card title="Когорты по неделе первого визита" icon={Users}
        insight={hasWeekData
          ? 'Строка — когорта новых посетителей, столбцы — недели спустя. Насыщенность клетки — доля вернувшихся.'
          : 'Недельный масштаб станет информативным, когда истории наблюдений будет больше месяца — пока все посетители внутри первых недель.'}>
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
        insight="Площадь плитки — просмотры раздела за период. Видно, какие продуктовые блоки несут трафик, а какие простаивают.">
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
        insight="Столбцы — просмотры страниц (топ-20), линия — накопленная доля от их суммы. Где линия пересекает 80% — столько страниц несут основную нагрузку.">
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
        insight="По горизонтали — просмотры, по вертикали — среднее время на странице. Правый низ (много просмотров, мало времени) — популярные «тонкие» страницы, кандидаты на доработку. Пунктир — медианы.">
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
        insight="Пустые клики (без реакции интерфейса) и серии раздражённых кликов — прямые кандидаты на исправление UX.">
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
      <Card title="Карта возможностей в поиске Яндекса: показы и позиция" icon={Search}
        insight="По горизонтали — показы, по вертикали — средняя позиция (выше = лучше, ось перевёрнута), размер точки — клики. Правый низ (много показов, слабая позиция) — запросы с наибольшим потенциалом роста трафика.">
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
        <Card title="Поиски на сайте без результата" icon={AlertTriangle} insight="Прямая карта пробелов каталога: что ищут, но не находят. Приоритет на добавление.">
          <HBars data={dictToBars(s.zero_results, 12)} color={RED} labelWidth={190} />
        </Card>
        <Card title="Фразы прихода из поиска (Метрика)" icon={Search} insight="Реальный органический спрос, приведший визиты за период.">
          <HBars data={(dem.metrika_phrases || []).slice(0, 12).map((p) => ({ name: p.phrase, value: p.visits }))} color={GREEN} labelWidth={190} />
        </Card>
      </div>
      <Card title="Что ищут внутри сайта — по полям поиска" icon={Search}
        insight={`Каждое поле поиска сайта — отдельный срез спроса. Всего запросов за период: ${fmtInt(s.total_queries)}.`}>
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
        insight="Строки — страница-источник, столбцы — страница-назначение, насыщенность клетки — число переходов. Читается по строке: куда уходит посетитель с ключевой страницы.">
        <TransitionMatrix transitions={n.top_transitions} />
      </Card>
      <div className="grid lg:grid-cols-2 gap-5">
        <Card title="Точки входа" icon={LogIn} insight="С каких страниц начинаются сессии.">
          <HBars data={dictToBars(n.top_entries, 10)} color={GREEN} labelWidth={190} />
        </Card>
        <Card title="Точки выхода" icon={Route} insight="Где сессии обрываются — кандидаты на усиление перелинковки и призывов к действию.">
          <HBars data={dictToBars(n.top_exits, 10)} color={RED} labelWidth={190} />
        </Card>
        <Card title="Пустые клики: элементы без реакции" icon={MousePointerClick} insight="Пользователь кликает, интерфейс не отвечает. Каждая строка — конкретный элемент на конкретной странице.">
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
        <Card title="Серии раздражённых кликов" icon={MousePointerClick} insight="Многократные быстрые клики в одно место — признак «не работает» или «слишком медленно».">
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

const DEVICE_RU = {
  desktop: 'Компьютеры', mobile: 'Смартфоны', tablet: 'Планшеты',
  tv: 'Телевизоры', bot: 'Роботы', unknown: 'Не определено',
};
const deviceRu = (k) => DEVICE_RU[k] || k;

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
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Kpi label="Сессии (наш счётчик)" value={fmtInt(a.own_sessions_total)} color={PURPLE} sub="портреты behavior-сессий" />
        <Kpi label="Из них зарегистрированные" value={fmtInt(a.own_authed_sessions)} color={GREEN} />
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

      <Card title="Устройства: наш счётчик и Метрика" icon={Users}
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

      <Card title="Браузеры" icon={LayoutGrid}
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
        insight="Наши данные включают версию системы — точнее, чем агрегат Метрики.">
        <PairedBars own={a.os} metrika={ref.os} />
      </Card>

      <div className="grid lg:grid-cols-2 gap-5">
        <Card title="Экраны" icon={LayoutGrid}
          insight="Физические разрешения экранов — под какие размеры проектировать интерфейс и графики.">
          <HBars data={dictToBars(a.screens, 10)} color={BLUE} labelWidth={110} />
        </Card>
        <Card title="Ширина окна браузера" icon={LayoutGrid}
          insight="Реальная ширина рабочей области — важнее разрешения экрана: окна бывают свёрнуты.">
          <HBars data={dictToBars(a.viewports, 10)} color={BLUE} labelWidth={110} />
        </Card>
        <Card title="Языки и часовые пояса" icon={Users}
          insight="Язык браузера и таймзона — география и локализация аудитории без сбора персональных данных.">
          <div className="grid grid-cols-2 gap-4">
            <HBars data={dictToBars(a.languages, 8)} color={GREEN} labelWidth={80} />
            <HBars data={dictToBars(a.timezones, 8)} color={GREEN} labelWidth={130} />
          </div>
        </Card>
        <Card title="Сайты-источники переходов" icon={Route}
          insight="Домены, с которых пришли сессии по данным собственного счётчика.">
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
        insight="Каждая полоса — действие на сайте (тёмный сегмент — зарегистрированные, золотой — гости). Видно, какие действия делают авторизованные пользователи, а какие — случайные посетители.">
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
      <Card title="Полный реестр событий за период" icon={Database}
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
                {all.map((e) => (
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
          </div>
        ) : <Empty />}
      </Card>
    </div>
  );
}

function HypothesesTab({ d }) {
  const rows = d.hypotheses || [];
  if (!rows.length) {
    return <Card title="Гипотезы Пульс-аналитика" icon={Brain}><p className="text-[13px] text-text-tertiary">Гипотез пока нет — Пульс формулирует их ежедневно после утреннего отчёта.</p></Card>;
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
            <div className="min-w-0">
              <div className="text-[14px] text-text-primary">{h.statement}</div>
              {h.rationale && <div className="text-[12px] text-text-secondary mt-1">{h.rationale}</div>}
              <div className="text-[11px] text-text-tertiary mt-1">
                {h.confidence != null && `уверенность ${Math.round(h.confidence * 100)}% · `}
                {h.source} · {h.updated_at?.slice(0, 10)}
              </div>
            </div>
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
        insight="Всё, что копится в хранилище: объёмы, окна времени, фактические ключи JSON-полей и разбивки по типам. Данные пересчитываются из БД при каждом обновлении.">
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

const TABS = [
  { id: 'overview', label: 'Обзор', icon: Activity, C: OverviewTab },
  { id: 'acquisition', label: 'Привлечение', icon: Megaphone, C: AcquisitionTab },
  { id: 'audience', label: 'Аудитория', icon: Users, C: AudienceTab },
  { id: 'funnel', label: 'Воронка', icon: Filter, C: FunnelTab },
  { id: 'retention', label: 'Retention', icon: Users, C: RetentionTab },
  { id: 'pages', label: 'Контент', icon: LayoutGrid, C: PagesTab },
  { id: 'demand', label: 'Спрос и поиск', icon: Search, C: DemandTab },
  { id: 'navigation', label: 'Навигация и UX', icon: MousePointerClick, C: NavigationTab },
  { id: 'events', label: 'События', icon: TrendingUp, C: EventsTab },
  { id: 'hypotheses', label: 'Гипотезы', icon: Brain, C: HypothesesTab },
  { id: 'dataset', label: 'Датасет', icon: Database, C: DatasetTab },
];

export default function AdminBI() {
  const { user, isAuthed, isLoading, setUser } = useAuth();
  const [days, setDays] = useState(7);
  const [tab, setTab] = useState('overview');

  useDocumentMeta({ title: 'BI — служебный раздел', description: '', path: '/admin/bi', robots: 'noindex, nofollow' });

  const isAdmin = Boolean(user?.is_admin);
  const { data, isLoading: biLoading, isError, dataUpdatedAt, refetch, isFetching } = useQuery({
    queryKey: ['admin-bi', days],
    queryFn: () => fetchDashboard(days),
    enabled: isAdmin,
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

  const Active = TABS.find((t) => t.id === tab)?.C || OverviewTab;

  return (
    <div className="max-w-[1400px] mx-auto px-4 sm:px-6 pt-24 pb-10">
      <div className="flex flex-wrap items-center gap-3 mb-5">
        <h1 className="text-xl font-bold text-text-primary">BI-аналитика платформы</h1>
        <div className="flex items-center gap-1 rounded-full bg-surface border border-border-subtle p-1">
          {PERIODS.map((p) => (
            <button
              key={p.days} type="button" onClick={() => setDays(p.days)}
              className={`px-3 py-1 rounded-full text-[12px] transition-colors ${
                days === p.days ? 'bg-champagne text-white' : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
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

      {biLoading && <p className="text-[14px] text-text-tertiary py-10 text-center">Считаем витрины…</p>}
      {isError && <p className="text-[14px] text-negative py-10 text-center">Не удалось загрузить данные. Попробуйте обновить.</p>}
      {data && <Active d={data} />}
    </div>
  );
}
