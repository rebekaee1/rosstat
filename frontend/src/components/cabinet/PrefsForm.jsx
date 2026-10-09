import { useEffect, useMemo, useState } from 'react';
import { CheckCircle2 } from 'lucide-react';
import { useLocale, useT } from '../../i18n';
import { fetchPrefs, savePrefs } from '../../lib/cabinetApi';
import { cabinetErrorCode, cabinetErrorKey } from '../../lib/cabinetItems';
import { countryPublicName } from '../../lib/homeWorkbench';
import { useWorldCountries } from '../../lib/worldApi';
import Button from '../Button';
import Chip from '../Chip';
import ChipGroup from '../ChipGroup';
import Spinner from '../Spinner';

const LOCALES = ['ru', 'en'];
const NUMBER_FORMATS = ['ru', 'en'];
const UNITS = ['source', 'short'];
const CURRENCIES = ['USD', 'EUR', 'RUB', 'CNY'];
const TOPICS = ['inflation', 'rates', 'currencies', 'calendar'];

/** Оставляет только поля, которые принимает сервер (он отвечает 422 на любое чужое). */
function pickPrefs(data) {
  const out = {};
  if (LOCALES.includes(data?.locale)) out.locale = data.locale;
  if (typeof data?.units === 'string' && data.units) out.units = data.units;
  if (typeof data?.number_format === 'string' && data.number_format) out.number_format = data.number_format;
  if (/^[A-Z]{3}$/.test(data?.currency || '')) out.currency = data.currency;
  if (typeof data?.home_country === 'string' && data.home_country) out.home_country = data.home_country;
  if (Array.isArray(data?.newsletter_topics)) out.newsletter_topics = data.newsletter_topics.filter((x) => typeof x === 'string').slice(0, 12);
  return out;
}

function Field({ label, children }) {
  return (
    <div className="c11b-field">
      <div className="c11b-field__label">{label}</div>
      {children}
    </div>
  );
}

/**
 * Настройки: язык по умолчанию, формат чисел, единицы, валюта, главная страна, темы рассылки.
 * Сервер только хранит выбор; разделы сайта начнут учитывать его по мере обновлений. Темы рассылки не заменяют согласие:
 * оно остаётся в разделе «Профиль», письма пока не отправляются.
 */
export default function PrefsForm() {
  const t = useT();
  const { locale } = useLocale();
  const countries = useWorldCountries();
  const [state, setState] = useState({ status: 'loading', data: {} });
  const [draft, setDraft] = useState({});
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;
    Promise.resolve()
      .then(() => fetchPrefs())
      .then((res) => {
        if (!alive) return;
        const data = pickPrefs(res?.data);
        setState({ status: 'ready', data });
        setDraft(data);
      })
      .catch(() => { if (alive) setState({ status: 'error', data: {} }); });
    return () => { alive = false; };
  }, []);

  const options = useMemo(() => {
    const list = Array.isArray(countries.data?.countries) ? countries.data.countries : [];
    return list
      .filter((c) => c?.slug)
      .map((c) => ({ slug: c.slug, name: countryPublicName(c, locale) }))
      .sort((a, b) => a.name.localeCompare(b.name, locale));
  }, [countries.data, locale]);

  if (state.status === 'loading') return <div role="status" className="c11b-empty"><Spinner size={16} /> {t('common.loading')}</div>;
  if (state.status === 'error') return <div role="alert" className="c11b-empty">{t('c11b.err.generic')}</div>;

  const set = (patch) => { setSaved(false); setDraft((d) => ({ ...d, ...patch })); };
  const toggleTopic = (topic) => {
    const now = draft.newsletter_topics || [];
    set({ newsletter_topics: now.includes(topic) ? now.filter((x) => x !== topic) : [...now, topic] });
  };
  const dirty = JSON.stringify(pickPrefs(draft)) !== JSON.stringify(state.data);

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true); setError(null);
    try {
      const res = await savePrefs(pickPrefs(draft));
      const data = pickPrefs(res?.data);
      setState({ status: 'ready', data });
      setDraft(data);
      setSaved(true);
    } catch (err) {
      setError(t(cabinetErrorKey(cabinetErrorCode(err))));
    } finally {
      setBusy(false);
    }
  };

  const pick = (field, value, label) => (
    <Chip key={value} active={draft[field] === value} onClick={() => set({ [field]: draft[field] === value ? undefined : value })}>{label}</Chip>
  );

  return (
    <form onSubmit={submit} className="c11b-prefs">
      <p className="c11b-hint">{t('c11b.prefs.intro')}</p>
      <Field label={t('c11b.prefs.locale')}>
        <ChipGroup label={t('c11b.prefs.locale')}>
          {LOCALES.map((v) => pick('locale', v, t(`c11b.prefs.locale.${v}`)))}
        </ChipGroup>
      </Field>
      <Field label={t('c11b.prefs.numbers')}>
        <ChipGroup label={t('c11b.prefs.numbers')}>
          {NUMBER_FORMATS.map((v) => pick('number_format', v, t(`c11b.prefs.numbers.${v}`)))}
        </ChipGroup>
      </Field>
      <Field label={t('c11b.prefs.units')}>
        <ChipGroup label={t('c11b.prefs.units')}>
          {UNITS.map((v) => pick('units', v, t(`c11b.prefs.units.${v}`)))}
        </ChipGroup>
      </Field>
      <Field label={t('c11b.prefs.currency')}>
        <ChipGroup label={t('c11b.prefs.currency')}>
          {CURRENCIES.map((v) => pick('currency', v, v))}
        </ChipGroup>
      </Field>
      <Field label={t('c11b.prefs.country')}>
        <select
          className="fe-k8-well c11b-select"
          value={draft.home_country || ''}
          onChange={(e) => set({ home_country: e.target.value || undefined })}
          aria-label={t('c11b.prefs.country')}
        >
          <option value="">{t('c11b.prefs.countryNone')}</option>
          {options.map((o) => <option key={o.slug} value={o.slug}>{o.name}</option>)}
        </select>
      </Field>
      <Field label={t('c11b.prefs.topics')}>
        <ChipGroup label={t('c11b.prefs.topics')}>
          {TOPICS.map((topic) => (
            <Chip key={topic} active={(draft.newsletter_topics || []).includes(topic)} onClick={() => toggleTopic(topic)}>
              {t(`c11b.prefs.topics.${topic}`)}
            </Chip>
          ))}
        </ChipGroup>
        <p className="c11b-hint">{t('c11b.prefs.topicsNote')}</p>
      </Field>
      <div className="c11b-foot">
        <Button type="submit" loading={busy} disabled={!dirty}>{t('common.save')}</Button>
        {saved ? (
          <span role="status" className="c11b-ok"><CheckCircle2 size={16} aria-hidden="true" /> {t('c11b.prefs.saved')}</span>
        ) : null}
      </div>
      <p role="alert" className="c11b-row__err empty:hidden">{error}</p>
    </form>
  );
}
