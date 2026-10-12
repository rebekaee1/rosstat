// Официальный прогноз (МВФ): подпись выпуска. Дата приходит как ISO (YYYY-MM-DD)
// или отсутствует; без даты возвращаем нейтральное «последний выпуск».
export function formatOfficialVintage(vintage, locale) {
  const en = locale === 'en';
  if (!vintage || typeof vintage !== 'string') return en ? 'the latest release' : 'последний выпуск';
  const parsed = new Date(`${vintage.slice(0, 10)}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return en ? 'the latest release' : 'последний выпуск';
  return parsed.toLocaleDateString(en ? 'en-GB' : 'ru-RU', {
    day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC',
  });
}
