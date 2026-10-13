import { useEffect, useMemo, useState } from 'react';
import { usePending } from '../../lib/usePending';
import { CheckCircle2 } from 'lucide-react';
import { useLocale, useT } from '../../i18n';
import { fetchPrefs, savePrefs } from '../../lib/cabinetApi';
import { cabinetErrorCode, cabinetErrorKey } from '../../lib/cabinetItems';
import { applyPrefs } from '../../lib/cabinetPrefs';
import { countryPublicName } from '../../lib/homeWorkbench';
import { useWorldCountries } from '../../lib/worldApi';
import Button from '../Button';
import Chip from '../Chip';
import ChipGroup from '../ChipGroup';
import Spinner from '../Spinner';

const NUMBER_FORMATS = ['ru', 'en'];
// Рубль в списке не нужен: конвертер и так открывается парой «USD → RUB», выбор «RUB» ничего не менял бы (круг 13).
const CURRENCIES = ['USD', 'EUR', 'CNY'];

/**
 * Оставляет только поля, которые принимает сервер (он отвечает 422 на любое чужое).
 * Поля `locale`, `units`, `newsletter_topics` из формы убраны (круг 13), но ранее сохранённые значения проходят насквозь:
 * сохранение не стирает то, что человек выбрал раньше, и сервер по-прежнему принимает все шесть полей.
 */
function pickPrefs(data) {
  const out = {};
  if (data?.locale === 'ru' || data?.locale === 'en') out.locale = data.locale;
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
 * Настройки: формат чисел, валюта конвертера, главная страна. Все три действуют на сайте (`lib/cabinetPrefs.js`).
 * Круг 13 (C2): поля «язык по умолчанию» (язык задаёт адрес страницы, ADR-0003/0013), «единицы» (общего переключателя единиц
 * в данных нет) и «темы рассылки» (письма по темам не отправляются, согласие живёт в «Профиле») убраны из формы: поле, которое
 * ничего не меняет, обманывает человека.
 */
export default function PrefsForm() {
  const t = useT();
  const { locale } = useLocale();
  const countries = useWorldCountries();
  const [state, setState] = useState({ status: 'loading', data: {} });
  const [draft, setDraft] = useState({});
  const { pending: saving, run } = usePending();
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
  const dirty = JSON.stringify(pickPrefs(draft)) !== JSON.stringify(state.data);

  const submit = (event) => {
    event.preventDefault();
    return run(async () => {
      setError(null);
      try {
        const res = await savePrefs(pickPrefs(draft));
        const data = pickPrefs(res?.data);
        setState({ status: 'ready', data });
        setDraft(data);
        setSaved(true);
        // Сохранённое сразу начинает действовать на сайте (формат чисел, валюта конвертера, главная страна).
        applyPrefs(data);
      } catch (err) {
        setError(t(cabinetErrorKey(cabinetErrorCode(err))));
      }
    });
  };

  const pick = (field, value, label) => (
    <Chip key={value} active={draft[field] === value} onClick={() => set({ [field]: draft[field] === value ? undefined : value })}>{label}</Chip>
  );

  return (
    <form onSubmit={submit} className="c11b-prefs">
      <p className="c11b-hint">{t('c12u.prefs.intro')}</p>
      <Field label={t('c11b.prefs.numbers')}>
        <ChipGroup label={t('c11b.prefs.numbers')}>
          {NUMBER_FORMATS.map((v) => pick('number_format', v, t(`c11b.prefs.numbers.${v}`)))}
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
      <div className="c11b-foot">
        <Button type="submit" pending={saving} disabled={!dirty}>{t('common.save')}</Button>
        {saved ? (
          <span role="status" className="c11b-ok"><CheckCircle2 size={16} aria-hidden="true" /> {t('c11b.prefs.saved')}</span>
        ) : null}
      </div>
      <p role="alert" className="c11b-row__err empty:hidden">{error}</p>
    </form>
  );
}
