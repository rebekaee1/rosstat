# Повтор истории поиска и границы v2 — 30 сентября 2026

## Результат и смысл процентов

Снимок истории снят 30.09; исправления и финальная локальная приёмка
продолжены 01.10.2026 MSK.

Поиск на главной использует общую глобальную палитру: российские ряды,
международные ряды, регионы России и доступные субнациональные территории.
Все точки входа отправляют исходную формулировку в один endpoint, без
неявного ограничения Россией. Вторая версия улучшает составные понятия,
обычные вопросы на покрытых темах, географические формы, единицы и частоты,
точные названия/коды и незавершённый ввод. Это конечный детерминированный
разбор и ранжирование; обученной универсальной языковой модели здесь нет.

Первый полный прогон v2 на source9167af дал 109/110 = 99,09% strict hit@5
на ясном отобранном историческом gold и 2 615/3 664 = 71,37% nonempty
по всем q-состояниям. Полный acceptance на source60ac58 дал 109/110 hit@5 и
2 542/3 664 = 69,38% nonempty, HTTP ошибок нет. Затем новая независимая
выборка 40 дала 5/40 = 12,5% hit@5. После раскрытия её промахов реализован
третий общий repair pass; любые повторы этих 40 теперь development.
Его source31510ab9 зафиксирован на43 файлах, полная история повторена
с прежними corpus/gold bytes:108/110 =98,18% strict top5 и2 603/3 664
=71,04% nonempty, все main/nginx ответы200. Повтор inspected80 дал41/80 =51,25% top5,
inspected40 —21/40 =52,5%; оба набора без HTTP ошибок. Это development,
не независимое подтверждение переноса на новые темы.
Corpus, gold, промежуточные ошибки и обе версии сохраняются отдельно.

Этот проход выявил одну настоящую регрессию: raw «Валовой внутренний
продукт (ВВП) текущих ценах.» стал empty вместо nominal GDP. Whole-title
proof стирал `%` и ошибочно защищал другой native title «…% ВВП».
Source315 результат запечатан без исправления gold; следующий отдельный
проход сохраняет экономически значимые символы при доказательстве title.

Новая независимая выборка на source9167af дала **22/80 = 27,5% hit@5**. В ней есть факты для
всех 80 целей. Разговорные вопросы на новых темах остаются слабым местом:
**1/40**, точные описания меры — **3/20**, редкие каталожные формулировки —
**18/20**. После чтения промахов исправлены общие роли/единицы/разбор обычных слов;
на тех же 80 стало **38/80 = 47,5% hit@5**. Этот повтор является development.
Успех на знакомой истории не доказывает произвольное понимание запроса;
обе отрицательные первичные оценки сохранены.

## Что именно сохранено с сервера

Снимок PostgreSQL содержит **3 905 удержанных search events** с 29 мая по
30 сентября 2026 года, снят в 15:04 UTC / 18:04 MSK. ClickHouse содержит
6 527 копий этих событий: 3 905 уникальных и 2 622 дубликата. Их времена
сопоставлены с PostgreSQL; ClickHouse смещён на три часа. Это две копии
событий, а не 10 432 независимых поисковых действия.

В событиях есть **3 664 непустых состояния q**, **1 913 уникальных исходных
строк**, **1 915 пар (q, locale)**. Непустые запросы click-событий —
428 из 669 исторических кликов, 288 уникальных строк. Явно глобальный
context задан у **568 непустых состояний q**. Многие scope/context старых
событий отсутствуют; неизвестный scope не заменён глобальным молча.

Выгружены все 15 доступных nginx rotations: 1 108 search requests за
16–30 сентября, из них 483 с HTTP 499. Непустая q есть у 1 106 запросов;
повторяются 736 уникальных API-запросов. Часть nginx q уже содержит
клиентское расширение синонимов, поэтому не равна буквально набранной строке.
IP перед передачей преобразован в hash; сырьё и индивидуальные события
остаются в закрытом ignored каталоге, не в Git.

Побуквенная история не существовала в этой телеметрии. Debounce пропускал
промежуточный ввод; старый clamp обрезал q до 60 символов для local и 120
для global. У 85 из 132 табличных событий нет q. Новая выгрузка не может
восстановить не записанные клавиши или удалённые до retention записи.
Внешние агрегаты Метрики/Вебмастера отражают поиск Google/Яндекса и в
процент попаданий внутренних полей не включены.

Ранее реконструированные 150 технических клиентских путей и инвентарь всех
полей сохранены в [историческом отчёте](search-history-2026-09-30.md) и
[матрице](search-matrix-2026-09-30.json). Эти пути не дают relevance labels
и не устанавливают число физических людей.

## Воспроизводимый протокол

Baseline — commit `686c31d81917b814fdde7b9a409b3c24a9dba100`, содержащий
поисковую реализацию `bdcee357`. Исходная промежуточная v2 и итоговая v2
сохранены разными source snapshots и результатами; неудачный ранний прогон
не перезаписан после исправлений.

| Вход | SHA256 |
|---|---|
| Исторический corpus | `823cd2b20a4b59c88910639925b7696e7e6202528e416e9d0d3ec1faada6c3f8` |
| Исторический economic gold | `cae725346fbf5b86bdbe01d2c8d35698ab5b9fd4470e9f6e8de873bb187952b7` |
| Первый полный source manifest v2, 24 файла | `9167af6902b681e85401a77df4923f49ddda7b7b3afc790d5a3054db40ed2482` |
| Acceptance source manifest, 27 файлов | `60ac580ddcccfb194f5d4b35c2256ecb92167ede09019d65f7eb1b0801a8be7b` |
| Release3 search/SSR/home manifest, 43 файла | `31510ab9e7fa268540bd3c089450988c6efe44faf9a3a89bcf90b6d265ef8511` |
| Gold новой независимой выборки 80 | `f16b3b225fdc6143e7f03fa9b6ab54c05fa56efe278e4d954ace3b1063aced2f` |
| Queries новой выборки 80 | `b7e2302176abdf9e276230a92169e19fdd3db2662f3be0f1f05cef2429098d63` |
| Responses новой выборки 80 | `4bfc262dbd1f5e66f0b44f4f9c0fc37ee350b6753515f79aca88c584786f9f9e` |

Baseline/initial/first-full/acceptance API используют один восстановленный текущий каталог:
55 стран, 355 036 world indicators, 16 184 475 world points; 991 ряд
общего Indicator контура; 96 российских территорий, 495 региональных
метрик, 961 494 annual facts; 51 US state, 1 883 субнациональных определения,
4 477 743 points. Это снимок текущих фактов, не восстановление candidate
pool на дату каждого старого события. Read-only API wrappers не запускают
ETL, внешнюю модель, обучение, аналитические записи или production jobs.

Для всех исторических исходных пар сделан global API diagnostic. Его
nonempty доля не является общей правильностью всех локальных полей:
неизвестные старые scope, eligibility и selected peer context не восстановлены.
Явно scoped поля дополнительно проверены своим browser matcher на
реконструируемых producer pools. Nginx проверен отдельно из-за другого
происхождения q. Два worker и локальный восстановленный PostgreSQL дают
датированный timing, без production SLA.

## Все исторические запросы: coverage и recall

| Набор и знаменатель | Baseline | Первая v2 | Первый полный v2 | Acceptance v2 | Source31510ab9 | V4 |
|---|---:|---:|---:|---:|---:|---:|
| Все q-состояния, global diagnostic: непусто / 3 664 | 2 692 (73,47%) | 2 459 (67,11%) | 2 615 (71,37%) | 2 542 (69,38%) | 2 603 (71,04%) | 2 607 (71,15%) |
| Явно global: непусто / 568 | 422 (74,30%) | 377 (66,37%) | 400 (70,42%) | 386 (67,96%) | 394 (69,37%) | 396 (69,72%) |
| Старый clicked key в top5 / 428 | 237 (55,37%) | 232 (54,21%) | 236 (55,14%) | 233 (54,44%) | 239 (55,84%) | 239 (55,84%) |
| Scoped matcher: непусто / 787 | 674 (85,64%) | 713 (90,60%) | 713 (90,60%) | 713 (90,60%) | 713 (90,60%) | 713 (90,60%) |
| Nginx q-состояния: непусто / 1 106 | 851 (76,94%) | 586 (52,98%) | 729 (65,91%) | 709 (64,10%) | 725 (65,55%) | 725 (65,55%) |

Первый полный v2 дал 0 HTTP errors в main и два 500 timeout в nginx.
Полный acceptance60ac дал HTTP200 для всех 1 915 main и 736 nginx запросов,
включая оба прежних timeout. Main p50/p95 — 1 341/2 280 ms, nginx —
1 377/2 402 ms. Nonempty уменьшилось на 73 события относительно9167;
84 потерянных и11 приобретённых событий у43/8unique строк показали
регрессию настоящих native-prefix из-за control-neighbour guard.
Эта регрессия включена в следующий общий repair, а не скрыта. Медиана/p95
первого полного main — 1 041/2 240 ms; baseline — 711/2 453 ms. Медиана
ухудшилась, p95 улучшился; это local timing, не доказанная production скорость.

Число кликов не является gold правильности: пользователь мог выбрать другую
меру/страну, а старый context у части кликов неизвестен. Exact key recall
не смешивается с экономической релевантностью. Nonempty также не доказывает
попадание; короткий внутренний слог мог раньше возвращать случайный показатель.

Scoped replay охватывает 787 из 808 явно локальных запросов. У 21 нет
достаточного country/peer context. Использованы 96 current producer DTO pools
и одинаковый frozen matcher input для before/after, не исторические snapshots
каждого pool. У поднабора 714 событий exact scope восстановлен полностью:
непустая выдача выросла с 606 до 645. Остальные compatible pools имеют
отдельную пометку ограниченной реконструкции. Correctness labels у этих
локальных исторических событий отсутствуют.

Первая v2 уменьшила nonempty долю. В nginx из 267 old-nonempty → empty
случаев 211 (79%) — один-два символа. Старые совпадения по внутренним
слогам давали посторонние темы; это не доказанные правильные ответы. Итоговая
версия разрешает начало реального имени/кода компактного каталога, но сохраняет
ограничение broad world scan. Историческая доля сама по себе не оправдывает
возврат случайной карточки вместо пустоты.

## Правильная экономическая цель: строгий исторический gold

До изучения новых ответов вручную закреплены 110 ясных пар (q, locale):
83 нормализованные формулировки, 479 исторических событий. Выбраны однозначные
предмет/мера/география и заранее зарегистрированные эквиваленты native series.
Это отобранный понятный поднабор, а не unbiased оценка всех 1 913 строк.
Исходный overbroad draft и correction log сохранены; после просмотра новых
результатов gold не расширялся.

| Строгая метрика | Baseline | Первая v2 | Первый полный v2 | Acceptance v2 | Source31510ab9 | V4 |
|---|---:|---:|---:|---:|---:|---:|
| Правильная цель top1 / 110 | 93 (84,55%) | 97 (88,18%) | 105 (95,45%) | 105 (95,45%) | 104 (94,55%) | 105 (95,45%) |
| Правильная цель top5 / 110 | 99 (90,00%) | 102 (92,73%) | 109 (99,09%) | 109 (99,09%) | 108 (98,18%) | 109 (99,09%) |
| Правильная цель top100 / 110 | 105 (95,45%) | 102 (92,73%) | 110 (100,00%) | 110 (100,00%) | 109 (99,09%) | 110 (100,00%) |
| Явно global, правильная цель top5 / 86 событий | 78 (90,70%) | 76 (88,37%) | 86 (100,00%) | 86 (100,00%) | 84 (97,67%) | 86 (100,00%) |

Ранние регрессии из-за разбора составного GDP, приоритета housing, разной
нормализации ё/е и незаконченного обозначения рубля устранены общими правилами,
а не таблицей «исторический запрос → ответ». Семантический gold остался тем же.

Явно global gold содержит 86 событий, соответствующих 54 уникальным
историческим парам; event-weighted строка не означает 86 разных запросов.

Оставшееся строгое несовпадение для annual inflation не переименовано в hit:
WEO annual mean YoY CPI соответствует этой экономической мере по действующему
ingest/world-rank контракту, но не включён в frozen native-only accepted set.
Native target оказался на 58-м месте. Валидная альтернатива объясняется отдельно,
не повышает заранее заданный strict score и не устраняет ranking limitation.

## Случайные новые формулировки и независимость

Первая закрытая проверка содержала 120 случаев: 40 natural, 40 precise,
40 rare catalogue; 60 RU/60 EN и 30 каждого контура. Все цели имеют finite
facts. Первая v2 дала **52/120 top5 (43,33%)**, top1 50/120, без HTTP errors.
Natural — 4/40, precise — 10/40, rare — 38/40. Сохраняются raw inputs,
availability proof и первичный отрицательный результат.

После чтения этих ошибок набор стал development corpus. Общие исправления
grammar/quantity/geo довели промежуточный development replay до 87/120 top5
(72,50%). Это возврат регрессий на уже известных примерах, не новый blind score;
его source snapshot предшествует итоговому release freeze.

Для проверки переноса создана отдельная новая выборка 80: 40 natural,
20 precise, 20 rare; 40 RU/40 EN; 20 каждого контура; 11 world countries,
20 российских регионов, 20 US states. Native codes и формулировки отличаются
от первого набора. Gold, queries и availability proof закреплены до API
ответов; source и входы проверены до запуска, каждые 20 запросов и после.

Первый полный source9167af: **22/80 top1/top5/top20, 23/80 top100, MRR 0,27513**.
RU — 10/40, EN — 12/40; Россия — 5/20, world — 5/20, регионы России —
8/20, US subnational — 4/20. Получено 23 непустых ответа, 55 `no_coverage`,
один `unsupported_period`, один `ambiguous_geography`. У всех 57 пустых
или reason-failed целей существуют настоящие finite facts; для world
дополнительно доказаны ненулевые значения. Availability не объясняет эти
семантические промахи. Все 80 transport responses — HTTP 200.

После чтения этих 80 source60ac58 повторён на тех же frozen gold/query bytes:
**36/80 top1, 38/80 top5 (47,50%), 39/80 top20/top100, MRR 0,46354**.
Natural — 13/40, precise — 7/20, rare — 18/20; RU — 16/40, EN — 22/40.
По контурам hit@5: Россия 11/20, world 5/20, регионы 13/20, US subnational
9/20. Все 80 HTTP200; 40 непустых ответов, 39 no_coverage, одна ambiguous
geography. Это **development repair**, не новый blind score и не доказанное
понимание всех 80 целей. Исходные misses, cases и accepted targets не менялись.

Стратифицированная выборка не моделирует реальную долю каждого типа спроса.
Автор gold знает репозиторий и прежний поиск, но не видел ответы нового набора
до freeze и не менял oracle по ним. Это независимость от outcome adjustment,
не zero-knowledge judging. Два blind набора имеют разные запросы и версии;
43,33% и 27,5% нельзя объявлять controlled before/after падением или усреднять.

Новый независимый40 на source60ac58: **5/40 = 12,5% top1/top5/top100**,
MRR0,125; natural1/20, precise1/10, rare3/10; RU1/20 EN4/20;
Russia1/10 world0/10 region3/10 subnational1/10. Все40HTTP200,
35пустых при доказанных finitefacts:33no_coverage,1unsupported_period,
1unsupported_query. Seed3618675395; targets disjoint предыдущим120/80.
World2% TABLESAMPLE capped600 не является равномерным всемкаталогом.
Gold `baba184ca7fbc891327ba13244f4cd31d3c679589f9a1e4a67048c294bc782dd`,
queries `9832e85d6933d058289b57496697a2d50429d089d3afda15fdab32edbbb775d0`,
availability `8397d171796ecd47c757d43bbee8949293ece1264291bfdded93ad82dbfb645c`,
seal `2498989b7e02a068160e8b831ae3215426ef4caaf6a5d76704892b249ce991cf`.
Оценка12,5% сохранена; после диагноза этот набор становится development.
Выявлены общие PP/nativecurrency/temporalrole/native-title и year+mode
contract дефекты. Отсутствие ошибок HTTP не означает понимание вопроса.

Новая независимая40 на текущем source31510ab9: **13/40 =32,5% top1/top5/top100**,
MRR0,325. Natural3/20, precise4/10, rare6/10; RU7/20, EN6/20.
По контурам: Россия5/10, world1/10, регионы4/10, USsubnational3/10.
Все40HTTP200;27пустых при подтверждённых finitefacts —23no_coverage,
2ambiguous_geography,2unsupported_period. Seed441985506; nativecodes
не пересекаются с предыдущими120/80/40. Inputs/gold/proof запечатаны доAPI;
43sourcefiles и все sealedinputs проверены before/10/20/30/40/after.
Итоговыйseal `20fd5d04a3450bf2f2f2b793113bbd620ab199c35b9a7eb575a0b14577cff0f8`.
Выборка world остаётся ограниченной неравномерной block sample; экономически
неоднозначные BTC/Silver исключены до freeze. Source/outcomes не менялись.
Схема старого generator неожиданно содержала прежние запросы: это открыто
зафиксировано; новая формулировка построена по новым native metadata,
реализация и старые ответы автором до freeze не читались. Эта оценка показывает
оставшиеся ограничения; разные blind40 не являются pairedbefore/after.

## Новая независимая выборка V4: 80 запросов, 01.10

На новом source `259cb677` (51 файл) отдельный автор до ответов заморозил
80 запросов: по20 Russia/world/RUregion/USstate,40RU/40EN,
40natural/20precise/20rare. Seed `1295959268`; цели выбирались из полных
каталогов945/495/1882/278169, без прежнего world block-sample cap. Коды
исключены из предыдущих120/80/40 и release3fresh40. Формулировки опирались
на native metadata; для20 Eurostat целей сохранены official member labels.
Открытое ограничение независимости: схема старого генератора содержала
методологическую прозу; автор сообщил об этом до freeze и не использовал
старые запросы/ответы или реализацию. Все80 delivery responses до freeze
показали тот же code и выбранное finite значение;78 SSR200 и2 SSR301
с потерей режима отмечены в gold до поиска, не исключены.

Первичная оценка: **8/80 top1/top5/top100 =10%**, MRR0,10;
**80HTTP200,0errors,72empty**. Natural3/40, precise3/20, rare2/20;
RU3/40,EN5/40;Russia0/20,world0/20,RUregion3/20,USstate5/20.
Причины API:67no_coverage,2unsupported_query,3unsupported_period.
Однопоточный local replay выполнялся параллельно с двухпоточной историей:
p50/p95 399,96/685,35мс; максимум1323,56мс. Это не production latency.
Все51 source SHA, runtime PID, query/gold/proof и старые gold проверены
before/every20/after. Finalseal:
`1af29fe0679b2762f6a619378b40fd1ef42298147206d35ec7dfe93ae5be7aea`.

После ответов независимый смысловой разбор установил **одну ошибку эталона**
(#16: вопрос о месячном годовом процентном изменении, gold выбирает дневной
уровень долларового индекса в пунктах) и **три недостаточно определённые
формулировки** (#30 уровень ограничения активности, #39 весь секторM либо
regulated M_STS subset, #64 earnings либо иной отраслевой доход).
Исходные8/80 и gold не пересчитаны. Все8 hits относятся к76 clear cases;
их68 промахов прослежены до5parser declines,18world exclusions доLIMIT,
44required-term exclusions и1measure guard. Факты80native целей остаются
доступными. Diagnosisseal `cbb047d81d768c19a2d4cf35dd404dcf10e2d2191af2971b3472b7e17952246d`.
Этот набор после разбора является development; последующие улучшения на нём
не устанавливают новую независимую точность. Общие ремонты V5 реализованы отдельным source freeze; V4 source snapshot
и первичные ответы сохраняются побайтово.

## V4 завершён; V5 и повтор разобранных ошибок

Полностью запечатанный V4 source259cb677 вернул raw nominal GDP на первое
место:109/110 =99,09% strict top5;2 607/3 664 =71,15% nonempty.
Все1 915main и736nginx запросовHTTP200;nginx coverage725/1 106 =65,55%.
Seal `1eeede74920934675cc7ea9e1b89f30f68dc6ec798668de6083aa28fdedb1663`
сохраняет шесть фаз сравнения и неизменные corpus/gold bytes.

V5 разделяет registered source/output frequency, terminal end-of-period,
monetary valuation и observation/base year. Полное свидетельство оценки
находится в одном title/code либо одной native unit подписи; частичные поля
не соединяются. Price subject требует native названия либо точного товарного
семейства с денежной единицей на физическое количество. Расширены проверенные
Eurostat roles:17 официальных осей/34member пары,18 новых named facets,
29 поддержанных осей в общем inventory. Numeric/bool/list/object JSON не
заменяет строковый member; total другой оси не снимает обязательное уточнение.
Полные bounded словоформы и кеши2048/4096 хранят только чистое вычисление,
не ответы пользователей и не исторический oracle.

До окончательной integrated проверки private sourcec9668f27 повторён на тех же
inspected80 из V4:19/80top1,22/80top5 =27,5%,23nonempty,0HTTP errors.
Natural8/40,precise6/20,rare8/20;RU11/40 иEN11/40top5.
Это development улучшение относительно исходных8/80, а не новая blind
оценка. Gold/query/первичный seal и ранее ошибочный harness run20 сохранены;
первый runner сломал summary на None после20HTTP200, новый уникальный runner
повторил все80 без перезаписи прежних ответов. Восемь pre-fix source файлов
сохранены отдельным immutable snapshot,seal91e1c0b5.

Integrated suite обнаружил четыре nominal/control-form несовпадения,
включая ошибочное «методами»→«методи». Грамматическое окончание исправлено;
неизвестные control/unit forms не становятся domain словами. Exact alias
«долларами» проверяется по actualUSD unit с CAD/missing/title-only negatives.
После этого source9839569d закреплён на54файлах и прошёл910 search/year
проверок17,00s и86UI проверок3,06s. Старые pre-fix22/80 не присвоены
автоматически окончательным байтам; final historical replay и новая отдельно
зарегистрированная выборка получают собственные ответы/seals. Production
не менялся. Полный V5 replay выполнен на перезапущенном readonlyROOT8017
PID43743; последующий результат зафиксирован ниже.

## Запечатанный V5 и отдельное исправление V6

V5 source9839569d/54 files:1 911main HTTP200,4HTTP500;735/736nginx HTTP200,
один основной HTTP500 сохранён среди247same-V5reuse; все489freshnginx
HTTP200. Owned ASGI журнал содержит ровно4asyncpg statement timeout на
worldcandidate SELECT. У trace нет request ID/timestamp; сопоставление
с четырьмя HTTP500 ограничено общим прогоном, exact trace→ID не заявлено.
Seal `93771279f0600fad331ed9f99f73f701ab90d97ee806a98ebf1f08eee9b57cf2`;
seven-phase comparison
`e95a9e919d16520027153057c3cb30d8f94a5d107700974507f0a66568473112`.
Independent verification проверила source54/snapshot54,259previousfiles,
raw IDs/q/locale, gold110/86/479, harness и same-version reuse.

Strict110:103/110top1=93,64%;107/110top5=97,27%;3empty. Weighted479:
459/479top1 и467/479top5. Coverage:2 532/3 664client events=69,10%;
nginx695/1 106=62,84%; scoped713/787=90,60%,21scopeunreplayed.
Это сниженная наблюдаемая оценка V5; она не заменяется предыдущим V4.
Raw native prefixes ruoni/«безра»/«золотова» утратили rank1; «годовая
инфляция» улучшилась58→1. Во всей истории40запросов потеряли непустую
выдачу и один получил; coverage delta не означает correctness delta.

V6 ремонт общий: original raw singleton сохраняет prefix/fuzzy retrieval,
additional nominal forms и уже разобранные nominal OR группы требуют
полных слов. Static native member labels порождают точные axis/member
Boolean predicates при прежних provider/string-type/facet/unknown guards.
Label text для measure/display сохраняется через один CASE на ось.
На четырёх ошибочных формулировках readonly EXPLAIN без ANALYZE показал
64–126тысяч байт SQL до ремонта и5,6–9,9тысяч после. Это размер конструкций,
не production benchmark. Независимая hermetic проверка сравнила804старых/
новых CASE outputs,5typed cases и5raw/added-form controls; liveSQL0.
Девелоперские first-response probes и финальная история имеют отдельные
receipts. Нераскрытая новая preregistered40 не использована для V6 ремонта.

## Первый новый40 на окончательном V6

Source `9c6fdd77`/56 files, перезапущенный readonly ROOT8017 PID47102,
940 search/year/default-mode controls и86UI checks; полная retained history
на этих байтах ещё выполняется под новым tag `v6final`. Источники после
начала оценки не меняются. Исходный V6 подготовительный tag был занят
pre-run runtime log; отдельный чистый tag сохраняет оба первоначальных
bootstrap журнала и неизменный source manifest.

Новый seed12875437743505664700 зарегистрирован до выбора frames. Полные
frames:945Russia,354122world,46035definition×region,95982definition×USregion;
known native codes из семи прежних gold исключены. После независимого
shuffle выбраны40уникальных целей, по10на контур,20RU/20EN,20natural/
10precise/10rare. Это случайная выборка записей/пар, затем авторские
формулировки; не traffic-weighted population accuracy и не равномерная
выборка всех мыслимых предложений. Автор видел реализацию, но ответы до
фиксации gold/query/protocol не видел. Root semantic corrections до
search сохранены отдельно; после ответов gold не менялся.

Перед первымsearch проверены все40actual native facts и80API/SSR endpoints:
40deliveryHTTP200 с exact code/geo/date/value;SSR35×200,4×404,1×301.
Те же endpoints вновь проверены на final PID; замены целей0. Все205input
иprimary body hashes,7priorgold hashes и56source проверены.

Первый final V6 прогон: **17/40top1=17/40top5=42,5%**,40HTTP200,0errors,
17nonempty и23empty. Natural3/20=15%,precise8/10=80%,rare/native6/10=60%.
Russia5/10,world0/10,regions6/10,subnational6/10;RU7/20,EN10/20.
Empty reasons:20no_coverage,2unsupported_period,1unsupported_query.
Secondary exact year native paths8/10; это отдельная маршрутная проверка.
Наличие исходных фактов не означает поддержанную year/hidden destination
или языковой recall. Сохранены ровно40firstbodies, raw IDs, native ranks,
шесть source/PID/input guards; retries0. Seal
`2ed4d7f111937fbf669a43a0915d1af1f4fcf4d4209e260fd2ff99296a4862b0`;
independent completion повторно проверила130outcomefiles и205inputs.

Результат не подтверждает сильное универсальное понимание: новые
разговорные и международные формулировки остаются слабым местом.
Последующий разбор ошибок является development; первичная оценка42,5%
сохраняется. Данные предыдущих независимых выборок отличаются, поэтому
их проценты не объявляются paired причинным улучшением.

## Изменения и оставшиеся границы

Основной механизм описан в [контракте поиска](../search.md). V2 применяет
compound concepts до отдельных слов/typo; извлекает вопросительную роль,
subject, меру, country/region, дату, native unit и частоту. Неизвестные
содержательные qualifiers остаются обязательными. Typed guards общие для
Python/SQL и действуют до candidate budget на больших world наборах.
Они различают покрытые count/rate, nominal/real и другие пары, но набор конечен.

Подтверждённые code/native title защищены от внутренних дат и периодов;
длинные native prefixes поддерживают старое обрезание строки и незавершённый
ввод. Географические формы строятся от настоящего каталога, including full
oblast/republic/autonomous/remainder names и English possessive. `remainder`
имеет intent, но не новый delivery route. Настоящий unknown suffix не исчезает.

Ранжирование добавляет bounded title-only inverse frequency
`6*log1p((N+1)/(df+1))`, с capped semicolon penalty; exact scores ≥900
не меняются. Это не corpus BM25, embedding, learned rank или вероятность.
Существующие facts/canonical routes, storage planes и eligibility не заменены.

Source60ac58 устраняет обнаруженный pension amount/count edge, различает
credit stock/rate/origination, research personnel/organizations, employment/
compensation/benefit и валютную пару/index. Обычный дефис не превращается
в code; короткое hold/цены не автокорректируется в другой предмет. Native
per-N-persons требует конкретный знаменатель; валютный демоним не задаёт страну,
площадь в гектарах не подменяется yield. Общие SQL/Python guards проверены
положительными и отрицательными примерами, без lookup «запрос → answer code».

На source31510ab9 целый каталоговый title span защищён до разбора внутренних
географии/дат/%; внешний qualifier остаётся обязательным. Native code и
настоящий prefix имени отделены от control-word typo. Большой world preflight
ограничен тремя самостоятельными indexed probes с LIMIT128 на каждый;
общий OR всех окон в промежуточном кандидате вызывал actual8s PostgreSQL
statement timeout, поэтому этот кандидат не принят. Для трёх проблемных
запросов EXPLAIN у новой формы показал GIN/Bitmap, а known40 replay —0errors.
Это bounded discovery: найденный native span точен, но произвольное имя не
гарантированно попадёт в budget. Cold latency и planner зависят от окружения.

Проценты/PP и литр/тонна/кг проверяются по настоящей unit, общая dollars
подпись получает USD только от объявленной валюты US state producer. Role
сравнения с предыдущим месяцем/кварталом задаёт независимые frequency и mode.
Eurostat exactaxis/member constraints и nativefieldlabels действуют доLIMIT;
другая ось TOTAL, category/SEO и отсутствующее поле не подменяют уточнение.
Год России с registeredmode рендерит факты точного storedcode и сохраняет
canonical/navigation; worldyearmode и derivedmonth остаются unsupported.

Открытые ограничения: незнакомые subject/role formulations и отсутствующий
sliceaxis даже при fixed-age названии; исправленная compound phrase не всегда
видна в `corrected_query`. Candidate budgets и разрешённые routes остаются
ограничениями retrieval. `no_coverage` может означать отсутствие понимания при
наличии фактов. Следующий семантический канал требует independent acceptance,
строгих typed gates и измерения ресурсов на сервере 4 vCPU.

## Проверки и состояние

Датированный source31510ab9: **549 search/year tests**, **86 frontend tests /5files**
и43 exactsource files. Отдельные известные80/40 development API replays
прошли без ошибок; первичные blind scores сохранены.

Предыдущий source60ac58: **357 search tests** на неизменённых27файлах.
Полный acceptance suite: **3 421 passed / 9 skipped**; frontend **970 passed
/ 117 files**, lint/build, indicator/meta/language и knowledge guards прошли
в `check-all.sh`. Предыдущий source9167af сохранил **3 286 / 9 skipped**.
Интерфейс: **178 focused tests**, полный suite **970 passed / 117 files**.
Homepage tests используют настоящий hook/shared adapter с mock transport:
raw question, four planes, locale/cache, stale state, eligibility и IME.
Это компонентные проверки, а не production browser acceptance всех полей.

Реальный локальный браузер: RU desktop question → cash M0 → действующая
карточка с 405 observations и значением 20 744,7 млрд ₽ за август 2026;
RU wage question → карточка real wages; EN mobile → California Population
с настоящей карточкой/графиком. Проверены видимые варианты ответа, canonical
переходы и отсутствие horizontal overflow в проверенных viewport.
Source60ac58 дополнительно проверен в RU homepage raw-question
→ first M0 → та же настоящая карточка/график, с отдельным screenshot.
Source31510ab9: RU homepage → Norway oil imports/allpartners/2024 → first
native destination; существующий worldyear SSR через Compose/nginx3000
показал8 707,54тыс.тонн. Vite5178 подтверждает новый поиск и document URL,
но не рендерит publicyear SSR. Новый Russia2026/qoq standalone через
собственный8017adapter показал фактические1,42 и−0,97п.п., среднее0,22п.п.;
parent/graph/neighbor years сохранилиmode. Это actualrootSSR, без проверки
нового container image/nginxcache или production. Bundle содержит отдельные
browser records и screenshotSHA.
Screenshots находятся в закрытом audit bundle; это UI proof на local API,
не production acceptance или 150 новых browser journeys.

Knowledge/maps/full script gates прошли на source60ac58; после итоговых
таблиц выполняется финальная проверка identity/согласованности знаний. Fresh agent без истории чата восстановил four-plane UI/API/data/navigation
маршрут по README/CONTEXT/architecture/contracts/search/ADR; code/source SHA
совпал с freeze. Исправлены найденные пояснения issuer metadata, прежнего
pension edge и transport/hook retry. Его проверка была read-only source,
не API/browser/prod acceptance.

Работа локальная; push/deploy/live acceptance не выполнялись. Версия
API `federated-v2` и client cache revision `v3` не обозначают выпуск на сервер.
