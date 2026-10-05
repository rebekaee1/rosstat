import { useLocale } from './localeContext';

/** Dev / local EN preview banner. Not used for SEO hosts. */
export default function LocalePreviewBanner() {
  const { isPreview, locale, setPreviewLocale, t } = useLocale();
  if (!isPreview) return null;

  return (
    <div
      role="status"
      className="fixed bottom-2 left-1/2 z-[60] w-max max-w-[calc(100%-1rem)] -translate-x-1/2 rounded-full border border-champagne/30 bg-obsidian px-4 py-1.5 text-center text-xs text-text-secondary shadow-sm"
    >
      <span className="mr-3">{t('preview.banner')}</span>
      <button
        type="button"
        className="rounded-md bg-champagne/15 px-2 py-0.5 font-medium text-champagne hover:bg-champagne/25"
        onClick={() => setPreviewLocale(null)}
      >
        {t('preview.exit')} ({locale})
      </button>
    </div>
  );
}
