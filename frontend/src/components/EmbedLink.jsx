// «Встроить»: ведёт в конструктор виджетов с уже выбранным показателем. Стоит рядом со «Скачать» над графиком.
import { Link } from 'react-router-dom';
import { Code2 } from 'lucide-react';
import { track, events } from '../lib/track';
import { useT } from '../i18n';

export default function EmbedLink({ code }) {
  const t = useT();
  if (!code) return null;
  return (
    <Link
      to={`/widgets?code=${encodeURIComponent(code)}`}
      title={t('w6g.embed.linkHint')}
      onClick={() => track(events.RELATED_LINK_CLICK, { from: code, to: 'widgets', surface: 'indicator-embed' })}
      className="fe-help-link"
      data-no-export="true"
    >
      <Code2 className="h-4 w-4 shrink-0" aria-hidden="true" />
      <span>{t('w6g.embed.link')}</span>
    </Link>
  );
}
