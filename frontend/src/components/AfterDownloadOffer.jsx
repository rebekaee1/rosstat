import { useCallback, useEffect, useState } from 'react';
import { X } from 'lucide-react';
import { useT } from '../i18n';
import { track, events } from '../lib/track';
import { cn } from '../lib/format';
import { FOCUS_RING } from '../lib/uiTokens';
import TopicMailForm from './TopicMailForm';
import { useTopicMailEnabled } from '../lib/topicMail';
import { useWatch } from '../lib/useCabinet';
import '../styles/acq-mail.css';

/**
 * Предложение после скачивания (совет 19.11.2026, пункт 3.2): человек скачал файл российского показателя —
 * «Присылать новые значения этого ряда на почту?». Один раз на ряд за вкладку; «Закрыть» убирает предложение
 * для этого ряда до конца сессии. Мировые ряды (у скачивания есть страна) не предлагаются: письма «колокольчика»
 * по почте подключены к федеральным показателям. Вошедшему, который уже следит за рядом (колокольчик), предложение
 * не показывается (пока список слежений не загружен — тоже). Флаг сервера выключен — ничего не рисуется.
 * Подключается один раз в оболочке приложения.
 */
const SEEN_KEY = 'fe:acq:offer-seen';

function seen() {
  try { return new Set(JSON.parse(window.sessionStorage.getItem(SEEN_KEY) || '[]')); } catch { return new Set(); }
}
function markSeen(code) {
  try {
    const s = seen();
    s.add(code);
    window.sessionStorage.setItem(SEEN_KEY, JSON.stringify([...s].slice(-50)));
  } catch { /* не критично */ }
}

export default function AfterDownloadOffer() {
  const enabled = useTopicMailEnabled();
  const [code, setCode] = useState(null);
  const close = useCallback(() => setCode(null), []);

  useEffect(() => {
    if (!enabled) return undefined;
    const onDone = (e) => {
      const d = e?.detail || {};
      if (!d.code || d.country || seen().has(d.code)) return;
      markSeen(d.code);
      setCode(d.code);
    };
    window.addEventListener('fe:download-done', onDone);
    return () => window.removeEventListener('fe:download-done', onDone);
  }, [enabled]);

  if (!enabled || !code) return null;
  return <OfferCard key={code} code={code} onClose={close} />;
}

function OfferCard({ code, onClose }) {
  const t = useT();
  const { authed, watching, loaded } = useWatch('indicator', code);
  const hidden = authed && (!loaded || watching);
  useEffect(() => {
    if (!hidden) track(events.DOWNLOAD_MAIL_OFFER_VIEW, { indicator: code });
  }, [hidden, code]);
  if (hidden) return null;
  return (
    <aside className="acq-offer fe-reveal [--fe-duration:0.2s] [--fe-rise:8px]" aria-label={t('topicMail.offerTitle')}
      data-testid="after-download-offer">
      <div className="acq-offer__head">
        <p className="acq-offer__title">{t('topicMail.offerTitle')}</p>
        <button type="button" onClick={onClose} aria-label={t('common.close')} className={cn(FOCUS_RING, 'fe-press acq-offer__close')}>
          <X className="w-4 h-4" aria-hidden="true" />
        </button>
      </div>
      <TopicMailForm code={code} source="download" compact />
    </aside>
  );
}
