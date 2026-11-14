/** Статус события календаря (вынесено из CalendarEventCard, 15.11.2026: файл компонента экспортирует только компоненты). */

export function localTodayIso() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

/** Через сколько дней после даты выпуска перестаём «ждать данные» и пишем «дата прошла». */
const AWAIT_DAYS = 7;

/**
 * Статус события одной строкой (круг 14.11.2026). Раньше прошедшие события без цифры писались
 * «Ориентировочно» — и заседание ЦБ, прошедшее три недели назад, выглядело неподтверждённым.
 * Теперь: вышло (цифра есть на сайте) → ждём данные (неделя после даты) → дата прошла; будущее —
 * дата подтверждена, по графику (каждый рабочий день) или перенесено с прежней даты.
 */
export function eventStatus(event, today = localTodayIso()) {
  const date = event?.scheduled_date || '';
  if (event?.status === 'released' || (event?.actual_value != null && event.actual_value !== '')) {
    return { kind: 'released' };
  }
  if (date && date < today) {
    const days = Math.round((Date.parse(today) - Date.parse(date)) / 86400000);
    // Предварительная оценка ВВП (ключ «:flash») не добавляет точку в ряд — ждать на сайте нечего.
    const confirmable = event?.indicator_code && !String(event?.event_key || '').endsWith(':flash');
    return { kind: days <= AWAIT_DAYS && confirmable ? 'awaiting' : 'passed' };
  }
  if (event?.rescheduled_from) return { kind: 'moved', from: event.rescheduled_from };
  // Срок «не позднее» (бюджет Минфина): источник обещает не день выхода, а крайний срок.
  if (event?.deadline || event?.date_confidence === 'official_deadline') return { kind: 'deadline', date };
  if (event?.date_confidence === 'official_rule') return { kind: 'byRule' };
  return { kind: 'confirmed' };
}
