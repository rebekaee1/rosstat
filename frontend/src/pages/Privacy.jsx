import { Link } from 'react-router-dom';
import { Settings2 } from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import { track, events } from '../lib/track';
import { openConsentSettings } from '../lib/consent';
import { cn } from '../lib/format';
import { FOCUS_RING } from '../lib/uiTokens';

/**
 * Политика конфиденциальности и обработки персональных данных.
 *
 * Структура соответствует ч. 2 ст. 18.1 152-ФЗ: оператор, состав данных,
 * цели, правовые основания, cookie-категории (согласие через CookieConsent),
 * третьи лица, сроки, права субъекта. Дата редакции синхронизирована
 * с CONSENT_VERSION в lib/consent.js — при смене редакции поднять обе.
 */

const h2 = 'text-xl font-semibold text-text-primary mt-10 mb-3';
const p = 'text-text-secondary leading-relaxed mb-4';
const li = 'text-text-secondary leading-relaxed';

function CookieRow({ name, purpose, consent }) {
  return (
    <div className="rounded-xl border border-border-subtle px-4 py-3 mb-2">
      <p className="text-sm font-semibold text-text-primary">{name}</p>
      <p className="text-sm text-text-secondary leading-relaxed mt-0.5">{purpose}</p>
      <p className="text-xs text-text-tertiary mt-1">{consent}</p>
    </div>
  );
}

export default function Privacy() {
  useDocumentMeta({
    title: 'Политика конфиденциальности',
    description:
      'Политика обработки персональных данных сайта forecasteconomy.com: оператор, состав данных, cookie, права пользователей.',
    path: '/privacy',
  });

  return (
    <div className="max-w-3xl mx-auto px-4 md:px-8 pt-24 md:pt-28 pb-20 md:pb-24">
      <article className="prose prose-sm max-w-none">
        <p className="text-[10px] uppercase tracking-[0.3em] text-champagne font-semibold mb-4">
          Правовая информация
        </p>
        <h1 className="font-display text-3xl md:text-4xl font-bold text-text-primary mb-6 leading-tight">
          Политика конфиденциальности и обработки персональных данных
        </h1>
        <p className="text-sm text-text-tertiary mb-8">Редакция от 12 июня 2026 г.</p>

        <h2 className={h2}>1. Общие положения</h2>
        <p className={p}>
          Настоящая политика определяет порядок обработки персональных данных посетителей сайта{' '}
          <strong className="text-text-primary">forecasteconomy.com</strong> (далее — Сайт) и меры
          по обеспечению их безопасности в соответствии с Федеральным законом от 27.07.2006
          № 152-ФЗ «О персональных данных».
        </p>
        <p className={p}>
          Оператор персональных данных — Общество с ограниченной ответственностью «ИИМПАКТ ПЛЮС»
          (ООО «ИИМПАКТ ПЛЮС»), ИНН 9705243471, ОГРН 1257700255196, адрес: 123557, г. Москва,
          ул. Пресненский Вал, д. 21, помещ. 172 (далее — Оператор). Оператор включён в реестр
          операторов персональных данных Роскомнадзора, регистрационный номер 77-26-538159.
        </p>
        <p className={p}>
          Используя Сайт, вы соглашаетесь с условиями настоящей политики. Порядок использования
          материалов Сайта описан в{' '}
          <Link to="/terms" className="text-champagne hover:underline">
            пользовательском соглашении
          </Link>
          .
        </p>

        <h2 className={h2}>2. Какие данные обрабатываются</h2>
        <p className={p}>
          Сайт не требует регистрации, не содержит форм сбора персональных данных и доступен без
          указания каких-либо сведений о себе. Обрабатываются две группы данных:
        </p>
        <ul className="list-disc pl-5 space-y-2 mb-4">
          <li className={li}>
            <strong className="text-text-primary">Технические данные посетителей</strong> — файлы
            cookie, IP-адрес, сведения о браузере и устройстве, просмотренные страницы, источник
            перехода. Аналитические и рекламные данные собираются только после вашего согласия
            (раздел 4).
          </li>
          <li className={li}>
            <strong className="text-text-primary">Данные обращений</strong> — адрес электронной
            почты, имя (если вы его указали) и содержание сообщения при обращении к Оператору
            по электронной почте.
          </li>
        </ul>
        <p className={p}>
          Специальные категории персональных данных и биометрические данные не обрабатываются.
        </p>

        <h2 className={h2}>3. Цели и правовые основания обработки</h2>
        <ul className="list-disc pl-5 space-y-2 mb-4">
          <li className={li}>
            обеспечение работы Сайта и сохранение пользовательских настроек — в силу
            необходимости для предоставления функций Сайта;
          </li>
          <li className={li}>
            анализ посещаемости и улучшение Сайта (веб-аналитика) — на основании вашего согласия,
            выраженного через баннер настроек cookie;
          </li>
          <li className={li}>
            показ рекламных блоков рекламной сети — на основании вашего согласия, выраженного
            через баннер настроек cookie;
          </li>
          <li className={li}>
            ответы на обращения и переписка по существу вопроса — на основании вашего обращения.
          </li>
        </ul>

        <h2 className={h2}>4. Файлы cookie и согласие</h2>
        <p className={p}>
          При первом посещении Сайт показывает баннер настроек cookie. До получения вашего
          согласия аналитические и рекламные инструменты не запускаются и соответствующие
          cookie не устанавливаются. Используются три категории:
        </p>
        <CookieRow
          name="Необходимые"
          purpose="Сохранение настроек интерфейса и вашего выбора в отношении cookie. Обеспечивают работу Сайта, третьим лицам не передаются."
          consent="Согласие не требуется (ч. 2 ст. 6 152-ФЗ — необходимы для предоставления сервиса)."
        />
        <CookieRow
          name="Аналитические"
          purpose="Счётчик Яндекс Метрика: статистика посещений, источники переходов, поведение на страницах. Используются для улучшения Сайта."
          consent="Устанавливаются только после вашего согласия."
        />
        <CookieRow
          name="Рекламные"
          purpose="Рекламная сеть Яндекса: показ рекламных блоков и учёт их показов."
          consent="Устанавливаются только после вашего согласия."
        />
        <p className={p}>
          Изменить или отозвать согласие можно в любой момент — нажмите кнопку ниже или ссылку
          «Настройки cookie» в подвале любой страницы. Отзыв согласия прекращает установку
          новых cookie соответствующей категории; уже установленные cookie можно удалить
          в настройках браузера.
        </p>
        <button
          type="button"
          onClick={openConsentSettings}
          className={cn(
            FOCUS_RING,
            'inline-flex items-center gap-2 rounded-xl bg-champagne/10 text-champagne px-5 py-2.5 text-sm font-medium hover:bg-champagne/20 transition-colors mb-4'
          )}
        >
          <Settings2 className="w-4 h-4" aria-hidden="true" />
          Настройки cookie
        </button>

        <h2 className={h2}>5. Передача данных третьим лицам</h2>
        <p className={p}>
          Оператор не продаёт и не передаёт персональные данные третьим лицам, за исключением
          случаев, описанных ниже:
        </p>
        <ul className="list-disc pl-5 space-y-2 mb-4">
          <li className={li}>
            <strong className="text-text-primary">Яндекс</strong> (ООО «Яндекс», Россия) —
            обработка обезличенной статистики посещений сервисом Яндекс Метрика и показ рекламы
            Рекламной сетью Яндекса; в обоих случаях только после вашего согласия. Условия
            обработки данных описаны в документах Яндекса.
          </li>
          <li className={li}>
            <strong className="text-text-primary">Google Fonts</strong> — при загрузке страниц
            браузер запрашивает файлы шрифтов с серверов Google; в рамках такого запроса Google
            получает технические данные (IP-адрес запроса). Содержание ваших действий на Сайте
            при этом не передаётся.
          </li>
          <li className={li}>
            по требованию уполномоченных государственных органов — в случаях, установленных
            законодательством Российской Федерации.
          </li>
        </ul>

        <h2 className={h2}>6. Хранение, защита и сроки обработки</h2>
        <p className={p}>
          Данные обрабатываются автоматизированно и хранятся на серверах, расположенных на
          территории Российской Федерации. Соединение с Сайтом защищено протоколом HTTPS,
          доступ к данным ограничен. Сроки обработки: cookie — в пределах срока их действия
          или до отзыва согласия; данные обращений — в течение времени, необходимого для
          ответа и ведения переписки; статистика посещений — в обезличенном виде в течение
          срока работы Сайта.
        </p>

        <h2 className={h2}>7. Ваши права</h2>
        <p className={p}>
          В соответствии со статьями 14 и 20 закона № 152-ФЗ вы вправе запросить сведения об
          обработке ваших персональных данных, потребовать их уточнения, блокирования или
          уничтожения, а также отозвать согласие на обработку. Для этого направьте запрос на
          адрес электронной почты из раздела 9 — ответ будет дан в течение 10 рабочих дней.
          Вы также вправе обжаловать действия Оператора в Роскомнадзоре или в судебном порядке.
        </p>

        <h2 className={h2}>8. Изменения политики</h2>
        <p className={p}>
          Оператор вправе обновлять настоящую политику. Новая редакция публикуется на этой
          странице с указанием даты. При существенных изменениях Сайт повторно запросит ваше
          согласие на использование cookie.
        </p>

        <h2 className={h2}>9. Контакты</h2>
        <p className="text-text-secondary leading-relaxed mb-2">
          Вопросы по настоящей политике и запросы, связанные с персональными данными:
        </p>
        <ul className="list-disc pl-5 space-y-1 mb-4">
          <li className={li}>
            <a
              href="mailto:contact@forecasteconomy.com"
              className="text-champagne hover:underline"
              onClick={() => track(events.CONTACT_EMAIL)}
            >
              contact@forecasteconomy.com
            </a>
          </li>
          <li className={li}>
            <a
              href="mailto:rebeka.ee@aimpact.ru"
              className="text-champagne hover:underline"
              onClick={() => track(events.CONTACT_EMAIL)}
            >
              rebeka.ee@aimpact.ru
            </a>
          </li>
        </ul>
        <p className="text-text-secondary leading-relaxed">
          Почтовый адрес Оператора: 123557, г. Москва, ул. Пресненский Вал, д. 21, помещ. 172,
          ООО «ИИМПАКТ ПЛЮС».
        </p>
      </article>
    </div>
  );
}
