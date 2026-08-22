/**
 * Normalize API error bodies for UI (login / register / account).
 *
 * Backend already returns locale-aware detail via X-FE-Locale. This map is a
 * safety net for stale clients / missing header, and unwraps FastAPI
 * validation arrays so the form never shows "[object Object]".
 */

/** Known RU (and EN) backend strings → message keys. */
const DETAIL_TO_KEY = {
  'Неверный email или пароль': 'auth.login.errorCredentials',
  'Invalid email or password': 'auth.login.errorCredentials',
  'Слишком много попыток. Повторите позже': 'auth.login.errorLockout',
  'Too many attempts. Try again later': 'auth.login.errorLockout',
  'Аккаунт недоступен': 'auth.login.errorUnavailable',
  'Account unavailable': 'auth.login.errorUnavailable',
  'Требуется согласие на обработку персональных данных': 'auth.register.consentRequired',
  'Consent to personal data processing is required': 'auth.register.consentRequired',
  'Пользователь с таким email уже существует': 'auth.register.emailExists',
  'An account with this email already exists': 'auth.register.emailExists',
  'Некорректный email': 'auth.validation.email',
  'Invalid email': 'auth.validation.email',
  'Пароль не короче 8 символов': 'auth.validation.passwordShort',
  'Password must be at least 8 characters': 'auth.validation.passwordShort',
  'Слишком длинный пароль': 'auth.validation.passwordLong',
  'Password is too long': 'auth.validation.passwordLong',
  'Укажите email': 'auth.validation.emailRequired',
  'Email is required': 'auth.validation.emailRequired',
  'Этот email уже используется': 'auth.validation.emailTaken',
  'This email is already in use': 'auth.validation.emailTaken',
  'Способ входа не найден': 'auth.validation.identityMissing',
  'Sign-in method not found': 'auth.validation.identityMissing',
  'Нельзя удалить последний способ входа': 'auth.validation.lastIdentity',
  'Cannot remove the last sign-in method': 'auth.validation.lastIdentity',
  'Не авторизован': 'auth.error.unauthorized',
  'Not authenticated': 'auth.error.unauthorized',
  'CSRF-токен недействителен': 'auth.error.csrf',
  'Invalid CSRF token': 'auth.error.csrf',
  'Сообщение слишком короткое': 'account.feedbackTooShort',
  'Message is too short': 'account.feedbackTooShort',
  'Сообщение слишком длинное': 'account.feedbackTooLong',
  'Message is too long': 'account.feedbackTooLong',
  'Имя не длиннее 120 символов': 'account.errorNameLength',
  'Name must be at most 120 characters': 'account.errorNameLength',
  'Лимит бесплатных выгрузок исчерпан. Войдите в аккаунт для безлимитного скачивания.':
    'download.limit.apiMessage',
  'Free download limit reached. Sign in for unlimited downloads.':
    'download.limit.apiMessage',
};

const STATUS_FALLBACK = {
  401: 'auth.login.errorCredentials',
  403: 'auth.login.errorUnavailable',
  409: 'auth.register.emailExists',
  422: 'auth.register.consentRequired',
  423: 'auth.login.errorLockout',
};

function firstDetailString(detail) {
  if (detail == null) return null;
  if (typeof detail === 'string') return detail;
  if (typeof detail === 'object' && typeof detail.message === 'string') {
    return detail.message;
  }
  if (Array.isArray(detail)) {
    for (const item of detail) {
      if (typeof item === 'string') return item;
      if (item && typeof item.msg === 'string') return item.msg;
    }
  }
  return null;
}

/**
 * @param {unknown} err — axios error
 * @param {(key: string) => string} t — useT()
 * @param {string} [fallbackKey='common.networkError']
 */
export function apiErrorMessage(err, t, fallbackKey = 'common.networkError') {
  if (!err?.response) {
    return t(fallbackKey);
  }
  const status = err.response.status;
  const raw = firstDetailString(err.response.data?.detail);
  if (raw && DETAIL_TO_KEY[raw]) {
    return t(DETAIL_TO_KEY[raw]);
  }
  if (raw && typeof raw === 'string' && !/^[[{]/.test(raw)) {
    // Backend already localized — show as-is.
    return raw;
  }
  if (STATUS_FALLBACK[status]) {
    return t(STATUS_FALLBACK[status]);
  }
  return t(fallbackKey);
}
