// Карточка «Установить приложение» (PWA). Только вид: решения «когда показывать» —
// в PwaInstallPrompt и lib/pwaPolicy.js.
//   platform="android" — кнопка «Установить» (системное окно через beforeinstallprompt);
//   platform="ios"     — подсказка «Поделиться → На экран «Домой» → Добавить» с иконками.
import { useState } from 'react';
import { ArrowRight, PlusSquare, Share, Smartphone, X } from 'lucide-react';
import { cn } from '../lib/format';
import { FOCUS_RING } from '../lib/uiTokens';
import { useT } from '../i18n';
import Button from './Button';

function IosStep({ icon: Icon, label }) {
  return (
    <li className="flex min-w-0 flex-1 flex-col items-center gap-1.5 text-center">
      <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-obsidian-lighter/50 text-champagne-ink">
        <Icon className="h-5 w-5" aria-hidden="true" />
      </span>
      <span className="text-xs leading-tight text-text-secondary">{label}</span>
    </li>
  );
}

export function IosHint() {
  const t = useT();
  return (
    <ol className="flex items-start gap-1" data-testid="pwa-ios-steps">
      <IosStep icon={Share} label={t('pwa.ios.step.share')} />
      <li aria-hidden="true" className="mt-3 text-text-tertiary"><ArrowRight className="h-4 w-4" /></li>
      <IosStep icon={PlusSquare} label={t('pwa.ios.step.add')} />
      <li aria-hidden="true" className="mt-3 text-text-tertiary"><ArrowRight className="h-4 w-4" /></li>
      <IosStep icon={Smartphone} label={t('pwa.ios.step.confirm')} />
    </ol>
  );
}

/**
 * Круг 9, S2. Карточка стоит над нижней панелью, плашкой cookie и плашкой «Результат» (`--fe-bottom-clear`, z1-tokens.css),
 * а не на 12 px от низа окна, где панель (z-70) её накрывала. На iPhone три шага инструкции (~200 pt) не висят на экране сразу:
 * сначала тонкая строка «Установите Forecast Economy» и кнопка «Как?», шаги раскрываются по касанию.
 */
export default function PwaInstallCard({
  platform, onInstall, onLater, onAck, busy = false, className, floating = true,
}) {
  const t = useT();
  const ios = platform === 'ios';
  const [stepsOpen, setStepsOpen] = useState(false);
  const slim = ios && floating && !stepsOpen;
  return (
    <aside
      role="dialog"
      aria-label={t('pwa.card.aria')}
      data-fe-floating="pwa-install"
      data-testid="pwa-install-card"
      data-slim={slim ? 'true' : undefined}
      className={cn(
        'fe-reveal [--fe-duration:0.22s] [--fe-rise:10px] print:hidden',
        floating && 'fixed inset-x-3 bottom-[calc(var(--fe-bottom-clear,env(safe-area-inset-bottom,0px))+12px)] z-40 mx-auto max-w-md',
        'rounded-2xl fe-glass-pop shadow-2xl',
        slim ? 'p-2.5' : 'p-4',
        className,
      )}
    >
      {slim ? (
        <div className="flex items-center gap-2.5">
          <img src="/icons/icon-192.png" alt="" width="36" height="36" className="h-9 w-9 shrink-0 rounded-lg" />
          <p className="min-w-0 flex-1 text-sm font-semibold leading-snug text-text-primary">{t('pwa.card.title')}</p>
          <Button variant="secondary" onClick={() => setStepsOpen(true)} aria-expanded="false" className="shrink-0">{t('c9a.pwa.how')}</Button>
          <button
            type="button"
            onClick={onLater}
            aria-label={t('common.close')}
            className={cn(FOCUS_RING, 'fe-press flex h-11 w-11 shrink-0 items-center justify-center rounded-md text-text-tertiary hover:text-text-primary')}
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      ) : (
        <>
          <div className="flex items-start gap-3">
            <img src="/icons/icon-192.png" alt="" width="44" height="44" className="h-11 w-11 shrink-0 rounded-xl" />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-text-primary">{t(ios ? 'pwa.ios.title' : 'pwa.card.title')}</p>
              <p className="mt-0.5 text-sm leading-snug text-text-secondary">{t(ios ? 'pwa.ios.body' : 'pwa.card.body')}</p>
            </div>
            <button
              type="button"
              onClick={onLater}
              aria-label={t('common.close')}
              className={cn(FOCUS_RING, 'fe-press -mr-1 -mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-md text-text-tertiary hover:text-text-primary pointer-coarse:h-11 pointer-coarse:w-11')}
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
          {ios && <div className="mt-3"><IosHint /></div>}
          <div className="mt-3 flex items-center gap-2">
            {ios ? (
              <Button onClick={onAck} className="flex-1">{t('pwa.ios.ok')}</Button>
            ) : (
              <Button onClick={onInstall} loading={busy} className="flex-1">{t('pwa.card.install')}</Button>
            )}
            <Button variant="secondary" onClick={onLater} className="flex-1">{t('pwa.card.later')}</Button>
          </div>
        </>
      )}
    </aside>
  );
}
