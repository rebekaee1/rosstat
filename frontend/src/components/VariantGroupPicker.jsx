import { useNavigate, useSearchParams } from 'react-router-dom';
import { ChipLink, OverflowChipGroup } from './ChipGroup';
import { useT } from '../i18n';
import MobileNavSelect from './MobileNavSelect';
import { PickerCard, PickerLabel } from './PickerParts';
import { useViewModeSummary } from './viewModesContext';

const VISIBLE_VARIANTS = 8;

/** Сравнение без регистра, пробелов и знаков: «Валовой внутренний продукт, в текущих ценах» и то же в заголовке страницы. */
function sameText(a, b) {
  const norm = (v) => String(v || '').toLowerCase().replace(/[^a-zа-яё0-9]+/gi, ' ').trim();
  return norm(a) !== '' && norm(a) === norm(b);
}

/**
 * Внутрисемейный переключатель карточек («Все товары»/«Продовольственные»/...).
 *
 * `?mode=` берём из текущего URL (источник правды), чтобы при переходе на sibling
 * сохранялся выбранный «Режим инфляции» (месячная, недельная, …).
 *
 * `basePath` — префикс URL без кода: `/russia/indicator` (дефолт) или
 * `/{country}/indicator` для мира (ADR-0013).
 * На &lt;lg при 3+ срезах — нативный select (как темы у страны/региона).
 *
 * Чип показывает `item.short` (короткое имя, см. lib/viewModeShortLabels.js), полное имя уходит в `title`.
 * `pageTitle` — заголовок страницы: если выбранный вариант совпадает с ним, в свёрнутой строке телефона
 * его не повторяем (раньше «Вид графика» дублировал заголовок страницы).
 */
export default function VariantGroupPicker({
  group,
  currentCode,
  embedded = false,
  basePath = '/russia/indicator',
  pageTitle = '',
}) {
  const t = useT();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const currentItem = group?.codes?.find((item) => item.code === currentCode);
  const currentLabel = currentItem ? (currentItem.labelKey ? t(currentItem.labelKey) : currentItem.label) : '';
  const duplicatesTitle = Boolean(pageTitle) && sameText(currentItem?.label || currentLabel, pageTitle);
  useViewModeSummary(
    'variant', 10,
    duplicatesTitle ? '' : (currentItem?.short || currentLabel),
    duplicatesTitle ? t('w6e.mode.values') : '',
  );
  if (!group) return null;
  const qs = searchParams.toString();
  const suffix = qs ? `?${qs}` : '';
  const root = (basePath || '/russia/indicator').replace(/\/$/, '');
  const useMobileSelect = group.codes.length >= 3;
  const groupLabel = group.labelKey ? t(group.labelKey) : group.label;
  const codeOptions = group.codes.map((item) => ({
    ...item,
    displayLabel: item.labelKey ? t(item.labelKey) : item.label,
  }));

  const body = (
    <>
      {useMobileSelect ? (
        <div className="lg:hidden">
        <MobileNavSelect
          label={groupLabel}
          value={currentCode}
          options={codeOptions.map((item) => ({
            value: item.code,
            label: item.displayLabel,
          }))}
          pickTitle={t('w6e.pickVariant')}
          onChange={(code) => {
            navigate(`${root}/${code}${suffix}`, { preventScrollReset: true });
          }}
          className="mb-0"
        />
        </div>
      ) : null}

      <div className={useMobileSelect ? 'hidden lg:block' : undefined}>
        <PickerLabel>{groupLabel}</PickerLabel>
        {/* До восьми чипов сразу (выбранный не прячется), остальные под «Ещё показатели»: полоса выбора не растёт на пять рядов. */}
        <OverflowChipGroup
          label={groupLabel}
          grid
          limit={VISIBLE_VARIANTS}
          moreLabel={t('z4.variants.more')}
          items={codeOptions}
          isActive={(item) => item.code === currentCode}
          renderChip={(item) => (
            <ChipLink
              key={item.code}
              active={item.code === currentCode}
              to={`${root}/${item.code}${suffix}`}
              preventScrollReset
              title={item.title || undefined}
            >
              {item.short || item.displayLabel}
            </ChipLink>
          )}
        />
      </div>
    </>
  );

  return <PickerCard compact={embedded} className="min-w-0 fe-pick-card--variant">{body}</PickerCard>;
}
