import { useNavigate, useSearchParams } from 'react-router-dom';
import ChipGroup, { ChipLink } from './ChipGroup';
import { useT } from '../i18n';
import MobileNavSelect from './MobileNavSelect';
import { PickerCard, PickerLabel } from './PickerParts';
import { useViewModeSummary } from './viewModesContext';

/**
 * Внутрисемейный переключатель карточек («Все товары»/«Продовольственные»/...).
 *
 * `?mode=` берём из текущего URL (источник правды), чтобы при переходе на sibling
 * сохранялся выбранный «Режим инфляции» (месячная, недельная, …).
 *
 * `basePath` — префикс URL без кода: `/russia/indicator` (дефолт) или
 * `/{country}/indicator` для мира (ADR-0013).
 * На &lt;lg при 3+ срезах — нативный select (как темы у страны/региона).
 */
export default function VariantGroupPicker({
  group,
  currentCode,
  embedded = false,
  basePath = '/russia/indicator',
}) {
  const t = useT();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const currentItem = group?.codes?.find((item) => item.code === currentCode);
  useViewModeSummary(
    'variant', 10,
    currentItem ? (currentItem.labelKey ? t(currentItem.labelKey) : currentItem.label) : '',
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
        <MobileNavSelect
          label={groupLabel}
          value={currentCode}
          options={codeOptions.map((item) => ({
            value: item.code,
            label: item.displayLabel,
          }))}
          onChange={(code) => {
            navigate(`${root}/${code}${suffix}`, { preventScrollReset: true });
          }}
          className="mb-0"
        />
      ) : null}

      <div className={useMobileSelect ? 'hidden lg:block' : undefined}>
        <PickerLabel>{groupLabel}</PickerLabel>
        <ChipGroup label={groupLabel} grid>
          {codeOptions.map((item) => (
            <ChipLink
              key={item.code}
              active={item.code === currentCode}
              to={`${root}/${item.code}${suffix}`}
              preventScrollReset
            >
              {item.displayLabel}
            </ChipLink>
          ))}
        </ChipGroup>
      </div>
    </>
  );

  return <PickerCard compact={embedded} className="min-w-0">{body}</PickerCard>;
}
