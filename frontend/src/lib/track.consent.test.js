// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// Подменяем только то, что нужно track.js; consentAllows читает настоящее хранилище согласия.
vi.mock('./behavior', async () => {
  const actual = await vi.importActual('./behavior');
  return { ...actual, isAutomationClient: () => false, visitorId: () => 'v-1' };
});

import { events, sendEvent, track } from './track';

const CONSENT_KEY = 'fe:consent:v1';
const CONSENT_V = '2026-06-16';

let beacon;

beforeEach(() => {
  window.localStorage.clear();
  beacon = vi.fn(() => true);
  Object.defineProperty(navigator, 'sendBeacon', { value: beacon, configurable: true });
});
afterEach(() => { window.localStorage.clear(); });

const sentNames = () => beacon.mock.calls.map(([, blob]) => blob).length;

describe('sendEvent и согласие на аналитику (152-ФЗ)', () => {
  it('без выбора согласие подразумевается: событие уходит', () => {
    sendEvent('indicator_view', { indicator: 'cpi' });
    expect(beacon).toHaveBeenCalledTimes(1);
  });

  it('явный отказ текущей редакции: события не уходят', () => {
    window.localStorage.setItem(CONSENT_KEY, JSON.stringify({ v: CONSENT_V, analytics: false, ads: false }));
    sendEvent('indicator_view', { indicator: 'cpi' });
    track(events.DOWNLOAD_CSV, { indicator: 'cpi' });
    expect(sentNames()).toBe(0);
  });

  it('но сам факт отказа (consent_update) фиксируется', () => {
    window.localStorage.setItem(CONSENT_KEY, JSON.stringify({ v: CONSENT_V, analytics: false, ads: false }));
    sendEvent('consent_update', { analytics: 0 });
    expect(beacon).toHaveBeenCalledTimes(1);
  });

  it('отказ прежней редакции не действует (как в behavior.js)', () => {
    window.localStorage.setItem(CONSENT_KEY, JSON.stringify({ v: '2020-01-01', analytics: false }));
    sendEvent('indicator_view', {});
    expect(beacon).toHaveBeenCalledTimes(1);
  });
});

describe('реестр событий круга 11', () => {
  it('содержит события входа, языка и новых функций', () => {
    for (const name of [
      'auth_error', 'auth_form_error', 'oauth_consent_open', 'oauth_consent_cancel', 'locale_switch',
      'share_link', 'favorite_add', 'favorite_remove', 'compare_preset_open', 'compare_save',
      'compare_saved_open', 'indicator_subscribe', 'indicator_unsubscribe', 'push_prompt_view',
      'push_permission', 'converter_use', 'calc_use', 'export_run',
    ]) {
      expect(Object.values(events)).toContain(name);
    }
  });

  it('смена языка отправляет locale_switch до смены хоста', async () => {
    window.dispatchEvent(new CustomEvent('fe:locale-switch', { detail: { from: 'ru', to: 'en' } }));
    expect(beacon).toHaveBeenCalledTimes(1);
    const blob = beacon.mock.calls[0][1];
    const text = await new Promise((resolve) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.readAsText(blob);
    });
    const body = JSON.parse(text);
    expect(body.event_name).toBe('locale_switch');
    expect(body.params).toMatchObject({ from: 'ru', to: 'en' });
  });
});
