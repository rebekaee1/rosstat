import { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Lock, X } from 'lucide-react';
import { cn } from '../lib/format';
import { FOCUS_RING } from '../lib/uiTokens';
import { useT } from '../i18n';
import { useAuth } from '../context/authContext';
import { authLink, prepareAuthReturn, pendingExport, clearPendingExport, currentReturnTo } from '../lib/authReturn';
import { resumeExport } from '../lib/excel';
import Button from './Button';

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
  const close = () => { setOpen(false); if (isAuthed) clearPendingExport(); };
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
    const onKey = (e) => { if (e.key === 'Escape') { setOpen(false); if (isAuthed) clearPendingExport(); } };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, isAuthed]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm fe-reveal [--fe-duration:0.18s] [--fe-rise:0px]"
      onClick={close}
    >
      <div
        className="w-full max-w-md rounded-2xl border border-border-subtle bg-surface shadow-2xl ring-1 ring-black/10 p-6 fe-reveal [--fe-duration:0.22s] [--fe-rise:10px]"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="download-limit-title"
      >
        <div className="flex items-start justify-between gap-3 mb-4">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-champagne/15">
              <Lock className="w-5 h-5 text-champagne" />
            </div>
            <h2 id="download-limit-title" className="text-lg font-display font-bold text-text-primary">{t(canResume ? 'download.resume.title' : 'download.limit.title')}</h2>
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
        <p className="text-sm text-text-secondary leading-relaxed mb-5">
          {t(canResume ? (pending.payload ? 'download.resume.body' : 'download.resume.retryOnPage') : 'download.limit.body')}
        </p>
        {failed && <p role="alert" className="mb-4 text-sm text-negative">{t('download.resume.error')}</p>}
        <div className="flex items-center gap-3">
          {canResume ? <Button loading={busy} onClick={pending.payload ? resume : close} className="w-full">{t(pending.payload ? 'download.resume.action' : 'download.resume.back')}</Button> : <>
          <Button
            as={Link}
            to={authLink('/register')}
            onClick={() => { prepareAuthReturn(); setOpen(false); }}
            className="flex-1"
          >
            {t('auth.register.submitAlt')}
          </Button>
          <Button
            as={Link}
            variant="secondary"
            to={authLink('/login')}
            onClick={() => { prepareAuthReturn(); setOpen(false); }}
            className="flex-1"
          >
            {t('common.login')}
          </Button></>}
        </div>
      </div>
    </div>
  );
}
