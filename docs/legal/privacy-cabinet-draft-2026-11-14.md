# Черновик для юриста: политика конфиденциальности — личный кабинет (14.11.2026)

**Статус:** черновик агента, текст на сайте **не менялся**. Решение и правку `frontend/src/pages/Privacy.jsx`
(и английского варианта там же) делает владелец после проверки юристом. Основание: включение полного кабинета
(ADR-0019, дополнение 14.11.2026) добавляет к учётной записи четыре таблицы с персональными данными:
`user_saved_items`, `user_watches`, `user_exports`, `user_preferences` ([контракт](../data-contracts.md#c11-cabinet-2026-10-09)).

Что фактически делает код (сверено 14.11.2026, ветка агента кабинета):

| Таблица | Что хранится | Сколько | Когда удаляется |
|---|---|---|---|
| `user_saved_items` | избранное: показатели, страны, регионы, сравнения, расчёты, виды рейтинга — вид записи, ключ (код показателя, адрес сравнения, параметры расчёта), название, дата | до 200 | по кнопке человека; вместе с аккаунтом |
| `user_watches` | ряды, за которыми человек следит («колокольчик»), дата последнего увиденного значения | до 50 | по кнопке; вместе с аккаунтом |
| `user_exports` | история скачиваний: какая таблица, формат (CSV/Excel), число строк, период, дата; **файлы не хранятся** | последние 200 | по кнопке («Очистить историю»); вместе с аккаунтом |
| `user_preferences` | формат чисел, валюта конвертера, главная страна; хэш (SHA-256) личной ссылки календаря | одна запись | вместе с аккаунтом; ссылка — по кнопке «Отключить» |

- Гость (без входа) сохраняет избранное **только в своём браузере** (`localStorage`); на сервер оно уходит после входа.
- Данные кабинета не передаются третьим лицам, не попадают в аналитику, рекламу и журналы событий сайта.
- Все четыре раздела входят в файл «Скачать мои данные» (JSON) в кабинете; хэш ссылки календаря и пароль — нет.
- Личная ссылка календаря (`.ics`) открывается без входа: кто знает ссылку, видит даты выхода данных по рядам,
  за которыми следит человек (без адреса почты и имени). Ссылка показывается один раз, её можно заменить или отключить.
- Серверы — в РФ (как и остальные данные сайта).

## Вопросы юристу

1. **Правовое основание.** Сейчас вся учётная запись обрабатывается «на основании явного согласия, данного при
   регистрации». Кабинет — функция, которую человек включает сам (нажимает звезду, колокольчик). Оставить
   согласие или указать исполнение пользовательского соглашения (ст. 6 ч. 1 п. 5 152-ФЗ)? От ответа зависит, нужно ли
   менять текст согласия при регистрации и `Terms.jsx`.
2. Нужно ли отдельно упоминать, что 194 уже зарегистрированных человека (боевой, 14.11.2026) получат кабинет без нового
   согласия (данные появляются только после их собственного нажатия)?
3. Формулировка про личную ссылку календаря (доступ без входа по ссылке).
4. Если владелец включит письма «колокольчика» (флаг `RUSTATS_MAIL_WATCH_DIGEST_ENABLED`, зона агента почты), нужен
   абзац о них (вариант ниже помечен).

## Предлагаемый текст (русский)

**Раздел 2, после пункта «Данные учётной записи» — новый пункт:**

> **Данные личного кабинета** — то, что вы сами сохраняете и настраиваете в кабинете: избранное (показатели,
> страны, регионы, сравнения, расчёты, виды рейтингов — их названия и параметры), ряды, за выходом новых значений
> которых вы следите, история ваших скачиваний (какая таблица, формат, период и дата; сами файлы не хранятся) и
> настройки отображения (формат чисел, валюта конвертера, главная страна). Без входа в учётную запись избранное
> хранится только в вашем браузере и передаётся Оператору после входа. Данные кабинета не используются для
> аналитики и рекламы и не передаются третьим лицам.

**Раздел 3, новый пункт целей:**

> предоставление функций личного кабинета (избранное, отметка о выходе новых данных, личный календарь выходов,
> история скачиваний, настройки отображения) — на основании вашего явного согласия, данного при регистрации
> *[или: в целях исполнения пользовательского соглашения — по решению юриста]*.

**Раздел 6, после слов о данных учётной записи:**

> Данные личного кабинета хранятся, пока существует учётная запись: избранное — до 200 записей, слежения — до 50,
> история скачиваний — последние 200 записей. Вы можете удалить любую запись или всю историю скачиваний в кабинете;
> при удалении учётной записи все данные кабинета уничтожаются без возможности восстановления. Личная ссылка
> календаря хранится только в виде необратимого хэша; кто знает ссылку, видит даты выхода данных по рядам, за
> которыми вы следите, без сведений о вас. Ссылку можно заменить или отключить в кабинете в любой момент.

**Раздел 7, заменить предложение «копию обрабатываемых о вас данных Оператор предоставит по запросу…» на:**

> Копию данных вашей учётной записи и кабинета вы можете в любой момент скачать сами одним файлом (кнопка
> «Скачать мои данные» в профиле) или запросить на адрес почты из раздела 9.

**Только если включены письма о слежении (вариант, раздел 2, к пункту о рассылке):**

> Если вы включили письма о выходе новых данных по рядам, за которыми следите, Оператор направляет их на адрес
> почты учётной записи не чаще одного раза в день. Отключить их можно по ссылке в каждом письме или в кабинете.

## Proposed text (English, for the `en.` host)

**Section 2, new item after “Account data”:**

> **Account workspace data** — what you save and set up in your account yourself: favourites (indicators,
> countries, regions, comparisons, calculations, rating views — their names and parameters), the series whose new
> values you follow, your download history (which table, format, period and date; the files themselves are not
> stored) and display settings (number format, converter currency, home country). Without signing in, favourites are
> kept only in your browser and are passed to the Operator after you sign in. Account workspace data is not used for
> analytics or advertising and is not shared with third parties.

**Section 3, new purpose:**

> providing account features (favourites, the “New” mark for new data, a personal release calendar, download history,
> display settings) — on the basis of your explicit consent given at registration *[or: to perform the terms of use —
> per the lawyer’s decision]*.

**Section 6, after the account data sentence:**

> Account workspace data is kept while the account exists: up to 200 favourites, up to 50 followed series and the last
> 200 downloads. You can delete any entry or the whole download history in your account; deleting the account
> destroys all of it irreversibly. The personal calendar link is stored only as an irreversible hash; anyone who has the
> link sees the release dates of the series you follow, with no information about you. You can replace or disable the
> link in your account at any time.

**Section 7, replace “a copy of your data will be provided on request…” with:**

> You can download a copy of your account and workspace data yourself at any time as one file (“Download my data” in
> your profile) or request it at the email address in section 9.

**Only if “followed series” emails are enabled (section 2, next to the newsletter item):**

> If you turn on emails about new data for the series you follow, the Operator sends them to your account email no more
> than once a day. You can turn them off via the link in every email or in your account.
