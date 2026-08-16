import { useLocale } from './LocaleProvider';

/** Dev / local EN preview banner. Not used for SEO hosts. */
export default function LocalePreviewBanner() {
  const { isPreview, locale, setPreviewLocale, t } = useLocale();
  if (!isPreview) return null;

  return (
    <div
      role="status"
      className="sticky top-0 z-[60] border-b border-champagne/30 bg-obsidian px-4 py-2 text-center text-xs text-text-secondary"
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
