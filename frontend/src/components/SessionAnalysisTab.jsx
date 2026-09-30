import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import api from '../lib/api';

const BASE = '/admin/bi/session-analysis';
const box = 'rounded-xl border border-border-subtle bg-surface p-4';
const button = 'rounded-lg border border-border-subtle px-3 py-2 text-sm hover:bg-champagne/10 disabled:opacity-40';
const visualLabels = { not_reviewed: 'Запись не просмотрена', dom_only: 'Есть состояния DOM, пиксельного просмотра нет', partial: 'Просмотрена часть записи', reviewed: 'Запись просмотрена полностью' };
const gapLabels = { not_captured_or_expired: 'Запись не собрана или истёк срок хранения', missing_sequence: 'Не доставлен участок записи', missing_fragment: 'Не доставлена часть пакета', end_not_received: 'Завершение записи не доставлено', missing_full_snapshot: 'Нет начального состояния страницы', client_dropped_events: 'Часть событий потеряна на устройстве', invalid_payload: 'Повреждённый участок записи', server_read_byte_limit: 'Достигнут лимит размера чтения', server_read_row_limit: 'Достигнут лимит количества пакетов' };
const gapLabel = gap => gapLabels[gap?.reason] || 'Часть записи недоступна';
const aiLabels = { disabled: 'выключен', not_configured: 'не настроен', generated: 'гипотезы сформированы', invalid: 'ответ отклонён', failed: 'ответ не получен', skipped_input_budget: 'сводка превышает лимит модели, факты сохранены' };
const time = ms => `${(Math.max(0, ms || 0) / 1000).toFixed(1)} с`;
async function get(path, params) { return (await api.get(BASE + path, { params })).data; }

function Findings({ title, items = [] }) {
  const [limit, setLimit] = useState(20);
  return <section className={box}>
    <h3 className="font-semibold mb-3">{title} — {items.length}</h3>
    {!items.length && <p className="text-sm text-text-tertiary">Нет зарегистрированных выводов.</p>}
    <ul className="space-y-3 text-sm">
      {items.slice(0, limit).map((item, index) => <li key={item.id || item.code || index}>
        <p>{item.text}</p>
        {item.verification && <p className="text-text-secondary mt-1">Проверка: {item.verification}</p>}
        {!!item.evidence_ids?.length && <div className="flex flex-wrap gap-2 mt-1">
          {item.evidence_ids.map(id => <a key={id} className="text-champagne underline break-all" href={`#evidence-${id}`}>{id}</a>)}
        </div>}
      </li>)}
    </ul>
    {limit < items.length && <button type="button" className={button + ' mt-3'} onClick={() => setLimit(n => n + 50)}>Показать ещё — осталось {items.length - limit}</button>}
  </section>;
}

function ReplayPlayer({ sessionId }) {
  const query = useQuery({ queryKey: ['session-replay', sessionId], queryFn: () => get(`/sessions/${sessionId}/replay`), retry: 1 });
  const [index, setIndex] = useState(0);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState('');
  const [ready, setReady] = useState(false);
  const [playing, setPlaying] = useState(false);
  const root = useRef(null);
  const player = useRef(null);
  const recording = query.data?.recordings?.[index];
  useEffect(() => {
    let disposed = false;
    setReady(false);
    setPlaying(false);
    setOffset(0);
    setError('');
    if (!root.current || !recording?.events?.length || !recording.full_snapshots) return;
    Promise.all([import('@rrweb/replay'), import('@rrweb/replay/dist/style.css')]).then(([{ Replayer }]) => {
      if (disposed) return;
      player.current = new Replayer(recording.events, { root: root.current, skipInactive: false,
        showWarning: false, showDebug: false, mouseTail: false, blockClass: 'rr-block', insertStyleRules: ['iframe { pointer-events: none; }'] });
      player.current.pause(0);
      setReady(true);
    }).catch(() => { if (!disposed) setError('Не удалось воспроизвести структуру записи. События доступны ниже.'); });
    return () => { disposed = true; player.current?.destroy(); player.current = null; };
  }, [recording]);
  useEffect(() => {
    if (!playing) return;
    const timer = setInterval(() => {
      const at = player.current?.getCurrentTime();
      if (Number.isFinite(at)) setOffset(Math.min(at, recording.duration_ms));
      if (at >= recording.duration_ms) setPlaying(false);
    }, 200);
    return () => clearInterval(timer);
  }, [playing, recording]);
  return <section className={box}>
    <h3 className="font-semibold mb-2">Воспроизведение сессии</h3>
    <p className="text-sm text-text-secondary mb-3">Реконструкция DOM. Canvas-графики и сторонние ресурсы могут отсутствовать; точность пиксельного изображения не подтверждена.</p>
    {query.isLoading && <p>Загружаем запись…</p>}
    {query.isError && <p role="alert">Не удалось загрузить запись.</p>}
    {query.data && <>
      {!!query.data.gaps?.length && <p className="text-sm text-negative mb-3">Пропуски записи: {query.data.gaps.map(gapLabel).join('; ')}</p>}
      {!query.data.recordings?.length && <p className="text-sm">Собственная запись этой сессии отсутствует.</p>}
      {!!query.data.recordings?.length && <>
        <label className="text-sm">Страница записи
          <select aria-label="Страница записи" className="ml-2 rounded border border-border-subtle bg-surface px-2 py-1 max-w-full" value={index} onChange={e => { setIndex(Number(e.target.value)); setOffset(0); setError(''); }}>
            {query.data.recordings.map((r, i) => <option key={r.recording_id} value={i}>{i + 1}. {r.page} — {time(r.duration_ms)}</option>)}
          </select>
        </label>
        {recording && <div className="flex flex-wrap items-center gap-2 my-3">
          <button type="button" className={button} disabled={!ready || playing} onClick={() => { player.current?.play(offset); setPlaying(true); }}>Смотреть</button>
          <button type="button" className={button} disabled={!ready || !playing} onClick={() => { player.current?.pause(); setOffset(player.current?.getCurrentTime() || offset); setPlaying(false); }}>Пауза</button>
          <label className="flex items-center gap-2 text-sm flex-1 min-w-40">Перемотка
            <input aria-label="Время записи" type="range" min="0" max={Math.max(1, recording.duration_ms)} step="100" value={offset} disabled={!ready}
              onChange={e => { const at = Number(e.target.value); setOffset(at); player.current?.pause(at); setPlaying(false); }} />
            <span className="whitespace-nowrap">{time(offset)}</span>
          </label>
        </div>}
        {error && <p role="alert" className="text-negative text-sm">{error}</p>}
        <div className="overflow-auto max-h-[650px] rounded-lg border border-border-subtle bg-white" ref={root} />
      </>}
    </>}
  </section>;
}

function RawEvents({ sessionId }) {
  const [cursor, setCursor] = useState(null);
  const [source, setSource] = useState('behavior');
  const query = useQuery({ queryKey: ['session-raw-events', sessionId, source, cursor], queryFn: () => get(`/sessions/${sessionId}/events`, { source, cursor: cursor || undefined, limit: 100 }) });
  return <section className={box}>
    <h3 className="font-semibold mb-2">Все сохранённые события</h3>
    <label className="text-sm">Источник
      <select aria-label="Источник событий" className="ml-2 border border-border-subtle rounded bg-surface p-1" value={source} onChange={e => { setSource(e.target.value); setCursor(null); }}>
        <option value="behavior">Поведение и производительность</option>
        <option value="frontend">Бизнес-события</option>
      </select>
    </label>
    {query.data && <p className="text-sm text-text-secondary mb-3">Всего {query.data.total_captured_events}; эта страница содержит {query.data.items.length}. Поток доступен без выборки.</p>}
    {query.isError && <p role="alert">Не удалось загрузить события.</p>}
    <ol className="space-y-2 text-xs">
      {query.data?.items.map(e => <li key={e.id} className="scroll-mt-24 border-b border-border-subtle pb-2">
        <strong>{e.occurred_at ? new Date(e.occurred_at).toLocaleString('ru-RU', { timeZone: 'Europe/Moscow', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', fractionalSecondDigits: 3 }) + ' МСК' : 'Время неизвестно'} — {e.event_type}</strong> <span className="break-all">{e.page}</span>
        <pre className="whitespace-pre-wrap break-all text-text-secondary">{JSON.stringify(e, null, 2)}</pre>
      </li>)}
    </ol>
    <div className="flex gap-2 mt-3">
      <button type="button" className={button} disabled={!cursor} onClick={() => setCursor(null)}>К началу</button>
      <button type="button" className={button} disabled={!query.data?.has_more || query.isFetching} onClick={() => setCursor(query.data.next_cursor)}>Следующие события</button>
    </div>
  </section>;
}

function SessionDetail({ sessionId }) {
  const client = useQueryClient();
  const query = useQuery({ queryKey: ['session-report', sessionId], queryFn: () => get(`/sessions/${sessionId}/analysis`), retry: 1 });
  const report = query.data;
  if (query.isLoading) return <p>Собираем отчёт по сессии…</p>;
  if (query.isError) return <p role="alert">Не удалось собрать отчёт по сессии.</p>;
  if (!report) return null;
  return <div className="space-y-4">
    <div className={box}>
      <h2 className="text-lg font-semibold mb-2">Разбор сессии</h2>
      <p className="text-xs break-all text-text-tertiary">{sessionId}</p>
      <p className="text-sm mt-2">События: {report.coverage.analyzed_events} из {report.coverage.captured_events} — {report.coverage.captured_events === 0 ? 'поток событий отсутствует' : report.coverage.event_complete ? 'обработаны все сохранённые' : 'обработана часть сохранённых'}</p>
      <p className="text-sm">{visualLabels[report.coverage.visual.status] || report.coverage.visual.status}</p>
      <p className="text-sm text-text-secondary">Страниц: {report.metrics.pageviews} — наблюдаемый интервал: {time(report.metrics.observed_duration_ms)} — AI: {aiLabels[report.ai.status] || 'статус неизвестен'}</p>
      <p className="text-sm text-text-secondary mt-2">Полнота сбора всех посетителей, число физических людей и удовлетворённость по этой сессии не установлены.</p>
      <button type="button" className={button + ' mt-3'} disabled={query.isFetching} onClick={() => {
        void client.invalidateQueries({ queryKey: ['session-report', sessionId] });
        void client.invalidateQueries({ queryKey: ['session-replay', sessionId] });
        void client.invalidateQueries({ queryKey: ['session-raw-events', sessionId] });
      }}>Обновить разбор</button>
    </div>
    <ReplayPlayer sessionId={sessionId} />
    <div className="grid gap-4 lg:grid-cols-2">
      <Findings title="Факты" items={report.facts} />
      <Findings title="Гипотезы" items={report.inferences} />
      <Findings title="Что проверить и улучшить" items={report.recommendations} />
      <Findings title="Неизвестно" items={report.unknowns} />
    </div>
    <section className={box}>
      <h3 className="font-semibold mb-2">Доказательства отчёта — {report.evidence.length}</h3>
      <div className="max-h-96 overflow-auto space-y-2 text-xs">
        {report.evidence.map(e => <details key={e.id} id={`evidence-${e.id}`} className="scroll-mt-24">
          <summary className="cursor-pointer">{time(e.relative_ms ?? e.original_time_ms)} — {e.id} — {e.page}</summary>
          <pre className="whitespace-pre-wrap break-all">{JSON.stringify(e, null, 2)}</pre>
        </details>)}
      </div>
    </section>
    <RawEvents sessionId={sessionId} />
  </div>;
}

export default function SessionAnalysisTab({ period = 'today', dateFrom, dateTo }) {
  const [cursor, setCursor] = useState(null);
  const [selected, setSelected] = useState(null);
  const params = { period, from: dateFrom || undefined, to: dateTo || undefined };
  const list = useQuery({ queryKey: ['session-analysis-list', params, cursor], queryFn: () => get('/sessions', { ...params, cursor: cursor || undefined }), refetchInterval: cursor ? false : 60_000 });
  const summary = useQuery({ queryKey: ['session-analysis-summary', params], queryFn: () => get('/summary', params), refetchInterval: 60_000 });
  return <div className="space-y-4">
    <div className={box}>
      <h2 className="text-lg font-semibold">Сессии и качество разбора</h2>
      <p className="text-sm text-text-secondary mt-2">Охват — все сохранённые сессии своего счётчика за выбранный период. Отказ от аналитики, блокировки и потерянные события ограничивают сбор.</p>
      {summary.data && <p className="text-sm mt-2">Собрано: {summary.data.total_captured_sessions} — свежих разборов: {summary.data.analyzed_sessions} — ожидают: {summary.data.pending_or_missing_sessions} — просмотрено полностью: {summary.data.visual_reviewed_sessions}</p>}
      {summary.isError && <p role="alert">Сводка пока недоступна.</p>}
      {!!summary.data?.issues?.length && <ul className="mt-3 space-y-1 text-sm">
        {summary.data.issues.map(i => <li key={i.code}>{i.recommendation || i.code} — {i.affected_analyzed_sessions} из {i.denominator_analyzed_sessions} разобранных сессий.</li>)}
      </ul>}
    </div>
    <div className="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
      <aside className={box}>
        <h3 className="font-semibold mb-3">Сессии — {list.data?.total_captured_sessions ?? '…'}</h3>
        {list.isError && <p role="alert">Не удалось загрузить список сессий.</p>}
        {list.data && !list.data.items.length && <p className="text-sm">За этот период сохранённых сессий нет.</p>}
        <ul className="space-y-2">
          {list.data?.items.map(s => <li key={s.session_id}>
            <button type="button" className={button + ' w-full text-left ' + (selected === s.session_id ? 'bg-champagne/10' : '')} onClick={() => setSelected(s.session_id)}>
              <span className="block">{new Date(s.first_at).toLocaleString('ru-RU', { timeZone: 'Europe/Moscow' })} МСК</span>
              <span className="text-xs text-text-secondary">{s.device_type || 'Устройство неизвестно'} — {s.browser || 'браузер неизвестен'} — {s.event_count} событий</span>
            </button>
          </li>)}
        </ul>
        <div className="flex gap-2 mt-3">
          <button type="button" className={button} disabled={!cursor} onClick={() => setCursor(null)}>К началу</button>
          <button type="button" className={button} disabled={!list.data?.has_more || list.isFetching} onClick={() => setCursor(list.data.next_cursor)}>Далее</button>
        </div>
      </aside>
      {selected ? <SessionDetail key={selected} sessionId={selected} /> : <p className="text-sm text-text-tertiary p-4">Выберите сессию для отчёта, записи и полного потока событий.</p>}
    </div>
  </div>;
}
