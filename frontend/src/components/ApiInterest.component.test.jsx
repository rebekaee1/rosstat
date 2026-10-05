import { render, screen, fireEvent, waitFor, cleanup, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { LocaleContext } from '../i18n/localeContext';
import { translate } from '../i18n/messages';
import { MESSAGES } from '../i18n/messages';
import ApiInterestLink from './ApiInterestLink';
import ApiInterestModal from './ApiInterestModal';
import DownloadLimitModal from './DownloadLimitModal';
import {
  API_INTEREST_EVENT,
  API_INTEREST_USE_CASES,
  resetApiInterestForTests,
} from '../lib/apiInterest';
import { submitApiInterest } from '../lib/api';
import { track } from '../lib/track';

vi.mock('../lib/track', () => ({
  track: vi.fn(),
  trackFile: vi.fn(),
  events: {
    API_INTEREST_VIEW: 'api_interest_view',
    API_INTEREST_CLICK: 'api_interest_click',
    API_INTEREST_SUBMIT: 'api_interest_submit',
  },
}));
vi.mock('../lib/api', () => ({
  submitApiInterest: vi.fn(),
  exportTable: vi.fn(),
}));
vi.mock('../context/authContext', () => ({ useAuth: () => ({ isAuthed: false }) }));

const ru = (key, vars) => translate(key, vars, 'ru');

function mockFlag(enabled) {
  globalThis.fetch = vi.fn(async () => ({ ok: true, json: async () => ({ enabled }) }));
}

function renderWithLocale(ui) {
  return render(
    <MemoryRouter>
      <LocaleContext.Provider value={{ locale: 'ru', t: ru, isPreview: false, setPreviewLocale() {} }}>
        {ui}
      </LocaleContext.Provider>
    </MemoryRouter>,
  );
}

const calls = (name) => track.mock.calls.filter(([event]) => event === name);

beforeEach(() => {
  resetApiInterestForTests();
  track.mockClear();
  submitApiInterest.mockReset();
});
afterEach(() => {
  cleanup();
  delete globalThis.fetch;
});

describe('точка входа и флаг api_interest_enabled', () => {
  it('скрыта и не шлёт показ, пока флаг выключен', async () => {
    mockFlag(false);
    renderWithLocale(<ApiInterestLink source="indicator" code="cpi" />);
    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 0));
    expect(screen.queryByRole('button', { name: /API и выгрузка/ })).toBeNull();
    expect(calls('api_interest_view')).toHaveLength(0);
  });

  it('скрыта, если конфиг недоступен (ошибка сети)', async () => {
    globalThis.fetch = vi.fn(async () => { throw new Error('offline'); });
    renderWithLocale(<ApiInterestLink source="indicator" code="cpi" />);
    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 0));
    expect(screen.queryByRole('button')).toBeNull();
  });

  it('видна при включённом флаге, показ шлётся один раз за сессию на точку входа', async () => {
    mockFlag(true);
    const first = renderWithLocale(<ApiInterestLink source="indicator" code="cpi" />);
    expect(await screen.findByRole('button', { name: 'API и выгрузка с прогнозом' })).toBeTruthy();
    expect(calls('api_interest_view')).toEqual([['api_interest_view', { source: 'indicator' }]]);
    first.unmount();
    // Повторный показ в той же сессии (другая страница показателя) — не считается.
    renderWithLocale(<ApiInterestLink source="indicator" code="ppi" />);
    await screen.findByRole('button', { name: 'API и выгрузка с прогнозом' });
    expect(calls('api_interest_view')).toHaveLength(1);
  });

  it('клик пишет api_interest_click {source, indicator_code} и открывает окно', async () => {
    mockFlag(true);
    const opened = vi.fn();
    window.addEventListener(API_INTEREST_EVENT, opened);
    renderWithLocale(<ApiInterestLink source="indicator" code="key-rate" />);
    fireEvent.click(await screen.findByRole('button', { name: 'API и выгрузка с прогнозом' }));
    expect(calls('api_interest_click')).toEqual([
      ['api_interest_click', { source: 'indicator', indicator_code: 'key-rate' }],
    ]);
    expect(opened).toHaveBeenCalledTimes(1);
    expect(opened.mock.calls[0][0].detail).toEqual({ source: 'indicator', indicatorCode: 'key-rate' });
    window.removeEventListener(API_INTEREST_EVENT, opened);
  });
});

describe('вторичная ссылка в окне лимита скачиваний', () => {
  const openLimit = () => act(() => { window.dispatchEvent(new CustomEvent('fe:download-limit')); });

  it('не показывается при выключенном флаге; основной сценарий цел', async () => {
    mockFlag(false);
    renderWithLocale(<DownloadLimitModal />);
    openLimit();
    expect(await screen.findByRole('link', { name: ru('common.login') })).toBeTruthy();
    expect(screen.getByRole('link', { name: ru('auth.register.submitAlt') })).toBeTruthy();
    await new Promise((r) => setTimeout(r, 0));
    expect(screen.queryByRole('button', { name: ru('apiInterest.limitLink') })).toBeNull();
  });

  it('при включённом флаге стоит под «Войти»; клик закрывает лимит и открывает заявку', async () => {
    mockFlag(true);
    const opened = vi.fn();
    window.addEventListener(API_INTEREST_EVENT, opened);
    renderWithLocale(<DownloadLimitModal />);
    openLimit();
    const link = await screen.findByRole('button', { name: ru('apiInterest.limitLink') });
    const login = screen.getByRole('link', { name: ru('common.login') });
    // Ссылка следует в DOM после кнопки входа (вторичная, под основным CTA).
    expect(login.compareDocumentPosition(link) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(calls('api_interest_view')).toEqual([['api_interest_view', { source: 'limit_modal' }]]);
    fireEvent.click(link);
    expect(calls('api_interest_click')).toEqual([
      ['api_interest_click', { source: 'limit_modal', indicator_code: null }],
    ]);
    expect(opened.mock.calls[0][0].detail.source).toBe('limit_modal');
    expect(screen.queryByRole('dialog')).toBeNull(); // окно лимита закрылось
    window.removeEventListener(API_INTEREST_EVENT, opened);
  });
});

describe('окно заявки', () => {
  const open = (detail = { source: 'indicator', indicatorCode: 'cpi' }) => {
    window.dispatchEvent(new CustomEvent(API_INTEREST_EVENT, { detail }));
  };
  const fill = async ({ email = 'analyst@example.com', useCase = 'consulting', comment = '' } = {}) => {
    fireEvent.change(await screen.findByLabelText(ru('apiInterest.emailLabel')), { target: { value: email } });
    if (useCase) fireEvent.change(screen.getByLabelText(ru('apiInterest.useCaseLabel')), { target: { value: useCase } });
    if (comment) fireEvent.change(screen.getByLabelText(ru('apiInterest.commentLabel')), { target: { value: comment } });
  };

  it('закрыто, пока нет события; по событию — честный текст без обещаний и ссылка на политику', async () => {
    renderWithLocale(<ApiInterestModal />);
    expect(screen.queryByRole('dialog')).toBeNull();
    open();
    const dialog = await screen.findByRole('dialog');
    expect(dialog.textContent).toContain('Доступ по API и выгрузка истории прогнозов — в разработке');
    expect(dialog.textContent).toContain('Оставьте почту — напишем, когда откроем');
    // никаких цен, сроков и «уже доступно»
    expect(dialog.textContent).not.toMatch(/₽|руб|\$|€|доступно уже|уже доступн|до \d|в \d{4}/i);
    expect(screen.getByRole('link', { name: ru('apiInterest.privacyLink') }).getAttribute('href')).toBe('/privacy');
    // сегменты — все 7 + плейсхолдер
    const select = screen.getByLabelText(ru('apiInterest.useCaseLabel'));
    expect(select.querySelectorAll('option')).toHaveLength(API_INTEREST_USE_CASES.length + 1);
  });

  it('валидирует почту и сегмент без запроса к серверу', async () => {
    renderWithLocale(<ApiInterestModal />);
    open();
    await fill({ email: 'not-an-email', useCase: '' });
    fireEvent.click(screen.getByRole('button', { name: ru('apiInterest.submit') }));
    expect(await screen.findByText(ru('apiInterest.errorEmail'))).toBeTruthy();
    expect(screen.getByText(ru('apiInterest.errorUseCase'))).toBeTruthy();
    expect(submitApiInterest).not.toHaveBeenCalled();
    expect(calls('api_interest_submit')).toHaveLength(0);
  });

  it('отправка: payload на сервер, в событии только use_case/source, без почты', async () => {
    submitApiInterest.mockResolvedValue({ ok: true });
    renderWithLocale(<ApiInterestModal />);
    open({ source: 'limit_modal', indicatorCode: null });
    await fill({ useCase: 'journalism', comment: 'нужны прогнозы ВВП' });
    fireEvent.click(screen.getByRole('button', { name: ru('apiInterest.submit') }));
    await waitFor(() => expect(submitApiInterest).toHaveBeenCalledTimes(1));
    expect(submitApiInterest).toHaveBeenCalledWith({
      email: 'analyst@example.com',
      use_case: 'journalism',
      comment: 'нужны прогнозы ВВП',
      source: 'limit_modal',
      indicator_code: null,
      website: '',
    });
    expect(await screen.findByText(ru('apiInterest.sentTitle'))).toBeTruthy();
    expect(calls('api_interest_submit')).toEqual([
      ['api_interest_submit', { use_case: 'journalism', source: 'limit_modal' }],
    ]);
    // Приватность: ни в одном аналитическом вызове нет ни почты, ни комментария.
    expect(JSON.stringify(track.mock.calls)).not.toContain('analyst@example.com');
    expect(JSON.stringify(track.mock.calls)).not.toContain('нужны прогнозы');
  });

  it('honeypot-поле скрыто от людей и не заполняется пользователем', async () => {
    renderWithLocale(<ApiInterestModal />);
    open();
    const trap = (await screen.findByRole('dialog')).querySelector('input[name="website"]');
    expect(trap.getAttribute('tabindex')).toBe('-1');
    expect(trap.closest('[aria-hidden="true"]')).toBeTruthy();
  });

  it('ошибка сервера: сообщение, форма и введённое сохраняются, событие не шлётся', async () => {
    submitApiInterest.mockRejectedValue({ response: { status: 500 } });
    renderWithLocale(<ApiInterestModal />);
    open();
    await fill();
    fireEvent.click(screen.getByRole('button', { name: ru('apiInterest.submit') }));
    expect(await screen.findByText(ru('apiInterest.error'))).toBeTruthy();
    expect(screen.getByLabelText(ru('apiInterest.emailLabel')).value).toBe('analyst@example.com');
    expect(calls('api_interest_submit')).toHaveLength(0);
  });

  it('429 даёт отдельное сообщение; Escape закрывает окно', async () => {
    submitApiInterest.mockRejectedValue({ response: { status: 429 } });
    renderWithLocale(<ApiInterestModal />);
    open();
    await fill();
    fireEvent.click(screen.getByRole('button', { name: ru('apiInterest.submit') }));
    expect(await screen.findByText(ru('apiInterest.errorRate'))).toBeTruthy();
    fireEvent.keyDown(window, { key: 'Escape' });
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
  });
});

describe('RU/EN паритет и контракт с backend', () => {
  const keys = (locale) => Object.keys(MESSAGES[locale]).filter((k) => k.startsWith('apiInterest.'));

  it('все ключи apiInterest.* есть в обоих словарях и непусты', () => {
    expect(keys('ru').length).toBeGreaterThan(20);
    expect(keys('en').sort()).toEqual(keys('ru').sort());
    for (const key of keys('ru')) {
      expect(MESSAGES.ru[key].trim()).not.toBe('');
      expect(MESSAGES.en[key].trim()).not.toBe('');
    }
  });

  it('у каждого сегмента есть подпись в RU и EN', () => {
    for (const key of API_INTEREST_USE_CASES) {
      expect(MESSAGES.ru[`apiInterest.useCase.${key}`]).toBeTruthy();
      expect(MESSAGES.en[`apiInterest.useCase.${key}`]).toBeTruthy();
    }
  });

  it('сегменты совпадают с backend API_INTEREST_USE_CASES', () => {
    const src = readFileSync(resolve(import.meta.dirname, '../../../backend/app/services/alerting.py'), 'utf8');
    const block = src.split('API_INTEREST_USE_CASES = {')[1].split('}')[0];
    const backend = [...block.matchAll(/"([a-z_]+)":/g)].map((m) => m[1]);
    expect(backend).toEqual(API_INTEREST_USE_CASES);
  });
});
