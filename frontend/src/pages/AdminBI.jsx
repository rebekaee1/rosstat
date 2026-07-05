// Админ-BI /admin/bi (директива владельца 2026-07-05): полная картина
// платформы для стратегических решений — KPI, привлечение, воронка,
// retention-когорты, качество страниц, спрос vs покрытие, внутренние поиски,
// граф навигации, проблемные элементы, гипотезы Пульса, инвентаризация
// датасета. Обычный пользователь раздела не видит: backend отвечает 404
// всем, кроме settings.admin_emails; страница вне навигации и вне sitemap.
// Данные самообновляются: Redis-кэш 15 минут + refetchInterval 15 минут.
import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  ResponsiveContainer, ComposedChart, Line, Area, Bar, XAxis, YAxis,
  Tooltip, CartesianGrid, Legend,
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
  internal: 'Внутренние',
  recommend: 'Рекомендательные',
  social: 'Соцсети',
  unknown: 'Не определён',
};

const fmtInt = (n) => (n == null ? '—' : Number(n).toLocaleString('ru-RU'));
const fmtPct = (n) => (n == null ? '—' : `${Number(n).toLocaleString('ru-RU')}%`);

function fetchDashboard(days) {
  return api.get(`/admin/bi/dashboard?days=${days}`).then((r) => r.data);
}

/* ---------- Примитивы ---------- */

function Card({ title, icon: Icon, children, span }) {
  return (
    <section className={`rounded-2xl bg-surface border border-border-subtle p-5 ${span || ''}`}>
      <h2 className="flex items-center gap-2 text-[15px] font-semibold text-text-primary mb-4">
        {Icon && <Icon size={16} className="text-champagne" />}
        {title}
      </h2>
      {children}
    </section>
  );
}

function Kpi({ label, value, sub }) {
  return (
    <div className="rounded-xl bg-surface border border-border-subtle px-4 py-3">
      <div className="text-[12px] text-text-tertiary">{label}</div>
      <div className="text-xl font-bold text-text-primary tabular-nums">{value}</div>
      {sub && <div className="text-[11px] text-text-tertiary mt-0.5">{sub}</div>}
    </div>
  );
}

function DataTable({ head, rows, empty = 'Нет данных за период' }) {
  if (!rows?.length) return <p className="text-[13px] text-text-tertiary">{empty}</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[13px]">
        <thead>
          <tr className="text-left text-text-tertiary border-b border-border-subtle">
            {head.map((h) => <th key={h} className="py-1.5 pr-3 font-medium whitespace-nowrap">{h}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((cells, i) => (
            <tr key={i} className="border-b border-border-subtle/50 last:border-0">
              {cells.map((c, j) => (
                <td key={j} className={`py-1.5 pr-3 ${j === 0 ? 'text-text-primary' : 'text-text-secondary tabular-nums'}`}>{c}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CounterList({ data, unit = '' }) {
  const entries = Object.entries(data || {});
  if (!entries.length) return <p className="text-[13px] text-text-tertiary">Нет данных за период</p>;
  const max = Math.max(...entries.map(([, v]) => v));
  return (
    <ul className="space-y-1.5">
      {entries.map(([k, v]) => (
        <li key={k} className="flex items-center gap-2">
          <span className="flex-1 min-w-0 truncate text-[13px] text-text-primary" title={k}>{k}</span>
          <span className="relative h-2 w-24 rounded-full bg-obsidian-light overflow-hidden shrink-0">
            <span className="absolute inset-y-0 left-0 rounded-full bg-champagne/70" style={{ width: `${(v / max) * 100}%` }} />
          </span>
          <span className="w-14 text-right text-[12px] text-text-secondary tabular-nums shrink-0">{fmtInt(v)}{unit}</span>
        </li>
      ))}
    </ul>
  );
}

/* ---------- Секции ---------- */

function OverviewTab({ d }) {
  const totals = useMemo(() => {
    const t = { visits: 0, visitors: 0, ad: 0, reg: 0, dl: 0, err: 0, ev: 0, srch: 0 };
    for (const r of d.kpi_daily || []) {
      t.visits += r.visits; t.visitors += r.visitors; t.ad += r.ad_visits;
      t.reg += r.registrations; t.dl += r.downloads; t.err += r.errors;
      t.ev += r.events; t.srch += r.searches;
    }
    return t;
  }, [d]);

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">
        <Kpi label="Визиты" value={fmtInt(totals.visits)} />
        <Kpi label="Посетители·дни" value={fmtInt(totals.visitors)} />
        <Kpi label="Из рекламы" value={fmtInt(totals.ad)} sub={totals.visits ? fmtPct(Math.round(totals.ad / totals.visits * 100)) : null} />
        <Kpi label="Регистрации" value={fmtInt(totals.reg)} sub={`всего ${fmtInt(d.users?.total)}`} />
        <Kpi label="Скачивания" value={fmtInt(totals.dl)} />
        <Kpi label="События" value={fmtInt(totals.ev)} />
        <Kpi label="Поиски на сайте" value={fmtInt(totals.srch)} />
        <Kpi label="Ошибки фронта" value={fmtInt(totals.err)} />
      </div>

      <Card title="Трафик по дням" icon={Activity}>
        <ResponsiveContainer width="100%" height={260}>
          <ComposedChart data={d.kpi_daily || []} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
            <XAxis dataKey="date" tick={{ fontSize: 11, fill: 'rgba(26,26,46,0.5)' }} tickFormatter={(v) => v.slice(5)} />
            <YAxis tick={{ fontSize: 11, fill: 'rgba(26,26,46,0.5)' }} width={40} />
            <Tooltip />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Area type="monotone" dataKey="visits" name="Визиты" stroke={GOLD} fill="rgba(184,148,47,0.14)" strokeWidth={2} />
            <Line type="monotone" dataKey="visitors" name="Посетители" stroke={INK} strokeWidth={1.6} dot={false} />
            <Line type="monotone" dataKey="ad_visits" name="Из рекламы" stroke={BLUE} strokeWidth={1.4} dot={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </Card>

      <div className="grid lg:grid-cols-2 gap-5">
        <Card title="Конверсии по дням" icon={TrendingUp}>
          <ResponsiveContainer width="100%" height={220}>
            <ComposedChart data={d.kpi_daily || []}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: 'rgba(26,26,46,0.5)' }} tickFormatter={(v) => v.slice(5)} />
              <YAxis tick={{ fontSize: 11, fill: 'rgba(26,26,46,0.5)' }} width={30} allowDecimals={false} />
              <Tooltip />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="registrations" name="Регистрации" fill={GREEN} radius={[3, 3, 0, 0]} />
              <Bar dataKey="downloads" name="Скачивания" fill={PURPLE} radius={[3, 3, 0, 0]} />
            </ComposedChart>
          </ResponsiveContainer>
        </Card>
        <Card title="Активность и ошибки по дням" icon={AlertTriangle}>
          <ResponsiveContainer width="100%" height={220}>
            <ComposedChart data={d.kpi_daily || []}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: 'rgba(26,26,46,0.5)' }} tickFormatter={(v) => v.slice(5)} />
              <YAxis tick={{ fontSize: 11, fill: 'rgba(26,26,46,0.5)' }} width={44} />
              <Tooltip />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line type="monotone" dataKey="events" name="События" stroke={GOLD} strokeWidth={1.6} dot={false} />
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
  const sourceRows = Object.entries(a.sources || {}).map(([k, v]) => [SOURCE_RU[k] || k, fmtInt(v)]);
  return (
    <div className="grid lg:grid-cols-2 gap-5">
      <Card title="Источники трафика" icon={Megaphone}>
        <DataTable head={['Источник', 'Визиты']} rows={sourceRows} />
      </Card>
      <Card title="Поисковики" icon={Search}>
        <CounterList data={a.search_engines} />
      </Card>
      <Card title="Кампании Директа" icon={Megaphone} span="lg:col-span-2">
        <DataTable
          head={['Кампания', 'Визиты', 'С целями', 'Конверсия', 'Отказы', 'Ср. время', 'Расход']}
          rows={(a.ad_campaigns || []).map((c) => [
            c.campaign, fmtInt(c.visits), fmtInt(c.goal_visits), fmtPct(c.goal_rate_pct),
            fmtPct(c.bounce_pct), `${c.avg_duration_sec} с`,
            c.cost == null ? 'нужен коннектор Директа' : fmtInt(c.cost),
          ])}
        />
      </Card>
      <Card title="Поисковые фразы (пришли из поиска)" icon={Search}>
        <CounterList data={a.top_phrases} />
      </Card>
      <div className="space-y-5">
        <Card title="География (города)" icon={Users}>
          <CounterList data={a.top_cities} />
        </Card>
        <Card title="Устройства" icon={Users}>
          <CounterList data={a.devices} />
        </Card>
      </div>
    </div>
  );
}

function FunnelTab({ d }) {
  const f = d.funnel || {};
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <Kpi label="Регистраций за период" value={fmtInt(f.registrations_total)} />
        <Kpi label="Каналов" value={fmtInt((f.by_source || []).length)} />
        <Kpi label="Посадочных страниц" value={fmtInt((f.top_landings || []).length)} />
      </div>
      <Card title="Воронка по каналам: визит → вовлечение → цель" icon={Filter}>
        <DataTable
          head={['Канал', 'Визиты', 'Вовлечённые (>1 стр. или 30с)', '%', 'Достигли цели', '%']}
          rows={(f.by_source || []).map((s) => [
            SOURCE_RU[s.source] || s.source, fmtInt(s.visits),
            fmtInt(s.engaged), fmtPct(s.engaged_pct),
            fmtInt(s.goal_visits), fmtPct(s.goal_pct),
          ])}
        />
        <p className="text-[12px] text-text-tertiary mt-3">
          Цели — из Метрики (goals визита). Регистрации указаны сквозно: точной склейки
          «визит → аккаунт» у Метрики нет, сопоставляйте динамику по дням на вкладке «Обзор».
        </p>
      </Card>
      <Card title="Посадочные страницы: куда приходят и где конвертируются" icon={Route}>
        <DataTable
          head={['Страница входа', 'Визиты', 'С целями', 'Конверсия']}
          rows={(f.top_landings || []).map((l) => [
            l.page, fmtInt(l.visits), fmtInt(l.goal_visits), fmtPct(l.goal_pct),
          ])}
        />
      </Card>
    </div>
  );
}

function RetentionTab({ d }) {
  const r = d.retention || {};
  const weekCols = ['+1', '+2', '+3', '+4', '+5', '+6', '+7', '+8'];
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <Kpi label="Уникальных посетителей (вся история)" value={fmtInt(r.unique_visitors)} />
        <Kpi label="Вернувшиеся (2+ недели)" value={fmtInt(r.returning_visitors)} />
        <Kpi label="Доля возвратов" value={fmtPct(r.returning_pct)} />
      </div>
      <Card title="Когорты по неделе первого визита: возвраты через N недель" icon={Users}>
        <div className="overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead>
              <tr className="text-left text-text-tertiary border-b border-border-subtle">
                <th className="py-1.5 pr-3 font-medium">Когорта (неделя)</th>
                <th className="py-1.5 pr-3 font-medium">Размер</th>
                {weekCols.map((w) => <th key={w} className="py-1.5 pr-2 font-medium">{w}</th>)}
              </tr>
            </thead>
            <tbody>
              {(r.cohorts || []).map((c) => (
                <tr key={c.cohort_week} className="border-b border-border-subtle/50 last:border-0">
                  <td className="py-1.5 pr-3 text-text-primary">{c.cohort_week}</td>
                  <td className="py-1.5 pr-3 text-text-secondary tabular-nums">{fmtInt(c.size)}</td>
                  {weekCols.map((w, i) => {
                    const v = c.week_plus?.[String(i + 1)] || 0;
                    const pct = c.size ? v / c.size : 0;
                    return (
                      <td key={w} className="py-1 pr-2">
                        <span
                          className="inline-block min-w-9 rounded px-1.5 py-0.5 text-center text-[12px] tabular-nums"
                          style={{ background: `rgba(184,148,47,${Math.min(0.85, pct * 2 + (v ? 0.08 : 0))})`, color: pct > 0.25 ? '#fff' : 'rgba(26,26,46,0.7)' }}
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
      </Card>
    </div>
  );
}

function PagesTab({ d }) {
  return (
    <Card title="Качество страниц: просмотры · время · скролл · мёртвые клики · отказы" icon={Activity}>
      <DataTable
        head={['Страница', 'Просмотры', 'Ср. время, с', 'Скролл, %', 'Dead-клики', 'Rage-клики', 'Отказы, %']}
        rows={(d.pages || []).map((p) => [
          p.page, fmtInt(p.pageviews),
          p.avg_dwell_sec ?? '—', p.avg_scroll_pct ?? '—',
          fmtInt(p.dead_clicks), fmtInt(p.rage_clicks),
          p.bounce_pct ?? '—',
        ])}
      />
    </Card>
  );
}

function DemandTab({ d }) {
  const dem = d.demand || {};
  const s = d.onsite_search || {};
  return (
    <div className="grid lg:grid-cols-2 gap-5">
      <Card title="Запросы из Яндекса (Вебмастер): показы · клики · позиция" icon={Search} span="lg:col-span-2">
        <DataTable
          head={['Запрос', 'Показы', 'Клики', 'Ср. позиция']}
          rows={(dem.webmaster_queries || []).map((q) => [
            q.query, fmtInt(q.impressions), fmtInt(q.clicks), q.avg_position ?? '—',
          ])}
        />
      </Card>
      <Card title="Фразы, с которых пришли (Метрика)" icon={Search}>
        <DataTable
          head={['Фраза', 'Визиты']}
          rows={(dem.metrika_phrases || []).map((p) => [p.phrase, fmtInt(p.visits)])}
        />
      </Card>
      <Card title="Поиски на сайте без результата — пробелы каталога" icon={AlertTriangle}>
        <CounterList data={s.zero_results} />
      </Card>
      <Card title="Внутренние поиски по полям" icon={Search} span="lg:col-span-2">
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Object.entries(s.by_context || {}).map(([ctx, counter]) => (
            <div key={ctx}>
              <div className="text-[12px] font-medium text-text-secondary mb-2">{ctx}</div>
              <CounterList data={counter} />
            </div>
          ))}
          {!Object.keys(s.by_context || {}).length && (
            <p className="text-[13px] text-text-tertiary">Нет данных за период</p>
          )}
        </div>
      </Card>
    </div>
  );
}

function NavigationTab({ d }) {
  const n = d.navigation || {};
  const b = d.behavior_issues || {};
  return (
    <div className="grid lg:grid-cols-2 gap-5">
      <Card title="Топ переходов между страницами" icon={Route} span="lg:col-span-2">
        <DataTable
          head={['Откуда', 'Куда', 'Переходов']}
          rows={(n.top_transitions || []).map((t) => [t.from, t.to, fmtInt(t.count)])}
        />
      </Card>
      <Card title="Точки входа" icon={LogIn}>
        <CounterList data={n.top_entries} />
      </Card>
      <Card title="Точки выхода (тупики)" icon={Route}>
        <CounterList data={n.top_exits} />
      </Card>
      <Card title="Dead-клики: не реагирующие элементы" icon={MousePointerClick}>
        <DataTable
          head={['Страница', 'Элемент', 'Кликов']}
          rows={(b.dead || []).map((x) => [x.page, x.element, fmtInt(x.count)])}
        />
      </Card>
      <Card title="Rage-клики: злые серии" icon={MousePointerClick}>
        <DataTable
          head={['Страница', 'Элемент', 'Кликов']}
          rows={(b.rage || []).map((x) => [x.page, x.element, fmtInt(x.count)])}
        />
      </Card>
    </div>
  );
}

function EventsTab({ d }) {
  const rows = Object.entries(d.events || {});
  return (
    <Card title="Все бизнес-события за период: гость vs зарегистрированный" icon={Activity}>
      <DataTable
        head={['Событие', 'Всего', 'Зарегистрированные', 'Гости']}
        rows={rows.map(([name, v]) => [name, fmtInt(v.total), fmtInt(v.authed), fmtInt(v.guest)])}
      />
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
    <Card title="Инвентаризация датасета: все собираемые слои" icon={Database}>
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
    // Владелец: самообновление раз в 15 минут (бэкенд держит Redis-кэш 15 мин).
    refetchInterval: 15 * 60 * 1000,
    staleTime: 14 * 60 * 1000,
    retry: 1,
  });

  if (isLoading) return null;
  if (!isAuthed) return <AdminLogin onSuccess={setUser} />;
  if (!isAdmin) {
    // Для обычного пользователя раздел не существует.
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
