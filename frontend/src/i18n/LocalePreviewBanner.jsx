import { useState } from 'react';
import { Languages, X } from 'lucide-react';
import { useLocale } from './localeContext';

/**
 * Режим предпросмотра языка (?preview_locale=…), только для разработки и проверки. На рабочих хостах не показывается.
 * Свёрнут в маленькую иконку внизу слева, чтобы не закрывать кнопки и ссылки; по нажатию раскрывается пояснение
 * и кнопка выхода.
 */
export default function LocalePreviewBanner() {
  const { isPreview, locale, setPreviewLocale, t } = useLocale();
  const [open, setOpen] = useState(false);
  if (!isPreview) return null;

  if (!open) {
    return (
      <button
        type="button"
        data-testid="locale-preview-toggle"
        aria-label={t('preview.banner')}
        aria-expanded="false"
        onClick={() => setOpen(true)}
        className="fixed bottom-3 left-3 z-[60] flex h-11 w-11 items-center justify-center rounded-full border border-champagne/30 bg-obsidian text-champagne shadow-sm opacity-80 hover:opacity-100"
      >
        <Languages className="h-4 w-4" aria-hidden="true" />
      </button>
    );
  }

  return (
    <div
      role="status"
      className="fixed bottom-3 left-3 z-[60] w-max max-w-[calc(100%-1.5rem)] rounded-2xl border border-champagne/30 bg-obsidian p-3 text-xs text-text-secondary shadow-sm"
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
