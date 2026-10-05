// Постоянная маленькая точка входа «Установить приложение» (подвал сайта).
// Скрыта у установивших, на десктопе, в iframe и когда выключен флаг install_prompt_enabled.
// Android: сразу системное окно установки; iPhone: окно с подсказкой «Поделиться → На экран «Домой»».
import { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import { track, events } from '../lib/track';
import { cn } from '../lib/format';
import { FOCUS_RING } from '../lib/uiTokens';
import { useT } from '../i18n';
import { currentPlatform, inIframe, promptNativeInstall, usePwaStore } from '../lib/pwa';
import { IosHint } from './PwaInstallCard';
import Button from './Button';

export default function PwaInstallEntry({ className }) {
  const t = useT();
  const store = usePwaStore();
  const platform = currentPlatform(); // дёшево; не замораживаем: UA в тестах подменяется на лету
  const [open, setOpen] = useState(false);
  const ios = platform === 'ios-safari';

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  const available = Boolean(store.config?.install_prompt_enabled)
    && !store.state.installed && !store.standalone && !inIframe()
    && ((platform === 'android' && store.deferredPrompt) || ios);
  if (!available) return null;

  const click = () => {
    track(events.PWA_INSTALL_ENTRY_CLICK, { platform: ios ? 'ios' : 'android' });
    if (ios) {
      track(events.PWA_IOS_HINT_VIEW, { platform: 'ios' });
      setOpen(true);
    } else {
      promptNativeInstall({ fromCard: false });
    }
  };

  return (
    <li>
      <button type="button" onClick={click} className={cn(className, 'text-left')} data-testid="pwa-install-entry">
        {t('pwa.entry')}
      </button>
      {open && (
        <div
          className="fixed inset-0 z-[60] flex items-end justify-center bg-black/50 p-3 sm:items-center"
          onClick={() => setOpen(false)}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="pwa-entry-title"
            className="w-full max-w-md rounded-2xl border border-border-subtle bg-surface p-5 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-3">
              <h2 id="pwa-entry-title" className="text-base font-display font-bold text-text-primary">{t('pwa.ios.title')}</h2>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label={t('common.close')}
                className={cn(FOCUS_RING, 'fe-press flex h-8 w-8 items-center justify-center rounded-md text-text-tertiary hover:text-text-primary pointer-coarse:h-11 pointer-coarse:w-11')}
              >
                <X className="h-5 w-5" aria-hidden="true" />
              </button>
            </div>
            <p className="mb-3 mt-1 text-sm text-text-secondary">{t('pwa.ios.body')}</p>
            <IosHint />
            <Button onClick={() => setOpen(false)} className="mt-4 w-full">{t('pwa.ios.ok')}</Button>
          </div>
        </div>
      )}
    </li>
  );
}
