import useDocumentMeta from '../lib/useMeta';

export default function About() {
  useDocumentMeta({
    title: 'О проекте Forecast Economy — открытые данные и прогноз',
    description:
      'Forecast Economy: бесплатная аналитика инфляции и ИПЦ России на основе официальных данных Росстата и ЦБ РФ. OLS-прогноз, исторические ряды с 1991 года.',
    path: '/about',
  });

  return (
    <div className="max-w-3xl mx-auto px-4 md:px-8 pt-24 md:pt-28 pb-20 md:pb-24">
      <article className="prose prose-sm max-w-none">
        <p className="text-[10px] uppercase tracking-[0.3em] text-champagne font-semibold mb-4">
          О проекте
        </p>
        <h1 className="font-display text-3xl md:text-4xl font-bold text-text-primary mb-6 leading-tight">
          Forecast Economy — макроэкономический терминал для России
        </h1>
        <p className="text-text-secondary leading-relaxed mb-6">
          <strong className="text-text-primary">Forecast Economy</strong> — веб-платформа для работы с официальной
          статистикой по инфляции и смежным индикаторам. Мы агрегируем данные из открытых источников
          (прежде всего <a href="https://rosstat.gov.ru" className="text-champagne hover:underline" target="_blank" rel="noopener noreferrer">Росстат</a>
          {' '}и <a href="https://cbr.ru" className="text-champagne hover:underline" target="_blank" rel="noopener noreferrer">Банк России</a>),
          показываем исторические ряды и строим{' '}
          <strong className="text-text-primary">OLS-прогноз</strong> на горизонт до 12 месяцев вперёд.
        </p>

        <h2 className="text-xl font-semibold text-text-primary mt-10 mb-3">Для кого этот сервис</h2>
        <ul className="list-disc pl-5 text-text-secondary space-y-2 mb-6">
          <li>аналитикам и исследователям, которым нужны ряды и прогноз в одном месте;</li>
          <li>журналистам и редакторам — быстрые графики и контекст по ИПЦ;</li>
          <li>всем, кто хочет видеть <strong className="text-text-primary">официальные данные</strong>, а не только заголовки новостей.</li>
        </ul>

        <h2 className="text-xl font-semibold text-text-primary mt-10 mb-3">Чем мы отличаемся</h2>
        <ul className="list-disc pl-5 text-text-secondary space-y-2 mb-6">
          <li>
            <strong className="text-text-primary">Первичные данные.</strong> Источники указаны на каждой
            странице; вы можете свериться с оригиналом на сайте Росстата или ЦБ.
          </li>
          <li>
            <strong className="text-text-primary">Прогноз с методологией.</strong> Модель OLS и окна
            обучения описаны в интерфейсе; прогноз — оценка по истории ряда, а не «мнение редакции».
          </li>
          <li>
            <strong className="text-text-primary">Бесплатный доступ.</strong> Просмотр данных и прогнозов
            не требует регистрации.
          </li>
        </ul>

        <h2 className="text-xl font-semibold text-text-primary mt-10 mb-3">Доверие и ограничения</h2>
        <p className="text-text-secondary leading-relaxed mb-4">
          Материалы носят <strong className="text-text-primary">исключительно информационный характер</strong> и не являются
          индивидуальной инвестиционной рекомендацией, финансовым или юридическим советом. Прогнозы
          отражают статистическую экстраполяцию прошлых данных и могут расходиться с фактической
          динамикой из-за шоков, смены политики и пересмотра рядов.
        </p>
        <p className="text-text-secondary leading-relaxed">
          По вопросам сотрудничества и замечаний по данным:{' '}
          <a href="mailto:contact@forecasteconomy.com" className="text-champagne hover:underline">
            contact@forecasteconomy.com
          </a>
          .
        </p>
      </article>
    </div>
  );
}
