/**
 * Черновик раздела политики конфиденциальности о персональной подборке в рассылке (ADR-0033, 15.11.2026).
 *
 * Текст подготовлен для юриста владельца и на сайте не показывается, пока сборка не получит
 * VITE_PRIVACY_PERSONAL_NEWSLETTER=true (после проверки юристом и решения владельца). Тот же флаг
 * политики на сервере — RUSTATS_NEWSLETTER_PERSONAL_BEHAVIOR_SIGNALS: письма людям с блоками по
 * поведению на сайте включаются только после публикации этого текста.
 */

export const PERSONAL_NEWSLETTER_POLICY_PUBLISHED =
  import.meta.env.VITE_PRIVACY_PERSONAL_NEWSLETTER === 'true';

const h3 = 'text-lg font-semibold text-text-primary mt-6 mb-2';
const p = 'text-text-secondary leading-relaxed mb-4';
const li = 'text-text-secondary leading-relaxed';

export function PersonalNewsletterPolicyRu() {
  return (
    <section data-testid="privacy-personal-newsletter">
      <h3 className={h3}>Персональная подборка в информационной рассылке</h3>
      <p className={p}>
        Если вы подписаны на информационную рассылку, в письмо может входить раздел «Для вас» —
        подборка официальных данных по темам, которые вас интересуют. Чтобы её составить, Оператор
        автоматически анализирует ваши действия на Сайте, связанные с вашей учётной записью:
      </p>
      <ul className="list-disc pl-5 space-y-2 mb-4">
        <li className={li}>
          показатели, регионы и страны, страницы которых вы открывали, а также сравнения, прогнозы
          и скачанные файлы;
        </li>
        <li className={li}>
          показатели, которые вы выбирали в поиске Сайта. Текст поисковых запросов в профиль не
          сохраняется: запрос сопоставляется с показателем, который по нему выбирают посетители чаще всего;
        </li>
        <li className={li}>
          избранное, слежения за выходом новых значений, сохранённые сравнения, настройки личного
          кабинета (темы рассылки, главная страна, валюта);
        </li>
        <li className={li}>
          язык версии Сайта, страну регистрации, часовой пояс браузера (чтобы письмо не приходило
          ночью) и переходы по ссылкам из прошлых писем;
        </li>
        <li className={li}>
          действия на Сайте до регистрации — с того же браузера, с которого вы затем вошли в
          учётную запись.
        </li>
      </ul>
      <p className={p}>
        Из этих сведений составляется профиль интересов: перечень показателей и тем с весами.
        Профиль используется только для подбора содержания писем Оператора; он не передаётся третьим
        лицам, не используется для рекламы и не влечёт для вас юридических последствий. Числа в
        подборке берутся из официальных источников, указанных в письме. Регион, определённый по
        IP-адресу, для подборки не используется.
      </p>
      <p className={p}>
        Для оценки полезности рассылки Оператор учитывает переходы по ссылкам из писем: в ссылках
        есть метки выпуска и блока письма и, при необходимости, обезличенная метка получателя, по
        которой нельзя установить адрес электронной почты.
      </p>
      <p className={p}>
        Основание обработки — ваше согласие на информационную рассылку. Отключить персональную
        подборку, не отказываясь от рассылки, можно по ссылке «Письма без персональной подборки»
        в любом письме; после этого письмо приходит в общем для всех виде. Если вы отказались от
        аналитических cookie, действия на Сайте в подборке не учитываются. Профиль интересов и
        сведения о подборках хранятся, пока существует учётная запись (сведения о составе прошлых
        писем — не дольше 180 дней), удаляются вместе с ней и входят в копию данных, которую
        Оператор предоставляет по вашему запросу.
      </p>
    </section>
  );
}

export function PersonalNewsletterPolicyEn() {
  return (
    <section data-testid="privacy-personal-newsletter">
      <h3 className={h3}>Personal picks in the newsletter</h3>
      <p className={p}>
        If you subscribe to the newsletter, an email may include a “For you” section — official data
        on topics that interest you. To pick it, the Operator automatically analyses your activity on
        the Site linked to your account:
      </p>
      <ul className="list-disc pl-5 space-y-2 mb-4">
        <li className={li}>
          indicators, regions and countries whose pages you opened, as well as comparisons, forecasts
          and downloaded files;
        </li>
        <li className={li}>
          indicators you selected in the Site search. The text of your searches is not stored in the
          profile: a search is matched to the indicator visitors most often pick for it;
        </li>
        <li className={li}>
          favourites, alerts for new values, saved comparisons and account settings (newsletter
          topics, home country, currency);
        </li>
        <li className={li}>
          the language version of the Site, the country at sign-up, your browser time zone (so that
          emails do not arrive at night) and clicks on links in previous emails;
        </li>
        <li className={li}>
          your activity on the Site before sign-up — from the same browser you later used to sign in.
        </li>
      </ul>
      <p className={p}>
        This information forms an interest profile: a list of indicators and topics with weights. The
        profile is used only to choose the content of the Operator’s emails; it is not shared with
        third parties, is not used for advertising and has no legal effect on you. Figures in the
        section come from the official sources named in the email. A region inferred from your IP
        address is not used.
      </p>
      <p className={p}>
        To measure how useful the newsletter is, the Operator counts clicks on links in emails: the
        links carry the issue and block of the email and, where needed, a pseudonymous recipient tag
        that does not reveal your email address.
      </p>
      <p className={p}>
        The legal basis is your consent to the newsletter. You can switch off personal picks without
        unsubscribing via the “Emails without personal picks” link in any email; after that you
        receive the same email as everyone else. If you declined analytics cookies, your activity on
        the Site is not used. The interest profile and records of past picks are kept while your
        account exists (records of past emails for no longer than 180 days), are deleted with the
        account and are included in the copy of your data the Operator provides on request.
      </p>
    </section>
  );
}
