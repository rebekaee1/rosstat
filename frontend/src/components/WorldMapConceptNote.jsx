import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Link } from 'react-router-dom';
import { Info } from 'lucide-react';
import { isWeoMapConcept } from '../lib/homeWorkbench';
import { russiaCategoryPath } from '../lib/sitePaths';
import { useT } from '../i18n';

const TIP_WIDTH_PX = 352; // ~22rem
const TIP_GAP_PX = 6;
const VIEW_PAD_PX = 16;

function tipPosition(anchorRect) {
  if (!anchorRect || typeof window === 'undefined') return null;
  const width = Math.min(TIP_WIDTH_PX, window.innerWidth - VIEW_PAD_PX * 2);
  let left = anchorRect.left;
  // На широких экранах якорь справа у чипов — выравниваем по правому краю кнопки.
  if (anchorRect.left + width > window.innerWidth - VIEW_PAD_PX) {
    left = anchorRect.right - width;
  }
  left = Math.max(VIEW_PAD_PX, Math.min(left, window.innerWidth - width - VIEW_PAD_PX));
  const top = anchorRect.bottom + TIP_GAP_PX;
  return { top, left, width };
}

/**
 * Дискретная справка у карты для концептов МВФ/WEO: hover/focus и tap.
 * Тултип в portal (fixed), чтобы соседние чипы и overflow родителя не клипали текст.
 */
export default function WorldMapConceptNote({ conceptSlug }) {
  const t = useT();
  const tipId = useId();
  const rootRef = useRef(null);
  const tipRef = useRef(null);
  const closeTimer = useRef(null);
  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState(null);

  const clearCloseTimer = () => {
    if (closeTimer.current != null) {
      window.clearTimeout(closeTimer.current);
      closeTimer.current = null;
    }
  };

  const scheduleClose = () => {
    clearCloseTimer();
    closeTimer.current = window.setTimeout(() => setOpen(false), 120);
  };

  useLayoutEffect(() => {
    if (!open) return undefined;
    const update = () => {
      const rect = rootRef.current?.getBoundingClientRect();
      setCoords(tipPosition(rect));
    };
    update();
    window.addEventListener('resize', update);
    window.addEventListener('scroll', update, true);
    return () => {
      window.removeEventListener('resize', update);
      window.removeEventListener('scroll', update, true);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return undefined;
    const onDoc = (event) => {
      const t = event.target;
      if (rootRef.current?.contains(t) || tipRef.current?.contains(t)) return;
      setOpen(false);
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

  useEffect(() => () => clearCloseTimer(), []);

  if (!isWeoMapConcept(conceptSlug)) return null;

  const tip = open && coords && typeof document !== 'undefined'
    ? createPortal(
      <div
        ref={tipRef}
        id={tipId}
        role="tooltip"
        onMouseEnter={() => {
          clearCloseTimer();
          setOpen(true);
        }}
        onMouseLeave={scheduleClose}
        style={{
          position: 'fixed',
          top: coords.top,
          left: coords.left,
          width: coords.width,
        }}
        className="z-[220] rounded-xl border border-border-subtle bg-surface px-3.5 py-3 text-[12px] leading-5 text-text-secondary shadow-lg"
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
      </div>,
      document.body,
    )
    : null;

  return (
    <div
      ref={rootRef}
      className="relative shrink-0"
      onMouseEnter={() => {
        clearCloseTimer();
        setOpen(true);
      }}
      onMouseLeave={scheduleClose}
    >
      <button
        type="button"
        aria-expanded={open}
        aria-controls={tipId}
        aria-label={t('home.map.weoNoteAria')}
        onClick={() => {
          clearCloseTimer();
          setOpen((prev) => !prev);
        }}
        onFocus={() => {
          clearCloseTimer();
          setOpen(true);
        }}
        className="inline-flex h-7 w-7 items-center justify-center rounded-lg text-text-tertiary transition-colors hover:bg-champagne/10 hover:text-champagne focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-champagne/40"
      >
        <Info size={14} strokeWidth={1.75} aria-hidden="true" />
      </button>
      {tip}
    </div>
  );
}
