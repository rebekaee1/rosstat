import Chip from './Chip';
import ChipGroup, { OverflowChipGroup } from './ChipGroup';
import { PickerCard, PickerLabel, PickerHint } from './PickerParts';
import { useT } from '../i18n';
import { cn } from '../lib/format';
import { pickerHintKey } from '../lib/pickerLabels';
import { modeSummaryText, useViewModeSummary } from './viewModesContext';

/**
 * Двухуровневый переключатель показа (общая отрисовка для всех семейных пикеров).
 * Верхний ряд — смысл («Год к году», «Средняя за период»), под ним одна строка-пояснение,
 * ниже — детализация (по месяцам, по кварталам). Ряды выложены сеткой равных ячеек, без рваных переносов.
 *
 * groups: [{ id, label, rawLabel? }]; subModes: [{ mode, label, disabled?, hint? }].
 * Недоступные подрежимы не показываем: ряд из серых «нет данных» кнопок только занимает место.
 */
export default function ModeGroupsPicker({
  title,
  groups,
  activeGroupId,
  onTopClick,
  subModes = [],
  subGroupLabel,
  currentMode,
  onSubClick,
  compact = false,
  className,
}) {
  const t = useT();
  const activeGroup = groups.find((g) => g.id === activeGroupId);
  const hintKey = pickerHintKey(activeGroup?.rawLabel);
  const visibleSub = subModes.filter((m) => !m.disabled);
  const currentSub = visibleSub.length > 1 ? visibleSub.find((m) => m.mode === currentMode) : null;
  useViewModeSummary(
    'mode', 20,
    modeSummaryText(activeGroup?.label, currentSub?.label),
    activeGroup?.label || '',
  );

  const body = (
    <>
      <PickerLabel>{title}</PickerLabel>
      <ChipGroup label={title} grid>
        {groups.map((group) => (
          <Chip
            key={group.id}
            active={group.id === activeGroupId}
            onClick={() => onTopClick(group)}
          >
            {group.label}
          </Chip>
        ))}
      </ChipGroup>
      <PickerHint>{hintKey ? t(hintKey) : null}</PickerHint>
      {visibleSub.length > 1 && (
        <div className="fe-pick-sub">
          <PickerLabel>{t('w3.picker.detail')}</PickerLabel>
          <OverflowChipGroup
            label={subGroupLabel}
            dense
            items={visibleSub}
            isActive={(item) => currentMode === item.mode}
            renderChip={(item) => (
              <Chip
                key={item.mode}
                active={currentMode === item.mode}
                onClick={() => onSubClick(item)}
              >
                {item.label}
              </Chip>
            )}
          />
        </div>
      )}
    </>
  );

  return <PickerCard compact={compact} className={cn('fe-pick-card--mode', className)}>{body}</PickerCard>;
}
