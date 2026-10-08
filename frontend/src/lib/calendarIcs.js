/**
 * Одно событие календаря как файл .ics («добавить в календарь телефона»), собирается в браузере без регистрации.
 * Время в календаре публикаций — московское (UTC+3 без перехода на летнее время), поэтому в файл оно
 * записывается в UTC. Событие без времени становится событием на весь день.
 */

const PAD = (n) => String(n).padStart(2, '0');

function escapeText(value) {
  return String(value ?? '')
    .replace(/\\/g, '\\\\')
    .replace(/\r?\n/g, '\\n')
    .replace(/,/g, '\\,')
    .replace(/;/g, '\\;');
}

/** Строки длиннее 75 знаков переносятся по правилам RFC 5545 (продолжение начинается с пробела). */
function fold(line) {
  if (line.length <= 73) return line;
  const parts = [];
  let rest = line;
  parts.push(rest.slice(0, 73));
  rest = rest.slice(73);
  while (rest.length > 0) {
    parts.push(` ${rest.slice(0, 72)}`);
    rest = rest.slice(72);
  }
  return parts.join('\r\n');
}

function stamp(d) {
  return `${d.getUTCFullYear()}${PAD(d.getUTCMonth() + 1)}${PAD(d.getUTCDate())}T${PAD(d.getUTCHours())}${PAD(d.getUTCMinutes())}00Z`;
}

/**
 * @param {{scheduled_date: string, scheduled_time?: string|null, id?: string|number, source_event_uid?: string}} event
 * @param {{title: string, description?: string, url?: string, now?: Date}} opts
 * @returns {string|null} текст файла или null, если у события нет даты
 */
export function buildEventIcs(event, { title, description = '', url = '', now = new Date() } = {}) {
  const date = String(event?.scheduled_date || '');
  const m = date.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!m) return null;
  const [y, mo, d] = [Number(m[1]), Number(m[2]), Number(m[3])];
  const timeMatch = String(event.scheduled_time || '').match(/^(\d{1,2}):(\d{2})/);
  const uid = `${event.source_event_uid || event.id || `${date}-${title}`}@forecasteconomy`.replace(/\s+/g, '-');

  const lines = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//Forecast Economy//Calendar//RU',
    'CALSCALE:GREGORIAN',
    'METHOD:PUBLISH',
    'BEGIN:VEVENT',
    `UID:${uid}`,
    `DTSTAMP:${stamp(now)}`,
  ];
  if (timeMatch) {
    // Московское время → UTC.
    const start = new Date(Date.UTC(y, mo - 1, d, Number(timeMatch[1]) - 3, Number(timeMatch[2])));
    lines.push(`DTSTART:${stamp(start)}`, 'DURATION:PT30M');
  } else {
    const next = new Date(Date.UTC(y, mo - 1, d + 1));
    lines.push(
      `DTSTART;VALUE=DATE:${m[1]}${m[2]}${m[3]}`,
      `DTEND;VALUE=DATE:${next.getUTCFullYear()}${PAD(next.getUTCMonth() + 1)}${PAD(next.getUTCDate())}`,
    );
  }
  lines.push(`SUMMARY:${escapeText(title)}`);
  if (description) lines.push(`DESCRIPTION:${escapeText(description)}`);
  if (url) lines.push(`URL:${url}`);
  lines.push(
    'BEGIN:VALARM',
    'ACTION:DISPLAY',
    `DESCRIPTION:${escapeText(title)}`,
    'TRIGGER:-PT30M',
    'END:VALARM',
    'END:VEVENT',
    'END:VCALENDAR',
  );
  return `${lines.map(fold).join('\r\n')}\r\n`;
}

/** Предлагает файл к сохранению; на телефоне система сама открывает «Добавить в календарь». */
export function downloadIcs(text, fileName = 'event.ics') {
  if (!text || typeof document === 'undefined' || typeof Blob === 'undefined') return false;
  try {
    const blob = new Blob([text], { type: 'text/calendar;charset=utf-8' });
    const href = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = href;
    a.download = fileName;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(href), 4000);
    return true;
  } catch {
    return false;
  }
}
