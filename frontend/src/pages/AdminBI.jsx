// Админ-BI /admin/bi (директива владельца 2026-07-05, редизайн 2026-07-05 ночь-2):
// профессиональная многоуровневая визуализация для стратегических решений —
// не сырые таблицы, а диаграммы MBA-уровня: donut-структуры, воронки, scatter-
// квадранты «спрос×позиция» и «просмотры×вовлечение», Sankey-граф навигации,
// retention-кривая + когорты, стек-бары событий. Везде hover с точными числами
// и краткий содержательный вывод (insight) над графиком. Обычный пользователь
// раздела не видит: backend отвечает 404 всем, кроме settings.admin_emails.
// Данные самообновляются: Redis-кэш 15 минут + refetchInterval 15 минут.
import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  ResponsiveContainer, ComposedChart, Line, Area, Bar, BarChart, XAxis, YAxis,
  Tooltip, CartesianGrid, Legend, PieChart, Pie, Cell, LabelList,
  ScatterChart, Scatter, ZAxis, ReferenceLine, FunnelChart, Funnel,
  Sankey, Layer, Rectangle,
} from 'recharts';
import {
  Activity, Users, MousePointerClick, Search, TrendingUp, Route,
  AlertTriangle, Brain, Database, Megaphone, RefreshCw, Filter, LogIn,
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
// Категориальная палитра для структурных диаграмм (донаты/стеки/scatter).
const PALETTE = [GOLD, BLUE, GREEN, PURPLE, '#0891B2', '#DB2777', '#EA580C', '#65A30D', INK, '#9333EA'];

const PERIODS = [
  { days: 1, label: 'Сутки' },
  { days: 7, label: 'Неделя' },
  { days: 30, label: 'Месяц' },
  { days: 90, label: 'Квартал' },
  { days: 365, label: 'Год' },
];

const SOURCE_RU = {
  ad: 'Реклама (Директ)',
  organic: 'Поисковики',
  direct: 'Прямые заходы',
  referral: 'Ссылки с сайтов',
  link: 'Ссылки с сайтов',
  internal: 'Внутренние',
  recommend: 'Рекомендательные',
  social: 'Соцсети',
  unknown: 'Не определён',
};

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

function Empty() {
  return <p className="text-[13px] text-text-tertiary py-8 text-center">Нет данных за период</p>;
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

// Донат: структура (доли) с центральной суммой и легендой с процентами.
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

// Горизонтальные бары: рейтинг (фразы/города/поисковики/тупики).
function HBars({ data, height, color = GOLD, unit = '', valueFmt = fmtInt }) {
  const rows = (data || []).filter((d) => d.value != null);
  if (!rows.length) return <Empty />;
  const h = height || Math.max(120, rows.length * 30 + 16);
  return (
    <ResponsiveContainer width="100%" height={h}>
      <BarChart layout="vertical" data={rows} margin={{ top: 2, right: 44, bottom: 2, left: 4 }}>
        <XAxis type="number" hide />
        <YAxis
          type="category" dataKey="name" width={148}
          tick={{ fontSize: 11.5, fill: 'rgba(26,26,46,0.72)' }}
          tickFormatter={(v) => clip(v, 22)} interval={0}
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

/* ---------- Секции ---------- */

function OverviewTab({ d }) {
  const kpi = useMemo(() => d.kpi_daily || [], [d.kpi_daily]);
  const totals = useMemo(() => {
    const t = { visits: 0, visitors: 0, ad: 0, reg: 0, dl: 0, err: 0, ev: 0, srch: 0 };
    for (const r of kpi) {
      t.visits += r.visits; t.visitors += r.visitors; t.ad += r.ad_visits;
      t.reg += r.registrations; t.dl += r.downloads; t.err += r.errors;
      t.ev += r.events; t.srch += r.searches;
    }
    return t;
  }, [kpi]);
  const spark = (key) => kpi.map((r) => ({ v: r[key] }));
  const sources = d.acquisition?.sources || {};
  const srcDonut = Object.entries(sources).map(([k, v]) => ({ name: SOURCE_RU[k] || k, value: v }));

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">
        <Kpi label="Визиты" value={fmtInt(totals.visits)} series={spark('visits')} />
        <Kpi label="Посетители" value={fmtInt(totals.visitors)} series={spark('visitors')} color={INK} />
        <Kpi label="Из рекламы" value={fmtInt(totals.ad)} sub={totals.visits ? fmtPct(Math.round(totals.ad / totals.visits * 100)) : null} series={spark('ad_visits')} color={BLUE} />
        <Kpi label="Регистрации" value={fmtInt(totals.reg)} sub={`всего ${fmtInt(d.users?.total)}`} series={spark('registrations')} color={GREEN} />
        <Kpi label="Скачивания" value={fmtInt(totals.dl)} series={spark('downloads')} color={PURPLE} />
        <Kpi label="События" value={fmtInt(totals.ev)} series={spark('events')} />
        <Kpi label="Поиски" value={fmtInt(totals.srch)} series={spark('searches')} color={BLUE} />
        <Kpi label="Ошибки" value={fmtInt(totals.err)} series={spark('errors')} color={RED} />
      </div>

      <Card title="Трафик по дням" icon={Activity} insight="Площадь — визиты, линии — уникальные посетители и платный трафик. Расхождение визитов и посетителей = глубина возвратов.">
        <ResponsiveContainer width="100%" height={280}>
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
            <Area type="monotone" dataKey="visits" name="Визиты" stroke={GOLD} fill="url(#gVisits)" strokeWidth={2} />
            <Line type="monotone" dataKey="visitors" name="Посетители" stroke={INK} strokeWidth={1.6} dot={false} />
            <Line type="monotone" dataKey="ad_visits" name="Из рекламы" stroke={BLUE} strokeWidth={1.4} dot={false} strokeDasharray="4 3" />
          </ComposedChart>
        </ResponsiveContainer>
      </Card>

      <div className="grid lg:grid-cols-3 gap-5">
        <Card title="Структура трафика" icon={Megaphone} span="lg:col-span-1" insight="Откуда приходят визиты за период.">
          <Donut data={srcDonut} centerLabel="визитов" />
        </Card>
        <Card title="Конверсии и ошибки по дням" icon={TrendingUp} span="lg:col-span-2" insight="Регистрации и скачивания — целевые действия; красная линия ошибок не должна расти вместе с трафиком.">
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
  const devDonut = Object.entries(a.devices || {}).map(([k, v]) => ({ name: k, value: v }));
  const ads = (a.ad_campaigns || []).filter((c) => c.visits > 0)
    .map((c) => ({ ...c, x: c.visits, y: c.goal_rate_pct, z: Math.max(c.bounce_pct, 1) }));

  return (
    <div className="grid lg:grid-cols-2 gap-5">
      <Card title="Источники трафика" icon={Megaphone} insight="Баланс платного и органического трафика — основа стоимости привлечения.">
        <Donut data={srcDonut} centerLabel="визитов" />
      </Card>
      <Card title="Поисковики" icon={Search} insight="Распределение органики по системам.">
        <HBars data={dictToBars(a.search_engines, 8)} color={BLUE} />
      </Card>

      <Card title="Кампании Директа: объём × конверсия × отказы" icon={Megaphone} span="lg:col-span-2"
        insight="По оси X — визиты, по Y — конверсия в цель, размер точки — доля отказов. Правый верх — эффективные кампании; крупные точки внизу справа — сливают бюджет.">
        {ads.length ? (
          <ResponsiveContainer width="100%" height={300}>
            <ScatterChart margin={{ top: 10, right: 20, bottom: 20, left: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
              <XAxis type="number" dataKey="x" name="Визиты" tick={{ fontSize: 11, fill: 'rgba(26,26,46,0.5)' }}
                label={{ value: 'визиты', position: 'insideBottom', offset: -8, fontSize: 11, fill: 'rgba(26,26,46,0.5)' }} />
              <YAxis type="number" dataKey="y" name="Конверсия, %" unit="%" tick={{ fontSize: 11, fill: 'rgba(26,26,46,0.5)' }} width={44} />
              <ZAxis type="number" dataKey="z" range={[60, 500]} name="Отказы, %" />
              <Tooltip {...TT_STYLE} cursor={{ strokeDasharray: '3 3' }}
                formatter={(v, n) => [n === 'Визиты' ? fmtInt(v) : `${v}%`, n]}
                labelFormatter={() => ''} />
              <Scatter data={ads} fill={GOLD} fillOpacity={0.6}>
                {ads.map((c, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
                <LabelList dataKey="campaign" position="top" formatter={(v) => clip(v, 16)} style={{ fontSize: 10, fill: 'rgba(26,26,46,0.6)' }} />
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>
        ) : <p className="text-[13px] text-text-tertiary py-6 text-center">Платных кампаний за период нет. Колонка расхода появится после подключения коннектора Яндекс.Директа.</p>}
      </Card>

      <Card title="Поисковые фразы прихода" icon={Search} insight="С каких запросов реально приходят на сайт.">
        <HBars data={dictToBars(a.top_phrases, 12)} />
      </Card>
      <div className="space-y-5">
        <Card title="Устройства" icon={Users}>
          <Donut data={devDonut} height={190} centerLabel="визитов" />
        </Card>
        <Card title="География (города)" icon={Users}>
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

  // Стек по каналам: цель / вовлечённые-без-цели / отсеялись.
  const stack = bySource.map((s) => ({
    name: SOURCE_RU[s.source] || s.source,
    goal: s.goal_visits,
    engaged: Math.max(s.engaged - s.goal_visits, 0),
    bounced: Math.max(s.visits - s.engaged, 0),
  }));

  return (
    <div className="space-y-5">
      <div className="grid lg:grid-cols-2 gap-5">
        <Card title="Общая воронка визита" icon={Filter} insight={`Из всех визитов вовлекается ${engRate}%, доходят до целевого действия ${goalRate}%.`}>
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
        <Card title="Качество каналов" icon={TrendingUp} insight="Состав каждого канала: доля дошедших до цели (зелёное), вовлечённых и отсеявшихся. Виден канал с высоким объёмом, но слабым качеством.">
          {stack.length ? (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart layout="vertical" data={stack} margin={{ top: 2, right: 12, bottom: 2, left: 4 }} stackOffset="expand">
                <XAxis type="number" hide domain={[0, 1]} />
                <YAxis type="category" dataKey="name" width={128} tick={{ fontSize: 11.5, fill: 'rgba(26,26,46,0.72)' }} tickFormatter={(v) => clip(v, 18)} interval={0} />
                <Tooltip {...TT_STYLE} formatter={(v, n) => [fmtInt(v), n]} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="goal" name="Цель" stackId="s" fill={GREEN} radius={[0, 0, 0, 0]} maxBarSize={26} />
                <Bar dataKey="engaged" name="Вовлечён" stackId="s" fill={GOLD} maxBarSize={26} />
                <Bar dataKey="bounced" name="Отсеялся" stackId="s" fill="rgba(26,26,46,0.14)" maxBarSize={26} />
              </BarChart>
            </ResponsiveContainer>
          ) : <Empty />}
        </Card>
      </div>
      <Card title="Посадочные страницы: объём входа × конверсия" icon={Route}
        insight="X — визиты на страницу входа, Y — их конверсия в цель. Правый верх — сильные точки входа, правый низ — трафик без отдачи.">
        {(f.top_landings || []).length ? (
          <ResponsiveContainer width="100%" height={300}>
            <ScatterChart margin={{ top: 10, right: 20, bottom: 20, left: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
              <XAxis type="number" dataKey="visits" name="Визиты" tick={{ fontSize: 11, fill: 'rgba(26,26,46,0.5)' }}
                label={{ value: 'визиты входа', position: 'insideBottom', offset: -8, fontSize: 11, fill: 'rgba(26,26,46,0.5)' }} />
              <YAxis type="number" dataKey="goal_pct" name="Конверсия" unit="%" tick={{ fontSize: 11, fill: 'rgba(26,26,46,0.5)' }} width={44} />
              <ZAxis range={[80, 80]} />
              <Tooltip {...TT_STYLE} cursor={{ strokeDasharray: '3 3' }}
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const p = payload[0].payload;
                  return (
                    <div style={TT_STYLE.contentStyle}>
                      <div style={{ fontWeight: 600, marginBottom: 2 }}>{p.page}</div>
                      <div>Визиты: {fmtInt(p.visits)}</div>
                      <div>С целью: {fmtInt(p.goal_visits)} ({p.goal_pct}%)</div>
                    </div>
                  );
                }} />
              <Scatter data={f.top_landings} fill={GOLD} fillOpacity={0.55} />
            </ScatterChart>
          </ResponsiveContainer>
        ) : <Empty />}
      </Card>
    </div>
  );
}

function RetentionTab({ d }) {
  const r = d.retention || {};
  const cohorts = useMemo(() => r.cohorts || [], [r.cohorts]);
  // Кривая удержания: средний % возврата по смещению недель.
  const curve = useMemo(() => {
    const acc = {};
    for (const c of cohorts) {
      for (let i = 1; i <= 8; i += 1) {
        const v = c.week_plus?.[String(i)] || 0;
        if (!acc[i]) acc[i] = { ret: 0, size: 0 };
        acc[i].ret += v; acc[i].size += c.size;
      }
    }
    return Array.from({ length: 8 }, (_, i) => {
      const k = i + 1; const a = acc[k] || { ret: 0, size: 0 };
      return { week: `+${k}`, pct: a.size ? Math.round(a.ret / a.size * 1000) / 10 : 0 };
    });
  }, [cohorts]);
  const weekCols = ['+1', '+2', '+3', '+4', '+5', '+6', '+7', '+8'];

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <Kpi label="Уникальных посетителей" value={fmtInt(r.unique_visitors)} sub="вся история" />
        <Kpi label="Вернувшиеся (2+ недели)" value={fmtInt(r.returning_visitors)} color={GREEN} />
        <Kpi label="Доля возвратов" value={fmtPct(r.returning_pct)} color={GOLD} />
      </div>
      <Card title="Кривая удержания" icon={TrendingUp} insight="Средний по когортам процент вернувшихся через N недель после первого визита. Пологий хвост = растёт лояльная аудитория.">
        <ResponsiveContainer width="100%" height={220}>
          <ComposedChart data={curve} margin={{ top: 6, right: 12, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="gRet" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={GOLD} stopOpacity={0.25} />
                <stop offset="100%" stopColor={GOLD} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
            <XAxis dataKey="week" tick={{ fontSize: 11, fill: 'rgba(26,26,46,0.5)' }} />
            <YAxis unit="%" tick={{ fontSize: 11, fill: 'rgba(26,26,46,0.5)' }} width={40} />
            <Tooltip {...TT_STYLE} formatter={(v) => [`${v}%`, 'возврат']} />
            <Area type="monotone" dataKey="pct" stroke={GOLD} fill="url(#gRet)" strokeWidth={2} />
          </ComposedChart>
        </ResponsiveContainer>
      </Card>
      <Card title="Когорты по неделе первого визита" icon={Users} insight="Строка — когорта, столбец — недели спустя. Насыщенность клетки = доля вернувшихся. Тёплая диагональ вправо = удержание держится.">
        {cohorts.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="text-left text-text-tertiary border-b border-border-subtle">
                  <th className="py-1.5 pr-3 font-medium">Когорта</th>
                  <th className="py-1.5 pr-3 font-medium">Размер</th>
                  {weekCols.map((w) => <th key={w} className="py-1.5 pr-2 font-medium text-center">{w}</th>)}
                </tr>
              </thead>
              <tbody>
                {cohorts.map((c) => (
                  <tr key={c.cohort_week} className="border-b border-border-subtle/50 last:border-0">
                    <td className="py-1.5 pr-3 text-text-primary tabular-nums">{c.cohort_week}</td>
                    <td className="py-1.5 pr-3 text-text-secondary tabular-nums">{fmtInt(c.size)}</td>
                    {weekCols.map((w, i) => {
                      const v = c.week_plus?.[String(i + 1)] || 0;
                      const pct = c.size ? v / c.size : 0;
                      return (
                        <td key={w} className="py-1 pr-2 text-center">
                          <span
                            className="inline-block min-w-9 rounded px-1.5 py-0.5 text-[12px] tabular-nums"
                            style={{ background: `rgba(184,148,47,${Math.min(0.85, pct * 2 + (v ? 0.08 : 0))})`, color: pct > 0.25 ? '#fff' : 'rgba(26,26,46,0.7)' }}
                            title={`${Math.round(pct * 100)}%`}
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
        ) : <Empty />}
      </Card>
    </div>
  );
}

function PagesTab({ d }) {
  const pages = (d.pages || []).map((p) => ({
    ...p,
    dwell: p.avg_dwell_sec ?? 0,
    problems: (p.dead_clicks || 0) + (p.rage_clicks || 0),
  }));
  const medViews = median(pages.map((p) => p.pageviews));
  const medDwell = median(pages.filter((p) => p.dwell > 0).map((p) => p.dwell));
  const problem = pages.filter((p) => p.problems > 0)
    .sort((a, b) => b.problems - a.problems).slice(0, 10)
    .map((p) => ({ name: p.page, value: p.problems }));

  return (
    <div className="space-y-5">
      <Card title="Карта качества страниц: просмотры × вовлечённость" icon={Activity}
        insight="X — просмотры, Y — среднее время на странице. Правый низ (много просмотров, мало времени) — «тонкие» популярные страницы, кандидаты на доработку. Пунктир — медианы.">
        {pages.length ? (
          <ResponsiveContainer width="100%" height={340}>
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
                      <div>Время: {p.avg_dwell_sec ?? '—'} с · скролл {p.avg_scroll_pct ?? '—'}%</div>
                      <div>Dead: {fmtInt(p.dead_clicks)} · Rage: {fmtInt(p.rage_clicks)} · отказы {p.bounce_pct ?? '—'}%</div>
                    </div>
                  );
                }} />
              <Scatter data={pages} fill={GOLD} fillOpacity={0.5} />
            </ScatterChart>
          </ResponsiveContainer>
        ) : <Empty />}
      </Card>
      <Card title="Страницы с проблемными кликами (dead + rage)" icon={AlertTriangle} insight="Где пользователи кликают впустую или в раздражении — прямые кандидаты на UX-фикс.">
        <HBars data={problem} color={RED} />
      </Card>
    </div>
  );
}

function DemandTab({ d }) {
  const dem = d.demand || {};
  const s = d.onsite_search || {};
  const wm = (dem.webmaster_queries || []).filter((q) => q.impressions > 0 && q.avg_position != null);

  return (
    <div className="space-y-5">
      <Card title="SEO-карта возможностей: показы × позиция" icon={Search}
        insight="X — показы в Яндексе, Y — средняя позиция (выше = лучше, ось перевёрнута), размер — клики. Правый низ (много показов, но позиция слабая) — запросы с наибольшим потенциалом роста.">
        {wm.length ? (
          <ResponsiveContainer width="100%" height={340}>
            <ScatterChart margin={{ top: 10, right: 20, bottom: 20, left: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
              <XAxis type="number" dataKey="impressions" name="Показы" tick={{ fontSize: 11, fill: 'rgba(26,26,46,0.5)' }}
                label={{ value: 'показы', position: 'insideBottom', offset: -8, fontSize: 11, fill: 'rgba(26,26,46,0.5)' }} />
              <YAxis type="number" dataKey="avg_position" name="Позиция" reversed tick={{ fontSize: 11, fill: 'rgba(26,26,46,0.5)' }} width={40} />
              <ZAxis type="number" dataKey="clicks" range={[50, 480]} name="Клики" />
              <ReferenceLine y={10} stroke="rgba(22,163,74,0.4)" strokeDasharray="4 4" label={{ value: 'топ-10', fontSize: 10, fill: 'rgba(22,163,74,0.7)', position: 'insideTopLeft' }} />
              <Tooltip {...TT_STYLE} cursor={{ strokeDasharray: '3 3' }}
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const p = payload[0].payload;
                  return (
                    <div style={TT_STYLE.contentStyle}>
                      <div style={{ fontWeight: 600, marginBottom: 2 }}>{p.query}</div>
                      <div>Показы: {fmtInt(p.impressions)} · клики: {fmtInt(p.clicks)}</div>
                      <div>Ср. позиция: {p.avg_position}</div>
                    </div>
                  );
                }} />
              <Scatter data={wm} fill={BLUE} fillOpacity={0.55} />
            </ScatterChart>
          </ResponsiveContainer>
        ) : <p className="text-[13px] text-text-tertiary py-6 text-center">Данных Вебмастера за период нет.</p>}
      </Card>
      <div className="grid lg:grid-cols-2 gap-5">
        <Card title="Поиски на сайте без результата" icon={AlertTriangle} insight="Прямая карта пробелов каталога: что люди ищут, но не находят.">
          <HBars data={dictToBars(s.zero_results, 12)} color={RED} />
        </Card>
        <Card title="Фразы прихода из поиска (Метрика)" icon={Search} insight="Реальный органический спрос, приведший визиты.">
          <HBars data={(dem.metrika_phrases || []).slice(0, 12).map((p) => ({ name: p.phrase, value: p.visits }))} color={GREEN} />
        </Card>
      </div>
      <Card title="Внутренние поиски по полям сайта" icon={Search} span="lg:col-span-2" insight="Что ищут в каждом поле — по контекстам (глобальный ⌘K, карта, регионы, сравнение).">
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {Object.entries(s.by_context || {}).map(([ctx, counter]) => (
            <div key={ctx}>
              <div className="text-[12px] font-medium text-text-secondary mb-2">{ctx}</div>
              <HBars data={dictToBars(counter, 6)} height={Math.max(90, Object.keys(counter).length * 26)} />
            </div>
          ))}
          {!Object.keys(s.by_context || {}).length && <Empty />}
        </div>
      </Card>
    </div>
  );
}

// Узел Sankey с подписью страницы.
function SankeyNode({ x, y, width, height, index, payload, containerWidth }) {
  if (x == null || y == null) return null;
  const isLeft = x < (containerWidth || 480) / 2;
  const name = payload?.name ?? '';
  return (
    <Layer key={`n-${index}`}>
      <Rectangle x={x} y={y} width={width} height={height} fill={GOLD} fillOpacity={0.85} radius={2} />
      <text
        x={isLeft ? x + width + 6 : x - 6} y={y + height / 2}
        textAnchor={isLeft ? 'start' : 'end'} dominantBaseline="middle"
        fontSize={11} fill="rgba(26,26,46,0.75)"
      >
        {clip(name, 22)}
      </text>
    </Layer>
  );
}

function NavigationTab({ d }) {
  const n = d.navigation || {};
  const transitions = (n.top_transitions || []).slice(0, 14);
  const sankey = useMemo(() => {
    if (!transitions.length) return null;
    const names = [];
    const idx = (name) => {
      let i = names.indexOf(name);
      if (i === -1) { i = names.length; names.push(name); }
      return i;
    };
    const links = transitions.map((t) => ({ source: idx(t.from), target: idx(t.to), value: t.count }));
    // Sankey не терпит циклов source==target — отфильтруем.
    const clean = links.filter((l) => l.source !== l.target);
    if (names.length < 2 || !clean.length) return null;
    return { nodes: names.map((name) => ({ name })), links: clean };
  }, [transitions]);

  return (
    <div className="space-y-5">
      <Card title="Граф навигации: как перетекает трафик между страницами" icon={Route}
        insight="Толщина потока — число переходов. Видны магистрали сайта и куда ведёт каждая ключевая страница.">
        {sankey ? (
          <ResponsiveContainer width="100%" height={Math.max(320, sankey.nodes.length * 26)}>
            <Sankey
              data={sankey}
              node={<SankeyNode />}
              link={{ stroke: GOLD, strokeOpacity: 0.18 }}
              nodePadding={22} nodeWidth={10}
              margin={{ top: 10, right: 160, bottom: 10, left: 20 }}
            >
              <Tooltip {...TT_STYLE} formatter={(v) => [fmtInt(v), 'переходов']} />
            </Sankey>
          </ResponsiveContainer>
        ) : <Empty />}
      </Card>
      <div className="grid lg:grid-cols-2 gap-5">
        <Card title="Точки входа" icon={LogIn} insight="С каких страниц начинаются сессии.">
          <HBars data={dictToBars(n.top_entries, 10)} color={GREEN} />
        </Card>
        <Card title="Точки выхода (тупики)" icon={Route} insight="Где сессии обрываются — кандидаты на усиление перелинковки.">
          <HBars data={dictToBars(n.top_exits, 10)} color={RED} />
        </Card>
      </div>
    </div>
  );
}

function EventsTab({ d }) {
  const rows = Object.entries(d.events || {})
    .map(([name, v]) => ({ name, authed: v.authed, guest: v.guest, total: v.total }))
    .sort((a, b) => b.total - a.total).slice(0, 22);
  return (
    <Card title="Бизнес-события: гость и зарегистрированный" icon={Activity}
      insight="Каждый бар — событие; сегменты — доля зарегистрированных (тёмное) и гостей. Видно, какие действия драйвят авторизованные пользователи.">
      {rows.length ? (
        <ResponsiveContainer width="100%" height={Math.max(260, rows.length * 26)}>
          <BarChart layout="vertical" data={rows} margin={{ top: 2, right: 48, bottom: 2, left: 4 }}>
            <XAxis type="number" hide />
            <YAxis type="category" dataKey="name" width={168} tick={{ fontSize: 11, fill: 'rgba(26,26,46,0.72)' }} tickFormatter={(v) => clip(v, 26)} interval={0} />
            <Tooltip {...TT_STYLE} formatter={(v, n) => [fmtInt(v), n === 'authed' ? 'Зарегистрированные' : 'Гости']} />
            <Legend wrapperStyle={{ fontSize: 11 }} formatter={(v) => (v === 'authed' ? 'Зарегистрированные' : 'Гости')} />
            <Bar dataKey="authed" name="authed" stackId="e" fill={INK} maxBarSize={20} radius={[0, 0, 0, 0]} />
            <Bar dataKey="guest" name="guest" stackId="e" fill={GOLD} maxBarSize={20} radius={[0, 4, 4, 0]}>
              <LabelList dataKey="total" position="right" formatter={fmtInt} style={{ fontSize: 10.5, fill: 'rgba(26,26,46,0.6)' }} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      ) : <Empty />}
    </Card>
  );
}

function HypothesesTab({ d }) {
  const rows = d.hypotheses || [];
  if (!rows.length) {
    return <Card title="Гипотезы Пульс-аналитика" icon={Brain}><p className="text-[13px] text-text-tertiary">Гипотез пока нет — Пульс пишет их ежедневно после утреннего отчёта.</p></Card>;
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

function DatasetTab({ d }) {
  const inv = d.dataset || {};
  const sections = inv.sections || inv;
  return (
    <Card title="Инвентаризация датасета: все собираемые слои" icon={Database} insight="Что и в каком объёме копится — основа для ML и глубокой аналитики.">
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {Object.entries(sections).map(([name, s]) => {
          if (typeof s !== 'object' || s == null) return null;
          return (
            <div key={name} className="rounded-xl border border-border-subtle p-3.5">
              <div className="text-[13px] font-semibold text-text-primary mb-1.5">{s.title || name}</div>
              <ul className="text-[12px] text-text-secondary space-y-0.5">
                {Object.entries(s).map(([k, v]) => {
                  if (k === 'title' || typeof v === 'object') return null;
                  return <li key={k}><span className="text-text-tertiary">{k}:</span> {typeof v === 'number' ? fmtInt(v) : String(v)}</li>;
                })}
              </ul>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

function median(arr) {
  const a = (arr || []).filter((v) => v != null && Number.isFinite(v)).sort((x, y) => x - y);
  if (!a.length) return 0;
  const mid = Math.floor(a.length / 2);
  return a.length % 2 ? a[mid] : (a[mid - 1] + a[mid]) / 2;
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
    <div className="min-h-[60vh] flex items-center justify-center px-4">
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
  { id: 'funnel', label: 'Воронка', icon: Filter, C: FunnelTab },
  { id: 'retention', label: 'Retention', icon: Users, C: RetentionTab },
  { id: 'pages', label: 'Страницы', icon: Route, C: PagesTab },
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
    <div className="max-w-[1400px] mx-auto px-4 sm:px-6 py-6">
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
