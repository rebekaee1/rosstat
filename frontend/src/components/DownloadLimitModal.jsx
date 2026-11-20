import { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Lock, X } from 'lucide-react';
import { cn } from '../lib/format';
import { FOCUS_RING } from '../lib/uiTokens';
import { useT } from '../i18n';
import { useAuth } from '../context/authContext';
import { authLink, prepareAuthReturn, pendingExport, clearPendingExport, currentReturnTo } from '../lib/authReturn';
import { resumeExport } from '../lib/excel';
import { track, events } from '../lib/track';
import Button from './Button';
import ApiInterestLink from './ApiInterestLink';
import OAuthButtons from './OAuthButtons';
import '../styles/k8-tools.css';
import '../styles/w5-pages.css';

// Открывается по window-событию 'fe:download-limit' (диспатчится из excel.js,
// когда бэкенд вернул 403 download_limit). Перенаправляет гостя на регистрацию.
export default function DownloadLimitModal() {
  const t = useT();
  const [open, setOpen] = useState(false);
  const { isAuthed } = useAuth();
  const location = useLocation();
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const pending = pendingExport();
  const canResume = isAuthed && pending?.path === currentReturnTo();
  useEffect(() => {
    if (isAuthed && pendingExport()?.path === currentReturnTo()) setOpen(true);
  }, [isAuthed, location.pathname, location.search, location.hash]);
  // Закрыл окно стены, ничего не нажав (крестик, Escape, подложка) — событие для воронки (20.11.2026).
  const close = (via) => {
    if (!canResume) track(events.LIMIT_MODAL_CLOSE, { via });
    setOpen(false);
    if (isAuthed) clearPendingExport();
  };
  const choose = (target) => {
    track(events.LIMIT_MODAL_REGISTER, { target });
    prepareAuthReturn();
    setOpen(false);
  };
  const resume = async () => {
    setBusy(true); setFailed(false);
    try { await resumeExport(pending.payload); setOpen(false); }
    catch { setFailed(true); }
    finally { setBusy(false); }
  };

  useEffect(() => {
    const handler = () => setOpen(true);
    window.addEventListener('fe:download-limit', handler);
    return () => window.removeEventListener('fe:download-limit', handler);
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e) => {
      if (e.key !== 'Escape') return;
      if (!canResume) track(events.LIMIT_MODAL_CLOSE, { via: 'escape' });
      setOpen(false);
      if (isAuthed) clearPendingExport();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, isAuthed, canResume]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[120] flex items-center justify-center p-4 fe-k8-scrim fe-reveal [--fe-duration:0.18s] [--fe-rise:0px]"
      onClick={() => close('scrim')}
    >
      <div
        className="w-full max-w-md max-h-[92dvh] overflow-y-auto overscroll-contain rounded-3xl p-6 fe-reveal [--fe-duration:0.22s] [--fe-rise:10px] fe-glass-pop"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="download-limit-title"
      >
        <div className="flex items-start justify-between gap-3 mb-4">
          <div className="flex items-center gap-3">
            <div className="fe-k8-gem">
              <Lock className="w-5 h-5 text-champagne" />
            </div>
            <h2 id="download-limit-title" className="text-lg font-display font-bold text-text-primary">{t(canResume ? 'download.resume.title' : 'download.limit.title')}</h2>
          </div>
          <button
            type="button"
            onClick={() => close('x')}
            className={cn(FOCUS_RING, 'fe-press flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-text-tertiary hover:text-text-primary pointer-coarse:h-11 pointer-coarse:w-11')}
            aria-label={t('common.close')}
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        {canResume ? (
          <>
            <p className="text-sm text-text-secondary leading-relaxed mb-5">
              {t(pending.payload ? 'download.resume.body' : 'download.resume.retryOnPage')}
            </p>
            {failed && <p role="alert" className="mb-4 text-sm text-negative">{t('download.resume.error')}</p>}
            <Button loading={busy} onClick={pending.payload ? resume : () => close('back')} className="w-full">{t(pending.payload ? 'download.resume.action' : 'download.resume.back')}</Button>
          </>
        ) : (
          <>
            {/* 14.11.2026: на телефоне со стены регистрировались 7 % против 29 % на компьютере — вход через
                Яндекс/VK теперь прямо здесь, одной кнопкой сверху, без перехода на страницу регистрации. */}
            <p className="text-sm text-text-secondary leading-relaxed mb-3">{t('download.limit.lead')}</p>
            <ul className="fe-w7p-benefits mb-4" aria-label={t('w7p.reg.benefitsAria')} data-testid="download-limit-benefits">
              <li>{t('w7p.reg.b1')}</li>
              <li>{t('w7p.reg.b2')}</li>
              <li>{t('w7p.reg.b3')}</li>
            </ul>
            <OAuthButtons
              next={currentReturnTo()}
              intent="login"
              dividerLabel={t('auth.oauth.divider')}
              onBeforeRedirect={prepareAuthReturn}
            />
            <div className="flex flex-col gap-2.5">
              <Button
                as={Link}
                variant="secondary"
                to={authLink('/register')}
                onClick={() => choose('email')}
                className="w-full"
              >
                {t('download.limit.email')}
              </Button>
              <Link
                to={authLink('/login')}
                onClick={() => choose('login')}
                className={cn(FOCUS_RING, 'self-center rounded-md px-2 py-1.5 text-sm text-text-secondary hover:text-text-primary')}
              >
                {t('download.limit.haveAccount')}
              </Link>
            </div>
          </>
        )}
        {/* Вторичная точка входа «фальшивой двери» API: только при api_interest_enabled. */}
        {!canResume && <ApiInterestLink source="limit_modal" variant="inline" onActivate={() => setOpen(false)} />}
      </div>
    </div>
  );
}
