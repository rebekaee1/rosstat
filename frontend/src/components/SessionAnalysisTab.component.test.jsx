import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import SessionAnalysisTab from './SessionAnalysisTab';

const calls = vi.hoisted(() => ({ get: vi.fn() }));
const playback = vi.hoisted(() => ({ play: vi.fn(), pause: vi.fn(), destroy: vi.fn(), getCurrentTime: vi.fn(() => 1500) }));
vi.mock('../lib/api', () => ({ default: calls }));
vi.mock('@rrweb/replay', () => ({ Replayer: class { constructor() { Object.assign(this, playback); } } }));
vi.mock('@rrweb/replay/dist/style.css', () => ({}));
const sid = 'a'.repeat(64);
function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(<QueryClientProvider client={client}><SessionAnalysisTab /></QueryClientProvider>);
}
beforeEach(() => { calls.get.mockReset(); Object.values(playback).forEach(fn => fn.mockClear()); });
afterEach(cleanup);
describe('session analysis displays actual coverage', () => {
  it('keeps missing analyses in the denominator and exposes list pagination', async () => {
    calls.get.mockImplementation(async (path, { params }) => ({ data: path.endsWith('/summary') ? {
      total_captured_sessions: 75, analyzed_sessions: 3, pending_or_missing_sessions: 72, visual_reviewed_sessions: 0, issues: [],
    } : { total_captured_sessions: 75, items: [], has_more: !params.cursor, next_cursor: 'page2' } }));
    mount();
    expect(await screen.findByText(/Собрано: 75 — свежих разборов: 3 — ожидают: 72/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Далее' }));
    await vi.waitFor(() => expect(calls.get).toHaveBeenCalledWith(expect.stringContaining('/sessions'), expect.objectContaining({ params: expect.objectContaining({ cursor: 'page2' }) })));
  });
  it('shows partial events and missing pixels without presenting them as a complete human review', async () => {
    calls.get.mockImplementation(async path => ({ data: path.endsWith('/summary') ? {
      total_captured_sessions: 1, analyzed_sessions: 1, pending_or_missing_sessions: 0, visual_reviewed_sessions: 0, issues: [],
    } : path.endsWith('/analysis') ? {
      session_id: sid, coverage: { captured_events: 20001, analyzed_events: 20000, event_complete: false, visual: { status: 'dom_only' } },
      metrics: { pageviews: 2, observed_duration_ms: 90000 }, ai: { status: 'disabled' },
      facts: [{ id: 'slow', text: 'INP 3744 мс', evidence_ids: ['event:1'] }], inferences: [], unknowns: [], recommendations: [],
      evidence: [{ id: 'event:1', relative_ms: 1, page: '/', source: 'behavior_event' }],
    } : path.endsWith('/replay') ? { recordings: [], gaps: [{ reason: 'missing_recording' }] }
      : path.endsWith('/events') ? { total_captured_events: 20001, items: [{ id: 'event:1', occurred_at: '2026-09-30T13:44:20.649Z', event_type: 'vital', page: '/' }], has_more: true, next_cursor: 'event2' }
        : { total_captured_sessions: 1, items: [{ session_id: sid, first_at: '2026-09-30T13:44:00Z', device_type: 'mobile', browser: 'Chrome', event_count: 20001 }], has_more: false } }));
    mount();
    fireEvent.click(await screen.findByRole('button', { name: /Chrome — 20001 событий/ }));
    expect(await screen.findByText(/События: 20000 из 20001 — обработана часть/)).toBeTruthy();
    expect(screen.getByText('Есть состояния DOM, пиксельного просмотра нет')).toBeTruthy();
    expect(await screen.findByText('Собственная запись этой сессии отсутствует.')).toBeTruthy();
    expect(await screen.findByText(/30.09.2026, 16:44:20[,.]649 МСК — vital/)).toBeTruthy();
    expect(screen.getByRole('link', { name: 'event:1' }).getAttribute('href')).toBe('#evidence-event:1');
    fireEvent.click(screen.getByRole('button', { name: 'Следующие события' }));
    await vi.waitFor(() => expect(calls.get).toHaveBeenCalledWith(expect.stringContaining('/events'), expect.objectContaining({ params: expect.objectContaining({ cursor: 'event2' }) })));
  });
  it('waits for the player and updates elapsed time while playing', async () => {
    calls.get.mockImplementation(async path => ({ data: path.endsWith('/summary') ? { issues: [] }
      : path.endsWith('/analysis') ? { coverage: { captured_events: 0, analyzed_events: 0, event_complete: true, visual: { status: 'dom_only' } },
        metrics: { pageviews: 1, observed_duration_ms: 2000 }, ai: { status: 'disabled' }, evidence: [] }
        : path.endsWith('/replay') ? { recordings: [{ recording_id: 'recording1', page: '/', duration_ms: 2000, full_snapshots: 1, events: [{ type: 2, timestamp: 1 }] }], gaps: [] }
          : path.endsWith('/events') ? { items: [], total_captured_events: 0, has_more: false }
            : { items: [{ session_id: sid, first_at: '2026-09-30T13:44:00Z', event_count: 0 }], has_more: false } }));
    mount();
    fireEvent.click(await screen.findByRole('button', { name: /0 событий/ }));
    const play = await screen.findByRole('button', { name: 'Смотреть', exact: true });
    await vi.waitFor(() => expect(play.disabled).toBe(false));
    fireEvent.click(play);
    expect(playback.play).toHaveBeenCalledWith(0);
    await vi.waitFor(() => expect(screen.getByRole('slider', { name: 'Время записи' }).value).toBe('1500'));
    fireEvent.click(screen.getByRole('button', { name: 'Пауза', exact: true }));
    expect(playback.pause).toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Пауза', exact: true }).disabled).toBe(true);
  });
});
