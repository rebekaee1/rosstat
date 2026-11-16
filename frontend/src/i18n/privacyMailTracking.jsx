/**
 * Черновик раздела политики конфиденциальности об учёте открытий писем и переходов из них (ADR-0034, 16.11.2026).
 *
 * Текст подготовлен для юриста владельца; юрист его НЕ смотрел. На сайте не показывается, пока сборка не получит
 * VITE_PRIVACY_MAIL_TRACKING=true (после проверки юристом и решения владельца). Тот же шаг на сервере —
 * RUSTATS_MAIL_TRACKING_ENABLED: пиксель открытия и метка получателя на ссылках включаются только после
 * публикации этого текста.
 */

export const MAIL_TRACKING_POLICY_PUBLISHED = import.meta.env.VITE_PRIVACY_MAIL_TRACKING === 'true';

const h3 = 'text-lg font-semibold text-text-primary mt-6 mb-2';
const p = 'text-text-secondary leading-relaxed mb-4';
const li = 'text-text-secondary leading-relaxed';

export function MailTrackingPolicyRu() {
  return (
    <section data-testid="privacy-mail-tracking">
      <h3 className={h3}>Как мы узнаём, полезны ли наши письма</h3>
      <p className={p}>
        Чтобы понимать, читают ли информационную рассылку и какие её разделы полезны, Оператор учитывает
        по каждому письму:
      </p>
      <ul className="list-disc pl-5 space-y-2 mb-4">
        <li className={li}>
          принято ли письмо почтовым сервисом и не вернулось ли оно с отказом;
        </li>
        <li className={li}>
          было ли письмо открыто: в письме есть невидимая картинка, запрос которой сообщает об открытии.
          Сохраняется время и тип почтовой программы одним словом; IP-адрес и полная строка сведений о
          программе не сохраняются. Если в вашей почте выключен показ картинок, открытие не учитывается;
        </li>
        <li className={li}>
          переход по ссылке из письма на Сайт: в ссылке есть метки выпуска, раздела письма и обезличенная
          метка получателя, по которой нельзя установить адрес электронной почты. После перехода учитываются
          ваши действия на Сайте в этом посещении и то, возвращались ли вы на Сайт в следующие 30 дней;
        </li>
        <li className={li}>
          отписку от рассылки и отказ от персональной подборки.
        </li>
      </ul>
      <p className={p}>
        Эти сведения используются только для оценки и улучшения писем Оператора, не передаются третьим
        лицам и не используются для рекламы. Сотрудники Оператора видят их в виде сумм по выпуску.
        Сведения о ваших письмах входят в выгрузку «Мои данные» в личном кабинете и удаляются вместе с
        учётной записью.
      </p>
      <p className={p}>
        Отказаться от такого учёта можно, не отписываясь от рассылки: по ссылке «Письма без персональной
        подборки» в конце любого письма. После отказа в письмах не будет невидимой картинки и метки
        получателя.
      </p>
    </section>
  );
}

export function MailTrackingPolicyEn() {
  return (
    <section data-testid="privacy-mail-tracking">
      <h3 className={h3}>How we learn whether our emails are useful</h3>
      <p className={p}>
        To understand whether the newsletter is read and which parts of it are useful, the Operator
        records for each email:
      </p>
      <ul className="list-disc pl-5 space-y-2 mb-4">
        <li className={li}>whether the mail service accepted the email or returned it;</li>
        <li className={li}>
          whether the email was opened: it contains an invisible image whose request signals an open. We
          store the time and a one-word type of mail program; the IP address and the full program string
          are not stored. If your mail program does not load images, the open is not recorded;
        </li>
        <li className={li}>
          a click from the email to the Site: the link carries labels of the issue and the section of the
          email and an anonymised recipient label that cannot be traced back to an email address. After
          the click we count your actions on the Site during that visit and whether you came back within
          the next 30 days;
        </li>
        <li className={li}>unsubscribing and turning off the personal selection.</li>
      </ul>
      <p className={p}>
        This information is used only to assess and improve the Operator&apos;s emails; it is not shared
        with third parties and is not used for advertising. The Operator&apos;s staff see it as totals per
        issue. Information about your emails is included in the “My data” export in your account and is
        deleted together with the account.
      </p>
      <p className={p}>
        You can opt out without unsubscribing: use the “Emails without the personal selection” link at
        the end of any email. After that, emails will carry neither the invisible image nor the recipient
        label.
      </p>
    </section>
  );
}
