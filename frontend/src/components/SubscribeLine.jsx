// Привлечение (совет 19.11.2026): одна строка под числом на 10 главных страницах входа из Яндекса.
//
// Что в строке (всё за флагами бэкенда, см. lib/siteAcq.js):
// - когда выйдет новое значение по нашему календарю, или честное «источник задерживает»;
// - «Присылать в Telegram» — ссылка в публичного бота `?start=site_<тема>` (только на темах бота
//   и только когда данные не задерживаются: обещать новое значение, которого нет, нельзя);
// - место для почтового способа (делает ветка почты, зона №4: `emailSlot`);
// - «Скачать таблицу за все годы» — тот же обработчик и тот же замок, что у кнопки над графиком.
// Без всплывающих окон и таймеров: строка стоит в странице и никому не мешает (решение совета, спор 5).
// События: subscribe_line_view (один раз на страницу и тему), subscribe_line_click {topic, channel, path}.
import { useEffect, useMemo, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { Download, Send } from 'lucide-react';
import { useCalendarUpcoming } from '../lib/hooks';
import { formatDate } from '../lib/format';
import { glueDate } from '../lib/periodPhrase';
import {
  FIRST_SCREEN_CODES,
  PAGE_TOPIC,
  botStartUrl,
  isDelayed,
  lineCopy,
  releaseCodeOf,
  useSiteAcqConfig,
} from '../lib/siteAcq';
import { track, events } from '../lib/track';
import { useLocale, useT } from '../i18n';
import '../styles/acq-line.css';

function dayText(value, locale, today) {
  const text = formatDate(value, 'day', locale);
  if (text === '—') return null;
  const year = String(today.getFullYear());
  return glueDate(text.endsWith(` ${year}`) ? text.slice(0, -(year.length + 1)) : text);
}

function monthText(value, locale) {
  const text = formatDate(value, 'full', locale);
  if (text === '—') return null;
  const month = text.split(' ')[0];
  return locale === 'en' ? month : month.toLowerCase();
}

export default function SubscribeLine({
  code,
  frequency,
  lastDate,
  freshness = null,
  onDownloadExcel = null,
  emailSlot = null,
  today = null,
}) {
  const t = useT();
  const { locale } = useLocale();
  const { pathname } = useLocation();
  const config = useSiteAcqConfig();
  const now = useMemo(() => today || new Date(), [today]);

  const onPage = FIRST_SCREEN_CODES.has(code);
  const topic = PAGE_TOPIC[code] || null;
  const lineOn = Boolean(config.line && topic && config.topics.includes(topic) && config.bot);
  const firstOn = Boolean(config.first_screen && onPage);
  const releaseCode = (lineOn || firstOn) ? releaseCodeOf(code) : null;
  const { data: upcoming } = useCalendarUpcoming(
    { indicator_code: releaseCode || '', limit: 1 },
    { enabled: Boolean(releaseCode) },
  );
  const event = releaseCode ? upcoming?.events?.[0] : null;
  const nextRelease = event?.scheduled_date || null;
  const nextEstimated = Boolean(event?.is_estimated);

  const delayed = isDelayed({ freshness, frequency, lastDate, nextRelease, today: now });
  const copy = lineCopy({ code, frequency, lastDate, nextRelease, nextEstimated, delayed });
  const showTelegram = lineOn && !delayed;
  const showWhen = Boolean(copy) && (firstOn || showTelegram);
  const showDownload = firstOn && typeof onDownloadExcel === 'function';

  const seen = useRef('');
  useEffect(() => {
    if (!showTelegram) return;
    const key = `${pathname}|${topic}`;
    if (seen.current === key) return;
    seen.current = key;
    track(events.SUBSCRIBE_LINE_VIEW, { topic, channel: 'telegram', path: pathname });
  }, [showTelegram, pathname, topic]);

  if (!onPage || !(showWhen || showTelegram || showDownload || emailSlot)) return null;

  const whenText = copy ? t(`acq.when.${copy.key}`, {
    date: copy.params.date ? dayText(copy.params.date, locale, now) : '',
    month: copy.params.month ? monthText(copy.params.month, locale) : '',
  }) : '';
  const href = showTelegram ? botStartUrl(config.bot, topic) : null;

  return (
    <section className="acq-line fe-glass-lite" data-testid="subscribe-line" data-topic={topic || ''} aria-label={t('acq.aria')}>
      {showWhen ? (
        <p className={`acq-line__when${delayed ? ' acq-line__when--late' : ''}`} data-testid="subscribe-line-when">{whenText}</p>
      ) : null}
      <div className="acq-line__actions">
        {href ? (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="acq-line__btn acq-line__btn--main fe-press"
            data-testid="subscribe-line-telegram"
            onClick={() => track(events.SUBSCRIBE_LINE_CLICK, { topic, channel: 'telegram', path: pathname })}
          >
            <Send size={15} aria-hidden="true" />
            <span>{t('acq.telegram')}</span>
          </a>
        ) : null}
        {/* Почтовый способ той же строки — зона №4 (ветка feat/acq-mail) подставляет сюда свой элемент. */}
        {emailSlot}
        {showDownload ? (
          <button
            type="button"
            className="acq-line__btn fe-press"
            data-testid="subscribe-line-download"
            onClick={() => onDownloadExcel()}
          >
            <Download size={15} aria-hidden="true" />
            <span>{t('acq.download')}</span>
          </button>
        ) : null}
      </div>
    </section>
  );
}
