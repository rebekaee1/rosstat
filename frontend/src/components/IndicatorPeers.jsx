// «Этот показатель в других странах» под карточкой «О показателе» (круг 11, F, U11): вместо пустой панели справа от таблицы
// истории короткий список стран, у которых есть тот же ряд, и ссылка на рейтинг. Данные уже в ответе страницы (`peers`).
import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight } from 'lucide-react';
import CountryFlag from './CountryFlag';
import { pickPeers } from '../lib/indicatorPeers';
import { indicatorPath, worldRatingPath } from '../lib/sitePaths';
import { useLocale, useT } from '../i18n';
import '../styles/z4-indicator.css';

export default function IndicatorPeers({ peers, currentSlug, ratingSlug = null }) {
  const t = useT();
  const { locale } = useLocale();
  const list = useMemo(() => pickPeers(peers, currentSlug, locale), [peers, currentSlug, locale]);
  if (list.length === 0 && !ratingSlug) return null;
  return (
    <section className="z4-peers rounded-3xl p-5 fe-glass-lite" aria-labelledby="z4-peers-title" data-testid="indicator-peers">
      <h3 id="z4-peers-title" className="mb-3 text-base font-semibold text-text-primary">{t('c11f.ind.peers.title')}</h3>
      {list.length > 0 && (
        <ul className="z4-peers__list">
          {list.map((peer) => (
            <li key={peer.country_slug}>
              <Link to={indicatorPath(peer.country_slug, peer.indicator_code)} className="z4-peers__link fe-press">
                <CountryFlag code={peer.country_code} />
                <span className="min-w-0">{peer.name}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
      {ratingSlug ? (
        <Link to={worldRatingPath(ratingSlug)} className="z4-peers__rating fe-press">
          {t('c11f.ind.peers.rating')}
          <ArrowUpRight size={13} aria-hidden="true" />
        </Link>
      ) : null}
    </section>
  );
}
