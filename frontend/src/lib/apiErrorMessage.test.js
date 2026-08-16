import { describe, expect, it } from 'vitest';
import { apiErrorMessage } from './apiErrorMessage';

const t = (key) => `T:${key}`;

describe('apiErrorMessage', () => {
  it('maps known Russian login detail', () => {
    const err = { response: { status: 401, data: { detail: 'Неверный email или пароль' } } };
    expect(apiErrorMessage(err, t)).toBe('T:auth.login.errorCredentials');
  });

  it('maps English backend detail', () => {
    const err = {
      response: {
        status: 409,
        data: { detail: 'An account with this email already exists' },
      },
    };
    expect(apiErrorMessage(err, t)).toBe('T:auth.register.emailExists');
  });

  it('unwraps FastAPI validation array', () => {
    const err = {
      response: {
        status: 422,
        data: {
          detail: [{ loc: ['body', 'password'], msg: 'Пароль не короче 8 символов', type: 'value_error' }],
        },
      },
    };
    expect(apiErrorMessage(err, t)).toBe('T:auth.validation.passwordShort');
  });

  it('maps download_limit message object', () => {
    const err = {
      response: {
        status: 403,
        data: {
          detail: {
            code: 'download_limit',
            message: 'Free download limit reached. Sign in for unlimited downloads.',
          },
        },
      },
    };
    expect(apiErrorMessage(err, t)).toBe('T:download.limit.apiMessage');
  });

  it('uses network fallback without response', () => {
    expect(apiErrorMessage({}, t)).toBe('T:common.networkError');
  });
});
