import { useEffect, useId, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Info } from 'lucide-react';
import { isWeoMapConcept } from '../lib/homeWorkbench';
import { russiaCategoryPath } from '../lib/sitePaths';
import { useT } from '../i18n';

/**
 * Дискретная справка у карты для концептов МВФ/WEO: hover/focus и tap.
 */
export default function WorldMapConceptNote({ conceptSlug }) {
  const t = useT();
  const tipId = useId();
  const rootRef = useRef(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return undefined;
    const onDoc = (event) => {
      if (!rootRef.current?.contains(event.target)) setOpen(false);
    };
    const onKey = (event) => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  if (!isWeoMapConcept(conceptSlug)) return null;

  return (
    <div
      ref={rootRef}
      className="relative shrink-0"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        type="button"
        aria-expanded={open}
        aria-controls={tipId}
        aria-label={t('home.map.weoNoteAria')}
        onClick={() => setOpen((prev) => !prev)}
        onFocus={() => setOpen(true)}
        className="inline-flex h-7 w-7 items-center justify-center rounded-lg text-text-tertiary transition-colors hover:bg-champagne/10 hover:text-champagne focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-champagne/40"
      >
        <Info size={14} strokeWidth={1.75} aria-hidden="true" />
      </button>
      {open && (
        <div
          id={tipId}
          role="tooltip"
          className="absolute left-0 top-full z-30 mt-1.5 w-[min(22rem,calc(100vw-2rem))] rounded-xl border border-border-subtle bg-surface px-3.5 py-3 text-[12px] leading-5 text-text-secondary shadow-lg sm:left-auto sm:right-0"
        >
          <p>{t('home.map.weoNote.p1')}</p>
          <p className="mt-2">{t('home.map.weoNote.p2')}</p>
          <p className="mt-2">{t('home.map.weoNote.p3')}</p>
          <div className="mt-2.5 flex flex-wrap gap-x-3 gap-y-1">
            <Link
              to="/methodology"
              className="font-medium text-champagne hover:underline"
            >
              {t('home.map.weoNote.methodology')}
            </Link>
            <Link
              to={russiaCategoryPath('gdp')}
              className="font-medium text-champagne hover:underline"
            >
              {t('home.map.weoNote.russiaGdp')}
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
