import useDocumentMeta from '../lib/useMeta';

export default function About() {
  useDocumentMeta({
    title: 'О проекте — экономические данные России бесплатно',
    description:
      'Forecast Economy — бесплатная платформа макроэкономической аналитики России. 80+ индикаторов в 9 категориях: ИПЦ, ВВП, курсы валют, ставки, рынок труда, торговля, население, бизнес, наука. Данные Росстата, ЦБ РФ и Минфина.',
    path: '/about',
  });

  return (
    <div className="max-w-3xl mx-auto px-4 md:px-8 pt-24 md:pt-28 pb-20 md:pb-24">
      <article className="prose prose-sm max-w-none">
        <p className="text-[10px] uppercase tracking-[0.3em] text-champagne font-semibold mb-4">
          О проекте
        </p>
        <h1 className="font-display text-3xl md:text-4xl font-bold text-text-primary mb-6 leading-tight">
          Forecast Economy — бесплатная аналитика экономики России
        </h1>
        <p className="text-text-secondary leading-relaxed mb-6">
          <strong className="text-text-primary">Forecast Economy</strong> — веб-платформа для работы
          с макроэкономическими данными России. Мы автоматически собираем <strong className="text-text-primary">80+ индикаторов</strong> из
          трёх официальных источников —{' '}
          <a href="https://rosstat.gov.ru" className="text-champagne hover:underline" target="_blank" rel="noopener noreferrer">Росстат</a>,{' '}
          <a href="https://cbr.ru" className="text-champagne hover:underline" target="_blank" rel="noopener noreferrer">Банк России</a> и{' '}
          <a href="https://minfin.gov.ru" className="text-champagne hover:underline" target="_blank" rel="noopener noreferrer">Минфин</a> —
          и представляем их в удобном виде: графики, таблицы, сравнения и прогнозы.
        </p>

        <h2 className="text-xl font-semibold text-text-primary mt-10 mb-3">Что есть на платформе</h2>
        <ul className="list-disc pl-5 text-text-secondary space-y-2 mb-6">
          <li><strong className="text-text-primary">9 категорий</strong> — цены и инфляция, процентные ставки, финансы и валюты, ВВП, рынок труда, население, внешняя торговля, бизнес, наука и образование.</li>
          <li><strong className="text-text-primary">Исторические ряды</strong> — от ежедневных курсов валют до годовых демографических данных с 1990 года.</li>
          <li><strong className="text-text-primary">Калькулятор инфляции</strong> — обесценивание денег за любой период на основе ИПЦ.</li>
          <li><strong className="text-text-primary">Сравнение индикаторов</strong> — два показателя на одном графике с двумя осями.</li>
          <li><strong className="text-text-primary">Экспорт</strong> — скачивание данных в Excel и CSV.</li>
          <li><strong className="text-text-primary">Встраиваемые виджеты</strong> — графики и карточки для вашего сайта.</li>
        </ul>

        <h2 className="text-xl font-semibold text-text-primary mt-10 mb-3">Для кого</h2>
        <ul className="list-disc pl-5 text-text-secondary space-y-2 mb-6">
          <li>Экономистам и аналитикам — вместо ручного скачивания Excel с Росстата и ЦБ.</li>
          <li>Журналистам — быстрые графики с источниками для публикаций.</li>
          <li>Студентам и исследователям — бесплатные временные ряды для курсовых и дипломных работ.</li>
          <li>Бизнесу — мониторинг ключевой ставки, инфляции, курсов для планирования.</li>
          <li>Всем, кто предпочитает <strong className="text-text-primary">первичные данные</strong> вместо интерпретаций СМИ.</li>
        </ul>

        <h2 className="text-xl font-semibold text-text-primary mt-10 mb-3">Источники данных</h2>
        <p className="text-text-secondary leading-relaxed mb-4">
          Данные загружаются автоматически и обновляются ежедневно в 06:00 МСК. Для каждого индикатора
          указан конкретный источник — вы всегда можете свериться с оригиналом. Мы используем только открытые данные
          государственной статистики, без коммерческих и биржевых источников.
        </p>

        <h2 className="text-xl font-semibold text-text-primary mt-10 mb-3">Прогнозы</h2>
        <p className="text-text-secondary leading-relaxed mb-4">
          Для индикаторов с достаточной историей строятся статистические прогнозы. Модели и параметры
          описаны на странице каждого индикатора. Прогноз — математическая экстраполяция, не экспертное
          мнение. Доверительные интервалы показывают степень неопределённости.
        </p>

        <h2 className="text-xl font-semibold text-text-primary mt-10 mb-3">Ограничения и дисклеймер</h2>
        <p className="text-text-secondary leading-relaxed mb-4">
          Материалы носят <strong className="text-text-primary">исключительно информационный характер</strong> и не являются
          инвестиционной рекомендацией. Прогнозы могут расходиться с реальностью из-за экономических
          шоков, пересмотра данных и изменения методологии источников.
        </p>
        <p className="text-text-secondary leading-relaxed">
          Вопросы, предложения и замечания по данным:{' '}
          <a href="mailto:contact@forecasteconomy.com" className="text-champagne hover:underline">
            contact@forecasteconomy.com
          </a>
        </p>
      </article>
    </div>
  );
}
