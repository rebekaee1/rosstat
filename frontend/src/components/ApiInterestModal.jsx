import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Braces, X } from 'lucide-react';
import { cn } from '../lib/format';
import { FOCUS_RING } from '../lib/uiTokens';
import { useT } from '../i18n';
import { submitApiInterest } from '../lib/api';
import { track, events } from '../lib/track';
import { API_INTEREST_EVENT, API_INTEREST_USE_CASES } from '../lib/apiInterest';
import Button from './Button';

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const FIELD = 'fe-input w-full px-3.5 py-2.5 rounded-xl bg-obsidian-lighter/50 border text-text-primary focus:outline-none';
const fieldClass = (invalid) => cn(
  FIELD,
  invalid ? 'border-negative focus:border-negative' : 'border-border-subtle focus:border-champagne/50',
);

/**
 * Окно заявки «API и выгрузка с прогнозами» («фальшивая дверь», замер спроса).
 * Монтируется один раз в App и открывается window-событием 'fe:api-interest'
 * (ApiInterestLink → openApiInterest). Текст ничего не обещает: «в разработке».
 * Почта уходит только в POST /api-interest; в аналитику — use_case и source.
 */
export default function ApiInterestModal() {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [ctx, setCtx] = useState({ source: 'indicator', indicatorCode: null });
  const [email, setEmail] = useState('');
  const [useCase, setUseCase] = useState('');
  const [comment, setComment] = useState('');
  const [website, setWebsite] = useState(''); // honeypot: человек не видит
  const [errors, setErrors] = useState({});
  const [submitError, setSubmitError] = useState('');
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const emailRef = useRef(null);

  useEffect(() => {
    const onOpen = (event) => {
      const detail = event?.detail || {};
      setCtx({ source: detail.source || 'indicator', indicatorCode: detail.indicatorCode || null });
      setErrors({});
      setSubmitError('');
      setSent(false);
      setOpen(true);
    };
    window.addEventListener(API_INTEREST_EVENT, onOpen);
    return () => window.removeEventListener(API_INTEREST_EVENT, onOpen);
  }, []);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  useEffect(() => {
    if (open && !sent) emailRef.current?.focus();
  }, [open, sent]);

  if (!open) return null;

  const close = () => setOpen(false);

  const submit = async (event) => {
    event.preventDefault();
    if (busy) return;
    const next = {};
    if (!EMAIL_RE.test(email.trim())) next.email = t('apiInterest.errorEmail');
    if (!API_INTEREST_USE_CASES.includes(useCase)) next.useCase = t('apiInterest.errorUseCase');
    setErrors(next);
    setSubmitError('');
    if (Object.keys(next).length) return;
    setBusy(true);
    try {
      await submitApiInterest({
        email: email.trim(),
        use_case: useCase,
        comment: comment.trim() || null,
        source: ctx.source,
        indicator_code: ctx.indicatorCode,
        website,
      });
      // В событие — только сегмент и точка входа; почта и комментарий не уходят.
      track(events.API_INTEREST_SUBMIT, { use_case: useCase, source: ctx.source });
      setSent(true);
      setEmail(''); setComment(''); setUseCase('');
    } catch (err) {
      setSubmitError(t(err?.response?.status === 429 ? 'apiInterest.errorRate' : 'apiInterest.error'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-[70] flex items-center justify-center overflow-y-auto p-4 bg-black/60 backdrop-blur-sm fe-reveal [--fe-duration:0.18s] [--fe-rise:0px]"
      onClick={close}
    >
      <div
        className="w-full max-w-md rounded-2xl border border-border-subtle bg-surface shadow-2xl ring-1 ring-black/10 p-6 fe-reveal [--fe-duration:0.22s] [--fe-rise:10px]"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="api-interest-title"
      >
        <div className="flex items-start justify-between gap-3 mb-4">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-champagne/15">
              <Braces className="w-5 h-5 text-champagne" aria-hidden="true" />
            </div>
            <h2 id="api-interest-title" className="text-lg font-display font-bold text-text-primary">
              {t('apiInterest.title')}
            </h2>
          </div>
          <button
            type="button"
            onClick={close}
            className={cn(FOCUS_RING, 'fe-press flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-text-tertiary hover:text-text-primary pointer-coarse:h-11 pointer-coarse:w-11')}
            aria-label={t('common.close')}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {sent ? (
          <div role="status">
            <p className="font-medium text-text-primary">{t('apiInterest.sentTitle')}</p>
            <p className="text-sm text-text-secondary leading-relaxed mt-1 mb-5">{t('apiInterest.sentBody')}</p>
            <Button onClick={close} className="w-full">{t('common.close')}</Button>
          </div>
        ) : (
          <form onSubmit={submit} noValidate>
            <p className="text-sm text-text-secondary leading-relaxed mb-5">{t('apiInterest.intro')}</p>

            <label className="block text-sm text-text-secondary mb-1.5" htmlFor="api-interest-email">
              {t('apiInterest.emailLabel')}
            </label>
            <input
              ref={emailRef}
              id="api-interest-email"
              name="email"
              type="email"
              inputMode="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder={t('w5.auth.emailPlaceholder')}
              aria-invalid={errors.email ? true : undefined}
              aria-describedby={errors.email ? 'api-interest-email-error' : undefined}
              className={fieldClass(errors.email)}
            />
            <p id="api-interest-email-error" role="alert" className="text-sm text-negative mt-1 empty:hidden">{errors.email}</p>

            <label className="block text-sm text-text-secondary mt-4 mb-1.5" htmlFor="api-interest-use-case">
              {t('apiInterest.useCaseLabel')}
            </label>
            <select
              id="api-interest-use-case"
              name="use_case"
              required
              value={useCase}
              onChange={(e) => setUseCase(e.target.value)}
              aria-invalid={errors.useCase ? true : undefined}
              aria-describedby={errors.useCase ? 'api-interest-use-case-error' : undefined}
              className={fieldClass(errors.useCase)}
            >
              <option value="" disabled>{t('apiInterest.useCasePlaceholder')}</option>
              {API_INTEREST_USE_CASES.map((key) => (
                <option key={key} value={key}>{t(`apiInterest.useCase.${key}`)}</option>
              ))}
            </select>
            <p id="api-interest-use-case-error" role="alert" className="text-sm text-negative mt-1 empty:hidden">{errors.useCase}</p>

            <label className="block text-sm text-text-secondary mt-4 mb-1.5" htmlFor="api-interest-comment">
              {t('apiInterest.commentLabel')}
            </label>
            <textarea
              id="api-interest-comment"
              name="comment"
              rows={3}
              maxLength={1000}
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder={t('apiInterest.commentPlaceholder')}
              className={cn(fieldClass(false), 'resize-y')}
            />

            {/* Honeypot: скрыто от людей и скринридеров, боты поле заполняют. */}
            <div aria-hidden="true" style={{ position: 'absolute', left: '-10000px', width: 1, height: 1, overflow: 'hidden' }}>
              <label htmlFor="api-interest-website">Website</label>
              <input
                id="api-interest-website"
                name="website"
                type="text"
                tabIndex={-1}
                autoComplete="off"
                value={website}
                onChange={(e) => setWebsite(e.target.value)}
              />
            </div>

            <p className="text-xs text-text-tertiary mt-4">
              {t('apiInterest.privacyNote')}{' '}
              <Link to="/privacy" target="_blank" rel="noopener" className="underline underline-offset-2 hover:text-text-primary">
                {t('apiInterest.privacyLink')}
              </Link>
            </p>

            <p role="alert" className="text-sm text-negative mt-3 empty:hidden">{submitError}</p>

            <Button type="submit" loading={busy} className="w-full mt-4">
              {busy ? t('apiInterest.sending') : t('apiInterest.submit')}
            </Button>
          </form>
        )}
      </div>
    </div>
  );
}
