import { useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  PREVIEW_QUERY,
  apexLocaleEnEnabled,
  normalizeHost,
  readLocalePreference,
  setLocalePreference,
} from './locale';

/**
 * До cutover EN живёт в ?preview_locale=. Клиентские Link его снимают —
 * возвращаем query и пишем cookie, чтобы крошки/API/числа не уезжали в RU.
 */
export default function LocalePreviewSync() {
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    if (apexLocaleEnEnabled()) return;
    const host = normalizeHost(window.location.hostname);
    if (host.startsWith('en.') || host.startsWith('ru.')) return;

    const params = new URLSearchParams(location.search);
    const preview = params.get(PREVIEW_QUERY);
    if (preview === 'en' || preview === 'ru') {
      if (readLocalePreference() !== preview) setLocalePreference(preview);
      return;
    }
    if (readLocalePreference() !== 'en') return;
    params.set(PREVIEW_QUERY, 'en');
    const search = params.toString();
    navigate(
      {
        pathname: location.pathname,
        search: search ? `?${search}` : '',
        hash: location.hash,
      },
      { replace: true },
    );
  }, [location.hash, location.pathname, location.search, navigate]);

  return null;
}
