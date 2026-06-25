import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Lock, X } from 'lucide-react';
import { cn } from '../lib/format';
import { FOCUS_RING } from '../lib/uiTokens';

// Открывается по window-событию 'fe:download-limit' (диспатчится из excel.js,
// когда бэкенд вернул 403 download_limit). Перенаправляет гостя на регистрацию.
export default function DownloadLimitModal() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const handler = () => setOpen(true);
    window.addEventListener('fe:download-limit', handler);
    return () => window.removeEventListener('fe:download-limit', handler);
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
      onClick={() => setOpen(false)}
    >
      <div
        className="w-full max-w-md rounded-2xl border border-border-subtle bg-surface shadow-2xl ring-1 ring-black/10 p-6"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className="flex items-start justify-between gap-3 mb-4">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-champagne/15">
              <Lock className="w-5 h-5 text-champagne" />
            </div>
            <h2 className="text-lg font-display font-bold text-text-primary">Доступно после регистрации</h2>
          </div>
          <button
            type="button"
            onClick={() => setOpen(false)}
            className={cn(FOCUS_RING, 'rounded-md p-1 text-text-tertiary hover:text-text-primary')}
            aria-label="Закрыть"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        <p className="text-sm text-text-secondary leading-relaxed mb-5">
          Скачивание данных и графиков доступно зарегистрированным пользователям.
          Регистрация бесплатна и открывает выгрузки без ограничений, за любой период
          истории, а также сравнение до 10 показателей.
        </p>
        <div className="flex items-center gap-3">
          <Link
            to="/register"
            onClick={() => setOpen(false)}
            className={cn(FOCUS_RING, 'flex-1 text-center rounded-xl bg-champagne text-white text-sm font-semibold py-2.5 hover:bg-champagne-muted transition-colors')}
          >
            Зарегистрироваться
          </Link>
          <Link
            to="/login"
            onClick={() => setOpen(false)}
            className={cn(FOCUS_RING, 'flex-1 text-center rounded-xl border border-border-subtle text-text-primary text-sm font-medium py-2.5 hover:border-champagne/40 transition-colors')}
          >
            Войти
          </Link>
        </div>
      </div>
    </div>
  );
}
