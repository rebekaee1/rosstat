// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import {
  VISITOR_SINCE_KEY,
  authErrorCode,
  authErrorField,
  clearAuthTrigger,
  consumeOAuthPending,
  firstVisitDays,
  landingPath,
  loginParams,
  markOAuthPending,
  oauthReturnError,
  peekAuthTrigger,
  rememberAuthTrigger,
  rememberLanding,
  signupParams,
} from './authTrigger';

beforeEach(() => { window.sessionStorage.clear(); window.localStorage.clear(); document.documentElement.lang = 'ru'; });
afterEach(() => { window.sessionStorage.clear(); window.localStorage.clear(); });

describe('что подтолкнуло к регистрации', () => {
  it('без упора это «direct»', () => {
    expect(peekAuthTrigger()).toBe('direct');
  });

  it('запоминает упоры и кнопки, остальные события игнорирует', () => {
    rememberAuthTrigger('scroll_depth');
    expect(peekAuthTrigger()).toBe('direct');
    rememberAuthTrigger('download_limit');
    expect(peekAuthTrigger()).toBe('gate_download');
    rememberAuthTrigger('header_register_click');
    expect(peekAuthTrigger()).toBe('header');
    rememberAuthTrigger('compare_limit_hit');
    expect(peekAuthTrigger()).toBe('gate_compare');
    clearAuthTrigger();
    expect(peekAuthTrigger()).toBe('direct');
  });

  it('упор старше 45 минут не считается', () => {
    window.sessionStorage.setItem('fe:auth:trigger', JSON.stringify({ value: 'nudge', ts: Date.now() - 46 * 60 * 1000 }));
    expect(peekAuthTrigger()).toBe('direct');
  });
});

describe('параметры signup / login_success', () => {
  it('содержат только технические поля', () => {
    window.localStorage.setItem(VISITOR_SINCE_KEY, String(Date.now() - 3 * 86400000 - 1000));
    window.history.pushState({}, '', '/indicator/cpi?utm=1');
    rememberLanding();
    rememberAuthTrigger('register_nudge_cta');
    const params = signupParams('yandex', { newsletter: true });
    expect(params).toEqual({
      method: 'yandex', newsletter: 1, site_locale: 'ru', trigger: 'nudge',
      landing: '/indicator/cpi', first_visit_days: 3,
    });
    expect(JSON.stringify(params)).not.toMatch(/@|utm/);
    expect(loginParams('email')).toEqual({ method: 'email', site_locale: 'ru' });
  });

  it('у старого посетителя без метки first_visit_days нет вовсе, а не ноль', () => {
    expect(firstVisitDays()).toBeNull();
    expect(signupParams('email')).not.toHaveProperty('first_visit_days');
  });

  it('первая страница запоминается один раз за вкладку', () => {
    window.history.pushState({}, '', '/compare');
    rememberLanding();
    window.history.pushState({}, '', '/calculators');
    rememberLanding();
    expect(landingPath()).toBe('/compare');
  });
});

describe('ошибки без текстов', () => {
  it('коды по статусу и полю', () => {
    expect(authErrorCode({ response: { status: 409 } })).toBe('exists');
    expect(authErrorCode({ response: { status: 401 } })).toBe('credentials');
    expect(authErrorCode({})).toBe('network');
    expect(authErrorField({ response: { status: 409 } })).toBe('email');
    expect(authErrorField({ response: { status: 422, data: { detail: [{ loc: ['body', 'password'] }] } } })).toBe('password');
    expect(authErrorField({ response: { status: 500 } })).toBeNull();
  });

  it('разбор ?error= допускает только простые коды', () => {
    expect(oauthReturnError('?error=oauth_denied&next=%2F')).toBe('oauth_denied');
    expect(oauthReturnError('?error=<script>')).toBeNull();
    expect(oauthReturnError('')).toBeNull();
  });
});

describe('возврат с провайдера', () => {
  it('флаг забирается один раз', () => {
    markOAuthPending('vk', 'login', { newsletter: true });
    expect(consumeOAuthPending()).toEqual({ provider: 'vk', intent: 'login', newsletter: true });
    expect(consumeOAuthPending()).toBeNull();
  });

  it('просроченный флаг игнорируется', () => {
    window.sessionStorage.setItem('fe:auth:pending', JSON.stringify({ provider: 'vk', intent: 'login', ts: Date.now() - 31 * 60 * 1000 }));
    expect(consumeOAuthPending()).toBeNull();
  });
});
