import { useEffect, useState } from 'react';
import { Languages, X } from 'lucide-react';
import { useLocale } from './localeContext';
import '../styles/z2-shell.css';

/** Пока страница прокручивается (и ещё полсекунды после), значок прячется: он не должен лежать поверх текста. */
function useHiddenWhileScrolling() {
  const [scrolling, setScrolling] = useState(false);
  useEffect(() => {
    let timer = 0;
    const onScroll = () => {
      setScrolling(true);
      window.clearTimeout(timer);
      timer = window.setTimeout(() => setScrolling(false), 600);
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => {
      window.removeEventListener('scroll', onScroll);
      window.clearTimeout(timer);
    };
  }, []);
  return scrolling;
}

/**
 * Режим предпросмотра языка (?preview_locale=…), только для разработки и проверки. На рабочих хостах не показывается.
 * Свёрнут в маленькую полупрозрачную иконку у правого нижнего края (над плашкой cookie, если она на экране),
 * прячется при прокрутке, чтобы не закрывать текст; по нажатию раскрывается пояснение и кнопка выхода.
 */
export default function LocalePreviewBanner() {
  const { isPreview, locale, setPreviewLocale, t } = useLocale();
  const [open, setOpen] = useState(false);
  const scrolling = useHiddenWhileScrolling();
  if (!isPreview) return null;

  // Над плашкой cookie, над док-панелью телефона и плашкой «Результат»: их высоты лежат в --fe-cookie-h, --fe-dock-h и --fe-sticky-h
  // (0, пока их нет на экране; круг 9 добавил плашку «Результат»).
  const lift = { bottom: 'calc(var(--fe-cookie-h, 0px) + var(--fe-dock-h, 0px) + var(--fe-sticky-h, 0px) + 8px)' };

  if (!open) {
    return (
      <button
        type="button"
        data-testid="locale-preview-toggle"
        data-hidden={scrolling ? 'true' : 'false'}
        aria-label={t('preview.banner')}
        aria-expanded="false"
        onClick={() => setOpen(true)}
        style={lift}
        className="z2-preview-toggle fixed right-2 z-[60] flex h-11 w-11 items-center justify-center rounded-full text-text-primary opacity-85 hover:opacity-100 focus-visible:opacity-100 fe-glass-2"
      >
        <Languages className="h-4 w-4" aria-hidden="true" />
      </button>
    );
  }

  return (
    <div
      role="status"
      style={lift}
      className="fixed right-2 z-[60] w-max max-w-[calc(100%-1rem)] rounded-2xl p-3 text-xs text-text-secondary shadow-sm fe-glass-pop"
    >
      <div className="flex items-start gap-2">
        <p className="min-w-0 flex-1">{t('preview.banner')}</p>
        <button
          type="button"
          aria-label={t('w7p.preview.close')}
          aria-expanded="true"
          onClick={() => setOpen(false)}
          className="-m-2 flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-text-secondary hover:text-text-primary"
        >
          <X className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
      <button
        type="button"
        className="mt-1 min-h-11 rounded-md bg-champagne/15 px-3 py-1 font-medium text-champagne hover:bg-champagne/25"
        onClick={() => setPreviewLocale(null)}
      >
        {t('preview.exit')} ({locale})
      </button>
    </div>
  );
}
