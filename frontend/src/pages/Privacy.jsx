import useDocumentMeta from '../lib/useMeta';

export default function Privacy() {
  useDocumentMeta({
    title: 'Политика конфиденциальности — RuStats',
    description:
      'Как RuStats обрабатывает данные посетителей: Яндекс.Метрика, cookies, контакты. Проект forecasteconomy.com.',
    path: '/privacy',
  });

  return (
    <div className="max-w-3xl mx-auto px-4 md:px-8 pt-32 pb-20">
      <article className="prose prose-sm max-w-none">
        <p className="text-[10px] uppercase tracking-[0.3em] text-champagne font-semibold mb-4">
          Правовая информация
        </p>
        <h1 className="text-3xl md:text-4xl font-bold text-text-primary mb-6">
          Политика конфиденциальности
        </h1>
        <p className="text-sm text-text-tertiary mb-8">Последнее обновление: 20 марта 2026 г.</p>

        <h2 className="text-xl font-semibold text-text-primary mt-8 mb-3">1. Общие положения</h2>
        <p className="text-text-secondary leading-relaxed mb-4">
          Сайт <strong className="text-text-primary">forecasteconomy.com</strong> (проект RuStats) уважает
          конфиденциальность посетителей. Настоящая политика описывает, какие данные могут собираться
          при использовании сайта и с какой целью.
        </p>

        <h2 className="text-xl font-semibold text-text-primary mt-10 mb-3">2. Сбор и использование данных</h2>
        <p className="text-text-secondary leading-relaxed mb-4">
          Для анализа посещаемости и улучшения работы сайта используется{' '}
          <strong className="text-text-primary">Яндекс.Метрика</strong> (счётчик веб-аналитики). Метрика
          может обрабатывать обезличенные сведения о визитах (просмотры страниц, источники переходов,
          приблизительный регион по IP в обобщённом виде в соответствии с настройками сервиса).
          Подробнее — в документации Яндекса о Метрике и обработке данных.
        </p>
        <p className="text-text-secondary leading-relaxed mb-4">
          Технические cookie и локальное хранилище браузера могут использоваться для сохранения
          настроек интерфейса и работы счётчика. Вы можете ограничить cookie в настройках браузера.
        </p>

        <h2 className="text-xl font-semibold text-text-primary mt-10 mb-3">3. Обращения пользователей</h2>
        <p className="text-text-secondary leading-relaxed mb-4">
          Если вы пишете нам на электронную почту, мы обрабатываем указанные вами адрес и текст
          обращения исключительно для ответа и ведения переписки по существу вопроса.
        </p>

        <h2 className="text-xl font-semibold text-text-primary mt-10 mb-3">4. Контакты</h2>
        <p className="text-text-secondary leading-relaxed">
          Вопросы по политике и данным:{' '}
          <a href="mailto:contact@forecasteconomy.com" className="text-champagne hover:underline">
            contact@forecasteconomy.com
          </a>
          .
        </p>
      </article>
    </div>
  );
}
