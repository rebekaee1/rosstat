import { useEffect, useState } from 'react';
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { cn } from '../lib/format';
import useDocumentMeta from '../lib/useMeta';
import { useAuth } from '../context/authContext';
import { useT } from '../i18n';
import { useCabinetConfig, useFeed } from '../lib/useCabinet';
import Chip from '../components/Chip';
import ChipGroup from '../components/ChipGroup';
import Spinner from '../components/Spinner';
import ProfilePanel from '../components/cabinet/ProfilePanel';
import SavedList from '../components/cabinet/SavedList';
import WatchList from '../components/cabinet/WatchList';
import ExportHistory from '../components/cabinet/ExportHistory';
import PrefsForm from '../components/cabinet/PrefsForm';
import '../styles/w5-pages.css';
import '../styles/k8-tools.css';
import '../styles/c11b-cabinet.css';

/** Разделы кабинета; адрес `/account?tab=…`. Без включённого кабинета остаётся только профиль, как раньше. */
const TABS = ['saved', 'compare', 'watches', 'exports', 'prefs', 'profile'];
const DEFAULT_TAB = 'saved';

export default function Account() {
  const t = useT();
  useDocumentMeta({ title: t('account.metaTitle'), path: '/account', robots: 'noindex, nofollow' });
  const navigate = useNavigate();
  const location = useLocation();
  const [params, setParams] = useSearchParams();
  const { user, isLoading, isAuthed } = useAuth();
  const cabinet = useCabinetConfig();
  const feed = useFeed();
  // Долгий ответ настройки не должен держать страницу в загрузке: через 2,5 с показываем профиль, как при выключенном кабинете.
  const [patient, setPatient] = useState(true);
  useEffect(() => {
    const id = window.setTimeout(() => setPatient(false), 2500);
    return () => window.clearTimeout(id);
  }, []);

  useEffect(() => {
    if (!isLoading && !isAuthed) navigate('/login', { replace: true });
  }, [isLoading, isAuthed, navigate]);

  if (isLoading) {
    return (
      <div role="status" className="fe-data-page max-w-2xl mx-auto px-4 pt-28 pb-24 flex items-center gap-3 text-text-secondary">
        <Spinner size={18} />
        {t('common.loading')}
      </div>
    );
  }
  if (!user) return null;

  const requested = params.get('tab');
  // Ссылка «Оставить отзыв» (/account#feedback) ведёт в профиль, где живёт форма.
  const wantsProfile = requested === 'profile' || location.hash === '#feedback';
  const tabs = cabinet.enabled ? TABS : [];
  const tab = !cabinet.enabled ? 'profile'
    : wantsProfile ? 'profile'
      : TABS.includes(requested) ? requested : DEFAULT_TAB;
  // Пока неизвестно, включён ли кабинет, и нужен не профиль, подождать ответа: иначе содержимое успеет смениться.
  const waiting = !cabinet.ready && patient && !wantsProfile;

  const go = (next) => {
    const nextParams = new URLSearchParams(params);
    nextParams.set('tab', next);
    setParams(nextParams, { replace: true });
  };

  const initial = (user.display_name || user.email || '?').trim().charAt(0).toUpperCase();

  return (
    <div className={cabinet.enabled ? 'fe-data-page max-w-3xl mx-auto px-4 pt-28 pb-24' : 'fe-data-page max-w-2xl mx-auto px-4 pt-28 pb-24'}>
      <header className="fe-reveal mb-6 flex items-center gap-4">
        <span className="w5-avatar" aria-hidden="true">{initial}</span>
        <div className="min-w-0">
          <h1 className="font-display text-2xl font-bold text-text-primary">{t('account.title')}</h1>
          <p className="truncate text-sm text-text-secondary">{t('w5.account.signedInAs')} {user.email}</p>
        </div>
      </header>
      <p className="mb-6 text-sm text-text-secondary">
        {cabinet.enabled ? t('c11b.account.intro') : t('account.intro')}
      </p>

      {tabs.length > 0 && (
        <ChipGroup nowrap role="tablist" label={t('c11b.tabs.aria')} className="c11b-tabs fe-fade-x scrollbar-hide">
          {tabs.map((id) => (
            <Chip
              key={id}
              role="tab"
              id={`account-tab-${id}`}
              aria-selected={tab === id}
              aria-pressed={undefined}
              aria-controls="account-panel"
              active={tab === id}
              onClick={() => go(id)}
            >
              {t(`c11b.tabs.${id}`)}
              {id === 'watches' && feed.newCount > 0 ? <span className="c11b-pill c11b-pill--tab">{feed.newCount}</span> : null}
            </Chip>
          ))}
        </ChipGroup>
      )}

      <div id="account-panel" role={tabs.length ? 'tabpanel' : undefined} aria-labelledby={tabs.length ? `account-tab-${tab}` : undefined} className={cn('c11b-panel', tab !== 'profile' && 'fe-panel fe-reveal rounded-3xl p-5 shadow-sm')}>
        {waiting ? (
          <div role="status" className="c11b-empty"><Spinner size={16} /> {t('common.loading')}</div>
        ) : null}
        {!waiting && tab === 'saved' && <SavedList mode="favorites" />}
        {!waiting && tab === 'compare' && <SavedList mode="comparisons" />}
        {!waiting && tab === 'watches' && <WatchList />}
        {!waiting && tab === 'exports' && <ExportHistory />}
        {!waiting && tab === 'prefs' && <PrefsForm />}
        {!waiting && tab === 'profile' && <ProfilePanel />}
      </div>
    </div>
  );
}
