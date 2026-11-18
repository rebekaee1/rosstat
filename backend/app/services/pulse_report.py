"""LLM-отчёт «пульса» в Telegram (П9б, 2026-07-02).

Пайплайн: снапшот дня (`pulse.py`) + память прошлых дней → OpenRouter
(model = settings.openrouter_model) → человеческая сводка на русском →
Telegram-сообщение владельцу (`settings.pulse_chat_id`) с новым оформлением
Bot API: expandable blockquote для сырых цифр + inline-кнопки, которые
обрабатывает `telegram_bot.py` (getUpdates-поллер).

Контроль контекста: модели передаём полный снапшот ТОЛЬКО за отчётный день;
прошлые дни — компактная память (числовое ядро + однострочная сводка),
поэтому окно не растёт с историей. После отчёта сводка дня записывается
в память (TTL 30 дней) — так у системы есть «вчера» и тренд недели.

Сеть (2026-07-08): прод-сервер российский, OpenRouter/Anthropic/OpenAI/Groq
блокируют его на границе Cloudflare (гео/санкционный комплаенс). Обход —
`settings.openrouter_proxy_url` (HTTP-forward-proxy на внешнем не-РФ хосте,
только для этого запроса); детали и security-модель прокси — `docs/backlog.md`.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timedelta, timezone
from html import escape

import httpx
from sqlalchemy import select

from app.config import settings
from app.database import analytics_session
from app.models import Hypothesis
from app.services import pulse
from app.services.display import today_msk
from app.services.alerting import digest_recipients
from app.services.pii_scrub import sanitize_memory_for_llm, sanitize_snapshot_for_llm, scrub_value
from app.services.telegram_bot import main_menu_keyboard, send_message

logger = logging.getLogger(__name__)

# Telegram parse_mode=HTML принимает только свои теги; всё прочее (в том числе «<» из
# текста LLM, например «норма < 2500 мс») обязано быть экранировано, иначе Bot API
# отвечает HTTP 400 «can't parse entities» и дайджест не уходит (2026-10-17: два адресата).
_TG_ALLOWED_TAG_RE = re.compile(
    r"</?(?:b|i|u|s|code|pre|blockquote|tg-spoiler)(?:\s[^<>]*)?>|<a\s[^<>]*>|</a>",
    re.IGNORECASE,
)
_HTML_ENTITY_RE = re.compile(r"&(?:#\d+|#[xX][0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]*);")


def _escape_text_run(text: str) -> str:
    """Экранирует «<», «>», «&» в обычном тексте, существующие сущности («&amp;») не трогает."""
    out: list[str] = []
    pos = 0
    for m in _HTML_ENTITY_RE.finditer(text):
        out.append(_escape_plain(text[pos:m.start()]))
        out.append(m.group(0))
        pos = m.end()
    out.append(_escape_plain(text[pos:]))
    return "".join(out)


def _escape_plain(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def sanitize_llm_html(text: str) -> str:
    """Оставляет разрешённые Telegram-теги, остальной текст экранирует для parse_mode=HTML."""
    out: list[str] = []
    pos = 0
    for m in _TG_ALLOWED_TAG_RE.finditer(text):
        out.append(_escape_text_run(text[pos:m.start()]))
        out.append(m.group(0))
        pos = m.end()
    out.append(_escape_text_run(text[pos:]))
    return "".join(out)

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

_SYSTEM_PROMPT = """Ты — аналитик forecasteconomy.com (экономическая статистика России). Раз в
день тебе присылают JSON с активностью сайта за сутки и краткую память по
прошлым дням.

Прочитай и напиши владельцу короткую записку — как понимающий человек, а не
как отчёт по шаблону. Что реально стоит внимания: рост/спад, аномалия,
проблема (ошибки фронта, упавший ETL, запросы в поиске без результатов — это
пробелы каталога, их стоит явно назвать). Разрез authed/guest в данных — это
зарегистрированные и гости сайта; упомяни, если там есть что-то интересное, не
ради галочки. Если день обычный — так и скажи в паре строк, не придумывай
значимость там, где её нет. Длину и структуру выбирай сам по ситуации.

Блок behavior — сырой поведенческий поток (наша «видеокамера»): просмотры
страниц, каждый клик по элементам интерфейса, время и глубина скролла по
страницам, что копируют. dead-клики — человек кликнул в некликабельное (ждал
реакции — её нет), rage-клики — злая серия кликов в одну точку; и то и другое —
прямые сигналы UX-проблем, называй конкретный элемент и страницу. У каждой строки
dead_clicks_top и rage_clicks_top два числа: n — клики, sessions — сколько разных сессий
(людей) их сделали. Суди по sessions: десятки кликов при sessions=1 — один человек, пиши
«один человек», не «люди», и не называй это главным сигналом дня. Тенденция — от трёх сессий.
Счётчик behavior.by_type.js_error включает роботов: безголовые браузеры фермы
не грузят картинки и Метрику и шлют по ошибке на каждый файл. О поломке сайта
говори только по marts.reliability: js_errors_real_own (ошибки кода) и
js_files_failed_own (файлы не загрузились у людей с кликом или движением);
js_files_failed_inert_sessions — то же у сессий без единого действия, это
роботы, не баг. seo.available=false с reason «webmaster token expired» —
токен Вебмастера истёк, владелец знает и обновить его не может: не напоминай
об этом и не делай выводов об индексации в Яндексе за этот день. etl.source_unavailable_indicators — ряды, у которых
не ответил источник (Росстат, Минфин и т.п.): это авария у источника, данные
догрузятся сами; не называй её проблемой нашей синхронизации. Число упавших рядов - etl.failed_indicators
(из них наших ошибок - etl.failed_own_indicators); etl.failed_indicator_ids - только первые 20 id, не считай по нему.

Блок acquisition — привлечение из Яндекс.Метрики: источники трафика
(реклама/органика/прямые/переходы с сайтов), поисковики, поисковые фразы,
рекламные кампании. Фразы — самое ценное: по ним видно, что люди ищут и чего
сайту не хватает. Если по фразам виден спрос, который мы не закрываем, —
скажи об этом прямо, это кандидат на новый раздел или текст.
Не сравнивай абсолюты разных дней недели как «трафик вернулся» (воскресенье
не равно среде). Пустой Referer — прямые по HTTP, не «откуда узнал».
Last-click Метрики не значит, что человек сегодня пришёл из рекламы.
ChatGPT / Алиса / Perplexity называй, если они есть в данных; Нейро Яндекса
отдельной метки не имеет и сидит внутри поиска Яндекса. Роботов в прямых
не путай с людьми.
Падение рекламных визитов до нуля не доказывает остановку кампании: причина
неизвестна без подтверждения из рекламного кабинета. Отделяй наблюдение от
гипотезы, не утверждай ни отключение рекламы, ни сбой Метрики по одному нулю.
traffic_sources с id=ad — платное привлечение, не обязательно Яндекс.Директ.
id=organic — органический поиск. ad_campaigns — строки UTM-отчёта Метрики,
не число активных кампаний и не статусы кампаний рекламного кабинета.
metadata.reports описывает сохранённые отчёты: missing — отсутствует,
failed — известен сбой синхронизации, stale — есть только другой день,
invalid — нет пригодного ответа. metadata.sync — журнал нашей синхронизации,
не статус API или рекламной кампании. available с пустым полным отчётом —
фактический ноль в выгрузке; null или отсутствующий отчёт не равны нулю.
Учитывай дату, sampled и полноту total_rows/returned_rows; суммы ограниченной
выборки не выдавай за весь трафик. Старые записи памяти без metadata могут
содержать неподтверждённые нули и выводы: не используй их как доказательство.
Партнёрский доход marts.partner_revenue — доход площадки от РСЯ, не расходы
на Директ и не платное привлечение. Держи отдельно платное привлечение,
органический поиск и доход РСЯ. days содержит даты дохода: для отчётного дня
используй только совпадающую дату, отсутствие строки не означает нулевой доход.
Не выдавай total_revenue_rub за сутки: это сумма окна витрины. Расходы ad_costs
и доход партнёра — разные показатели; прибыль без сопоставимых данных неизвестна.

Блоки ревизии 16.11.2026 (только суммы, без людей):
mail — почта сайта: letters_by_kind (письма дня по видам и итогам: sent — принято почтовым
сервером, bounced — вернулось, failed — не ушло, disabled/blocked — почта выключена или адрес не в
списке допуска, это не сбой), events (open — открыли люди; open_machine — открыла почтовая
программа сама, это не интерес; click — переходы на сайт), last_campaign — последний выпуск рассылки:
дошло, открыли, перешли, что смотрели в визите (visit), какие блоки письма сработали (blocks),
вернулись ли на сайт (returned: people и то же окно до письма same_window_before_send — сравнивай
с ним, а не с нулём; window_complete=false — срок ещё не истёк, не делай выводов), отписки,
отказы от личной подборки, жалобы. last_campaign=null — выпуски людям ещё не отправлялись: не
пиши «никто не открыл». tracking=false — учёт писем выключен. open_tracking=false — счётчик
открытий выключен намеренно (с ним Яндекс Почта прячет шапку письма): открытий в данных нет по
определению, opened_people=null. Не пиши «открытий нет», «никто не открыл», не называй это
странным и не выводи из этого спам или сбой учёта; интерес суди только по переходам
(clicked_people, click_sessions). Доля открытий всегда занижена (почта без картинок их не показывает).
consents — согласия дня: сколько новых подписались на рассылку, отписки, отказы от подборки.
cabinet — личный кабинет: избранное, слежения («колокольчик»), выгрузки, настройки.
public_bot — публичный Telegram-бот: чаты, активность, темы. research — скачивания исследований.
world_ingest — загрузка мировых данных (datasets_failed — наборы с ошибкой). freshness — сколько
российских рядов каталога устарели по правилу сайта (levels.stale) и какие дольше всех; рост
stale — сигнал, даже если ETL формально зелёный. telegram — доставка сообщений этого бота:
failed — владелец что-то не получил. calendar — публикации официальных данных: что вышло в
отчётный день и что ждём в ближайшие три дня (если вышел важный показатель и к нему пришли люди —
свяжи это). Раздел с полем error не посчитался: не делай по нему выводов.

Блок seo — индексация в Яндексе: sitemap_urls_total (сколько URL публикует
сайт), searchable_pages (сколько реально в поиске по Вебмастеру),
indexed_share_pct (доля), excluded_pages, sqi (ИКС), site_problems,
exclusion_reasons_sample (топ-5 причин исключения страниц из поиска по свежей
выборке событий — например DUPLICATE/LOW_QUALITY/HTTP_ERROR; пусто = выборка
недоступна, не значит «причин нет») и top_search_queries (спрос по
показам/кликам/позиции за последний известный день). available:false — токен
не настроен или Вебмастер недоступен, не считай это нулевой индексацией. Если
доля индексации низкая или сильно
изменилась — это стоит подсветить отдельно, это метрика роста трафика.
seo.in_search_freshness — от какого дня число «в поиске» (date) и предыдущая точка Яндекса
(previous_date, previous_value, gap_days). Яндекс обновляет его раз в 2–3 дня; data_gap=true
(в seo или у хоста в summary_by_host) — между точками больше недели без данных Яндекса (так было
08.10–13.11.2026 после аварий в дата-центрах Яндекса): разница накоплена за весь перерыв, это
пересчёт базы Яндекса, а не падение за день. Не пиши «упало с X до Y» и не выводи из этого
исключение страниц или санкцию; называй обе даты. Страницы ушли из поиска, только если это видно в
exclusion_reasons_sample, и вред для сайта — только если упали переходы из поиска Яндекса
(marts/acquisition). Одно и то же searchable_pages в памяти с одной и той же seo_in_search_date —
данные Яндекса стоят, а не «без изменений».

Регистрации и воронка (marts.signups_7d, marts.signup_funnel_7d, marts.goal_usage_7d,
users.new_list): имён и почт новых людей в данных нет — только число, способ входа и
язык сайта. signups_7d: locale — язык сайта, на котором человек
регистрировался (ru/en; unknown — язык не определён, это не ноль), origin.foreign —
страна первого визита не Россия (это не то же самое, что английская версия: на ней
бывают и россияне), channel/device/trigger — откуда пришёл и что подтолкнуло
(gate_* — упор в лимит гостя, nudge — приглашение на странице, header — кнопка в
шапке, direct — сам). signup_funnel_7d: шаги не вложены друг в друга, регистрации
считаются по аккаунтам, остальное по людям; dropped_at — на каком шаге ушли те, кто
дошёл до лимита или кнопки и не зарегистрировался; weakest — самое слабое звено при
базе не меньше 10. goal_usage_7d: has_data=false значит «разрезы не посчитаны», а не
«действий не было». Воронка и язык — наблюдение, причина неизвестна: не объясняй
падение или рост конкретной причиной без подтверждения.

Блок hypotheses в конце входа — булев слой знаний: открытые гипотезы о
пользователях и сайте. Твоя обязанность — вести его: пересматривай открытые
гипотезы по свежим данным (подтверждай/опровергай, если оснований достаточно)
и добавляй новые проверяемые гипотезы, когда данные их подсказывают. Гипотеза —
конкретное проверяемое утверждение («фразы про X дают визиты, но раздела X
нет — трафик уходит»), не банальность.
Перед тем как добавить новую, найди в блоке гипотезу о том же (та же страница,
тот же элемент, тот же показатель или та же причина) и обнови её по id: повтор
темы новой записью запрещён. Если тема повторяется много дней подряд и данных
достаточно, закрой её вердиктом, а не переписывай заново.

Блок «Контекст проекта» в начале входа — что происходит в проекте: последние выпуски
(заголовки изменений), режимы и флаги, события и решения с id, датой и тем, что ждать
в цифрах, остаток счёта OpenRouter. Прежде чем назвать изменение метрики обвалом,
ростом или поломкой, сверь его с контекстом: если запись объясняет изменение (смена
счёта, фильтр роботов, выпуск, авария источника, эксперимент), прямо назови её [id] и
не выдавай за новость. Если запись контекста объясняет открытую гипотезу, закрой
гипотезу вердиктом со ссылкой на [id] в rationale, а не заводи новую. Перед датами
замеров экспериментов из контекста не делай выводов о их исходе.

Цифры — только из данных, ничего не выдумывай и не округляй заметно.

Формат — Telegram HTML: <b>, <i>, <code>, <blockquote>. Markdown и списки через
"-"/"*" не рендерятся Telegram, не используй их.

В конце ответа, после строки ---HYPOTHESES---, выведи JSON-массив изменений
гипотез (может быть пустым []): [{"id": число или null для новой, "statement":
"утверждение", "verdict": true|false|null, "confidence": 0.0-1.0, "rationale":
"на чём основано"}]. Не более 5 новых или обновлённых гипотез за день; закрытия
существующих гипотез вердиктом (true/false) со ссылкой на [id] записи контекста в rationale
идут отдельно — до 15 за день, ими расчищай завал открытых гипотез. Всё до разделителя — текст
сообщения владельцу, без преамбул."""


_HYP_SEPARATOR = "---HYPOTHESES---"


# Сколько открытых гипотез видит модель и сколько знаков каждой. До 13.11.2026 в контекст шли 30 самых старых
# открытых гипотез: всё, что записано после августа, модель не видела, не могла пересмотреть и записывала заново.
# За четыре месяца набралось 266 открытых при примерно 60 темах («нет цены на сталь» двенадцать раз, «ошибки
# загрузки файлов после выкладки» двадцать пять раз). Теперь модель видит свежие гипотезы, а новая запись,
# почти дословно повторяющая открытую, обновляет её (`similar_open_hypothesis`).
OPEN_HYPOTHESES_IN_CONTEXT = 120
OPEN_HYPOTHESIS_CONTEXT_CHARS = 200
# Косинус по основам слов с весом редкости: 0,6 ловит перефразировку с теми же ключевыми словами и не склеивает
# разные темы одного шаблона («нет показателя X» и «нет показателя Y»). Подобрано на 266 гипотезах боевого.
SIMILAR_HYPOTHESIS_THRESHOLD = 0.6
_HYP_WORD_RE = re.compile(r"[a-zа-я0-9]+")


def _hypothesis_stems(text: str) -> set[str]:
    words = _HYP_WORD_RE.findall(text.lower().replace("ё", "е"))
    return {w[:5] if len(w) > 5 else w for w in words if len(w) >= 3 or w.isdigit()}


def similar_open_hypothesis(statement: str, open_statements: dict[int, str]) -> int | None:
    """id открытой гипотезы, которую новая формулировка повторяет, либо None."""
    import math

    docs = {hid: _hypothesis_stems(text) for hid, text in open_statements.items()}
    new = _hypothesis_stems(statement)
    if not new or not docs:
        return None
    total = len(docs) + 1
    seen: dict[str, int] = {}
    for stems in list(docs.values()) + [new]:
        for stem in stems:
            seen[stem] = seen.get(stem, 0) + 1

    def weights(stems: set[str]) -> dict[str, float]:
        raw = {stem: math.log((total + 1) / (seen.get(stem, 0) + 1)) for stem in stems}
        norm = math.sqrt(sum(value * value for value in raw.values())) or 1.0
        return {stem: value / norm for stem, value in raw.items()}

    new_vec = weights(new)
    best_id, best = None, 0.0
    for hid, stems in docs.items():
        vec = weights(stems)
        score = sum(value * vec.get(stem, 0.0) for stem, value in new_vec.items())
        if score > best:
            best_id, best = hid, score
    return best_id if best >= SIMILAR_HYPOTHESIS_THRESHOLD else None


async def _open_hypotheses() -> list[dict]:
    """Открытые гипотезы для контекста модели, свежие первыми (id нужен для пересмотра)."""
    async with analytics_session() as db:
        rows = (await db.execute(
            select(Hypothesis).where(Hypothesis.verdict.is_(None))
            .order_by(Hypothesis.updated_at.desc(), Hypothesis.id.desc()).limit(OPEN_HYPOTHESES_IN_CONTEXT)
        )).scalars().all()
    return [
        {"id": h.id, "statement": (h.statement or "")[:OPEN_HYPOTHESIS_CONTEXT_CHARS]}
        for h in rows
    ]


# 14.11.2026: открытых гипотез 266, а лимит 5 изменений в день не даёт их расчищать. Закрытие существующей гипотезы
# вердиктом со ссылкой на запись контекста проекта ([id] из pulse_context.yaml или [заметка N]) считается отдельно.
MAX_HYPOTHESIS_CHANGES = 5
MAX_CONTEXT_CLOSURES = 15
_CONTEXT_REF_RE = re.compile(r"\[([a-z0-9-]+|заметка \d+)\]")


def _context_ids() -> set[str]:
    try:
        from app.services import pulse_context

        return {e.id for e in pulse_context.load_entries()}
    except Exception:  # noqa: BLE001
        return set()


def is_context_closure(upd: dict, context_ids: set[str]) -> bool:
    """Закрытие существующей гипотезы вердиктом со ссылкой на запись контекста проекта."""
    if not isinstance(upd, dict) or upd.get("id") is None or not isinstance(upd.get("verdict"), bool):
        return False
    refs = _CONTEXT_REF_RE.findall(str(upd.get("rationale") or ""))
    return any(r in context_ids or r.startswith("заметка ") for r in refs)


def select_hypothesis_updates(updates: list, context_ids: set[str]) -> list[dict]:
    """До MAX_HYPOTHESIS_CHANGES обычных изменений и отдельно до MAX_CONTEXT_CLOSURES закрытий по контексту."""
    regular, closures = [], []
    for upd in updates or []:
        if not isinstance(upd, dict):
            continue
        if is_context_closure(upd, context_ids):
            if len(closures) < MAX_CONTEXT_CLOSURES:
                closures.append(upd)
        elif len(regular) < MAX_HYPOTHESIS_CHANGES:
            regular.append(upd)
    return regular + closures


async def _apply_hypothesis_updates(updates: list[dict]) -> int:
    """Изменения гипотез от LLM → таблица hypotheses. Возвращает число применённых."""
    applied = 0
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    open_statements: dict[int, str] | None = None
    async with analytics_session() as db:
        for upd in select_hypothesis_updates(updates, _context_ids()):
            if not isinstance(upd, dict) or not str(upd.get("statement") or "").strip():
                continue
            verdict = upd.get("verdict")
            if verdict is not None and not isinstance(verdict, bool):
                verdict = None
            confidence = upd.get("confidence")
            try:
                confidence = max(0.0, min(1.0, float(confidence))) if confidence is not None else None
            except (TypeError, ValueError):
                confidence = None
            h = None
            if upd.get("id") is not None:
                try:
                    h = await db.get(Hypothesis, int(upd["id"]))
                except (TypeError, ValueError):
                    h = None
            if h is None:
                # Новая запись, повторяющая открытую, обновляет её: слой знаний не должен расти повторами.
                if open_statements is None:
                    open_statements = {
                        row.id: row.statement
                        for row in (await db.execute(
                            select(Hypothesis).where(Hypothesis.verdict.is_(None))
                        )).scalars()
                    }
                same = similar_open_hypothesis(str(upd["statement"]), open_statements)
                h = await db.get(Hypothesis, same) if same is not None else None
            if h is None:
                h = Hypothesis(created_at=now)
                db.add(h)
            h.statement = str(upd["statement"])[:500]
            h.rationale = str(upd.get("rationale") or "")[:2000] or None
            h.verdict = verdict
            h.confidence = confidence
            h.updated_at = now
            applied += 1
        await db.commit()
    return applied


def _split_llm_output(content: str) -> tuple[str, list[dict]]:
    """Ответ модели → (текст владельцу, изменения гипотез)."""
    if _HYP_SEPARATOR not in content:
        return content.strip(), []
    text, _, tail = content.partition(_HYP_SEPARATOR)
    updates: list[dict] = []
    match = re.search(r"\[.*\]", tail, flags=re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, list):
                updates = [u for u in parsed if isinstance(u, dict)]
        except ValueError:
            logger.warning("Pulse hypotheses JSON parse failed: %s", tail[:200])
    return text.strip(), updates


def build_llm_user_content(snapshot: dict, memory: list[dict], hypotheses: list[dict],
                           context: str = "") -> str:
    """Текст пользовательского сообщения для модели.

    152-ФЗ (круг 11): всё, что уходит в OpenRouter через зарубежный прокси, проходит
    очистку: без имён и почт новых пользователей, без почт и телефонов в строках
    поиска, копирования и фраз. Чистая функция (проверяется тестом без сети).
    14.11.2026: первым идёт «Контекст проекта» (`pulse_context.build_block`, уже очищен).
    """
    head = f"Контекст проекта:\n{context}\n\n" if context else ""
    return (
        head
        + "Память за прошлые дни (старые → новые):\n"
        + json.dumps(sanitize_memory_for_llm(memory), ensure_ascii=False)
        + "\n\nСнапшот за отчётный день:\n"
        + json.dumps(sanitize_snapshot_for_llm(snapshot), ensure_ascii=False)
        + "\n\nОткрытые гипотезы (hypotheses):\n"
        + json.dumps(scrub_value(hypotheses), ensure_ascii=False)
    )


# 14.11.2026: Пульс ушёл без аналитика - OpenRouter ответил 402 «You requested up to 65536 tokens, but can only afford
# 36268»: без max_tokens сервис резервирует весь возможный ответ модели, и при остатке на счёте меньше этого резерва
# запрос отклоняется, хотя на сам отчёт денег хватает. Лимит в обычной работе по-прежнему не ставим (директива
# 2026-07-05); только при таком отказе повторяем один раз с max_tokens по остатку, если остаток не меньше
# _MIN_AFFORDABLE_TOKENS (отчёт с гипотезами занимает несколько тысяч токенов). Причину сбоя пишем в шапку отчёта.
_AFFORD_RE = re.compile(r"can only afford (\d+)")
_MIN_AFFORDABLE_TOKENS = 6000
_AFFORD_MARGIN_TOKENS = 512
_last_llm_failure: str | None = None


def llm_failure_note() -> str:
    """Причина последнего сбоя аналитика для шапки отчёта, простыми словами."""
    if _last_llm_failure == "credits":
        return ("LLM-аналитик недоступен: на счёте OpenRouter почти нет денег — пополнить на "
                "openrouter.ai/settings/credits")
    return "LLM-аналитик недоступен"


async def _llm_summary(snapshot: dict, memory: list[dict]) -> str | None:
    """Сводка дня через OpenRouter (+ ведение гипотез). None при сбое —
    отчёт уйдёт без LLM."""
    global _last_llm_failure
    _last_llm_failure = None
    if not settings.openrouter_api_key:
        return None
    hypotheses = await _open_hypotheses()
    try:
        from app.services import pulse_context

        from app.database import async_session

        async with async_session() as db:
            notes = await pulse_context.active_notes(db, today_msk())
        context = pulse_context.build_block(today_msk(), balance=await pulse_context.openrouter_balance(), notes=notes)
    except Exception:  # noqa: BLE001 - без контекста отчёт всё равно уходит
        logger.warning("Pulse context build failed", exc_info=True)
        context = ""
    payload = {
        # Без max_tokens: модель отвечает сколько нужно (директива владельца
        # 2026-07-05 «освободи его»; подтверждено 2026-08-04 — лимит не ставить).
        # История: лимит 1400 обрывал ответ по длине, Bedrock отдавал
        # content=null → отчёт молча уходил в fallback, а блок ---HYPOTHESES---
        # (и апсерт гипотез) не доходил до БД.
        "model": settings.openrouter_model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": build_llm_user_content(snapshot, memory, hypotheses, context),
            },
        ],
    }
    try:
        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "HTTP-Referer": "https://forecasteconomy.com",
            "X-Title": "Forecast Economy Pulse",
        }
        async with httpx.AsyncClient(
            timeout=90, proxy=settings.openrouter_proxy_url or None
        ) as client:
            resp = await client.post(_OPENROUTER_URL, json=payload, headers=headers)
            if resp.status_code == 402:
                m = _AFFORD_RE.search(resp.text)
                affordable = int(m.group(1)) - _AFFORD_MARGIN_TOKENS if m else 0
                if affordable >= _MIN_AFFORDABLE_TOKENS:
                    logger.warning("OpenRouter 402: retry with max_tokens=%d (balance is low)", affordable)
                    resp = await client.post(
                        _OPENROUTER_URL, json={**payload, "max_tokens": affordable}, headers=headers)
                if resp.status_code == 402:
                    _last_llm_failure = "credits"
        if resp.status_code != 200:
            logger.warning("OpenRouter HTTP %d: %s", resp.status_code, resp.text[:300])
            return None
        data = resp.json()
        choice = (data.get("choices") or [{}])[0]
        finish = choice.get("finish_reason")
        # content может прийти None (обрыв по длине у Bedrock) — не роняем отчёт.
        content = (choice.get("message") or {}).get("content")
        content = (content or "").strip()
        if not content:
            logger.warning("OpenRouter empty content (finish=%s)", finish)
            return None
        text, updates = _split_llm_output(content)
        if updates:
            try:
                n = await _apply_hypothesis_updates(updates)
                logger.info("Pulse hypotheses: %s updates applied", n)
            except Exception:
                logger.warning("Pulse hypotheses apply failed", exc_info=True)
        return text or None
    except Exception:
        logger.warning("OpenRouter call failed", exc_info=True)
        return None


def _acquisition_lines(snapshot: dict) -> list[str]:
    acq = snapshot.get("acquisition") or {}
    metrics = pulse.acquisition_metrics(acq)
    lines = []
    for label, key in (("Платное привлечение", "metrika_ad_visits"),
                       ("Органический поиск", "metrika_organic_visits")):
        value = metrics[key]
        lines.append(f"{label}: {value} визитов (Метрика)" if value is not None
                     else f"{label}: нет данных за отчётный день")
    rows = metrics["metrika_campaign_rows"]
    if rows is not None:
        visits = metrics["metrika_campaign_visits"]
        visits_text = visits if visits is not None else "нет данных"
        lines.append(f"UTM-кампании: строк отчёта {rows}, "
                     f"визитов {visits_text}; "
                     "число активных кампаний неизвестно")
    metadata = acq.get("metadata") or {}
    labels = {"traffic_sources": "Источники Метрики", "ad_campaigns": "UTM-отчёт"}
    states = {"missing": "нет данных", "failed": "сбой синхронизации",
              "stale": "устаревшие данные", "invalid": "непригодный ответ"}
    for report_type, label in labels.items():
        info = (metadata.get("reports") or {}).get(report_type) or {}
        if info.get("status") in states:
            suffix = f"; последний день {info['date_to']}" if info.get("date_to") else ""
            lines.append(f"{label}: {states[info['status']]}{suffix}")
        if info.get("sampled"):
            lines.append(f"{label}: выборочные данные")
        if (info.get("total_rows") is not None and info.get("returned_rows") is not None
                and info["total_rows"] > info["returned_rows"]):
            lines.append(f"{label}: неполная выборка, строк {info['returned_rows']} "
                         f"из {info['total_rows']}; суммы только по полученным строкам")
    if (metadata.get("sync") or {}).get("status") == "failed":
        lines.append("Метрика: последний запуск — сбой синхронизации; "
                     "сохранённые числа не подтверждают успешное обновление")
    if acq.get("refresh_error"):
        lines.append("Метрика: не удалось обновить данные из хранилища; "
                     "использован сохранённый снимок")
    partner = (snapshot.get("marts") or {}).get("partner_revenue") or {}
    day = next((row for row in partner.get("days", [])
                if row.get("day") == snapshot.get("date")), None)
    if day is not None and day.get("revenue_rub") is not None:
        lines.append(f"Доход РСЯ за отчётный день: {day['revenue_rub']} руб. "
                     "(доход площадки, не расходы на привлечение)")
    else:
        lines.append("Доход РСЯ: нет данных за отчётный день")
    return lines


def _fallback_summary(snapshot: dict) -> str:
    """Детерминированная сводка, если LLM недоступен."""
    u = snapshot.get("users", {})
    ev = snapshot.get("events", {})
    etl = snapshot.get("etl", {})
    aud = snapshot.get("audience", {})
    by_aud = ev.get("by_audience", {})
    dl_aud = ev.get("downloads_by_audience", {})
    lines = [
        f"👤 Пользователи: всего {u.get('total', 0)}, новых {u.get('new', 0)}",
        f"🫂 Активны за день: зарег. {aud.get('authed_active', 0)}, "
        f"гостей {aud.get('guest_sessions', 0)}",
        f"⚡ Событий: {ev.get('total', 0)} "
        f"(зарег. {by_aud.get('authed', 0)} / гости {by_aud.get('guest', 0)})",
        f"📥 Скачиваний: {sum(ev.get('downloads', {}).values())} "
        f"(зарег. {dl_aud.get('authed', 0)} / гости {dl_aud.get('guest', 0)})",
        f"🛑 Ошибок фронта: {sum(ev.get('errors', {}).values())}",
        _etl_line(etl),
        f"➕ Новых точек данных: {snapshot.get('data', {}).get('new_points', 0)}",
    ]
    try:
        from app.services import pulse_context

        n_ctx = pulse_context.count_active(today_msk())
        if n_ctx:
            lines.append(f"🧭 Контекст проекта: действующих событий и решений {n_ctx} (app/data/pulse_context.yaml)")
    except Exception:  # noqa: BLE001
        pass
    lines.extend(escape(line) for line in _acquisition_lines(snapshot))
    return "\n".join(lines)


def _etl_line(etl: dict) -> str:
    """ETL дня: наши ошибки отдельно от недоступности источника (14.11.2026: было «упавших 20» = обрезанный список)."""
    total = etl.get("failed_indicators", len(etl.get("failed_indicator_ids", [])))
    down = etl.get("source_unavailable_indicators", 0)
    own = etl.get("failed_own_indicators", max(total - down, 0))
    if down:
        return f"🏭 ETL: наших ошибок {own}, источник недоступен у {down} рядов (догрузятся сами)"
    return f"🏭 Упавших ETL-индикаторов: {total}"


def _raw_digits_block(snapshot: dict) -> str:
    """Сырые цифры дня в expandable blockquote (новое оформление Bot API 7.10)."""
    ev = snapshot.get("events", {})
    parts: list[str] = []
    aud = snapshot.get("audience", {})
    by_aud = ev.get("by_audience", {})
    dl_aud = ev.get("downloads_by_audience", {})
    parts.append(
        "Аудитория: зарег. активных "
        f"{aud.get('authed_active', 0)}, гостевых сессий {aud.get('guest_sessions', 0)}; "
        f"события зарег/гость {by_aud.get('authed', 0)}/{by_aud.get('guest', 0)}; "
        f"скачивания зарег/гость {dl_aud.get('authed', 0)}/{dl_aud.get('guest', 0)}"
    )
    if ev.get("by_name"):
        top = ", ".join(f"{k}: {v}" for k, v in list(ev["by_name"].items())[:15])
        parts.append(f"События: {escape(top)}")
    if ev.get("wall_hits"):
        top = ", ".join(f"{k}: {v}" for k, v in ev["wall_hits"].items())
        parts.append(f"Упоры в лимит гостя: {escape(top)}")
    if ev.get("top_indicators"):
        top = ", ".join(f"{k} ×{v}" for k, v in ev["top_indicators"].items())
        parts.append(f"Индикаторы: {escape(top)}")
    if ev.get("top_regions"):
        top = ", ".join(f"{k} ×{v}" for k, v in ev["top_regions"].items())
        parts.append(f"Регионы: {escape(top)}")
    if ev.get("search_top"):
        top = ", ".join(f"«{k}» ×{v}" for k, v in ev["search_top"].items())
        parts.append(f"Поиск: {escape(top)}")
    if ev.get("search_zero_results"):
        top = ", ".join(f"«{k}»" for k in ev["search_zero_results"])
        parts.append(f"Поиск без результатов: {escape(top)}")
    auth = snapshot.get("auth", {})
    if auth:
        parts.append("Auth: " + escape(", ".join(f"{k}: {v}" for k, v in auth.items())))
    acq = snapshot.get("acquisition", {})
    if acq.get("traffic_sources"):
        top = ", ".join(
            f"{name}: {row['visits'] if row.get('visits') is not None else 'нет данных'}"
            for name, row in sorted(acq["traffic_sources"].items(),
                                    key=lambda kv: -(kv[1].get("visits") or 0))
        )
        parts.append(f"Источники (Метрика): {escape(top)}")
    parts.extend(escape(line) for line in _acquisition_lines(snapshot))
    try:
        from app.services import pulse_extra

        parts.extend(escape(line) for line in pulse_extra.digits_lines(snapshot))
    except Exception:  # noqa: BLE001 — новые строки не должны ронять отчёт
        logger.warning("Pulse extra digits failed", exc_info=True)
    if acq.get("search_phrases_top"):
        top = ", ".join(
            f"«{p['phrase'][:40]}» ×{p['visits']}" for p in acq["search_phrases_top"][:10]
        )
        parts.append(f"Фразы из поиска: {escape(top)}")
    if not parts:
        return ""
    return "<blockquote expandable>" + "\n".join(parts) + "</blockquote>"


async def send_pulse_report(report_date: date | None = None) -> bool:
    """Собрать (или взять готовый) снапшот дня, прогнать через LLM, отправить в ТГ."""
    if not (settings.telegram_bot_token and settings.pulse_chat_id):
        logger.info("Pulse report skipped: telegram not configured")
        return False

    d = report_date or (today_msk() - timedelta(days=1))
    snapshot = await pulse.get_or_build_snapshot(d)
    # Привлечение обновляем на момент отчёта: снапшот фиксируется в 23:57,
    # а синк Метрики за этот день отрабатывает только утром (08:20).
    try:
        acquisition = await pulse.build_acquisition(d)
        snapshot["acquisition"] = acquisition
        await pulse.store_snapshot(snapshot)
    except Exception:
        logger.warning("Pulse acquisition refresh failed", exc_info=True)
        snapshot["acquisition"] = {**(snapshot.get("acquisition") or {}), "refresh_error": True}
    memory = await pulse.load_memory(days=7, before=d)

    summary = await _llm_summary(snapshot, memory)
    # Н-22: fallback без пометки маскировал недоступность LLM — владелец
    # читал детерминированную сводку, думая, что это аналитик (и гипотезы
    # молча не обновлялись).
    body = sanitize_llm_html(summary) if summary else (
        f"⚠️ <i>{escape(llm_failure_note())} — детерминированная сводка без гипотез.</i>\n\n"
        + _fallback_summary(snapshot)
    )

    msg_parts = [f"🛰 <b>Пульс платформы — {d.isoformat()}</b>", "", body]
    raw = _raw_digits_block(snapshot)
    if raw:
        msg_parts += ["", raw]
    text = "\n".join(msg_parts)

    # Пульс — всем получателям дайджеста (владелец + skrakan, указание 2026-07-06);
    # pulse_chat_id остаётся в списке через digest_recipients ∪ {pulse_chat_id}.
    recipients = {str(settings.pulse_chat_id)} if settings.pulse_chat_id else set()
    recipients |= set(digest_recipients())
    results = {}
    for cid in sorted(recipients):
        results[cid] = await send_message(
            cid, text, reply_markup=main_menu_keyboard(), kind="pulse_digest"
        )
    ok = any(results.values())
    # память дня пишем даже при сбое отправки — снапшот уже посчитан
    await pulse.store_memory(d, pulse.memory_core(snapshot), summary or _fallback_summary(snapshot))
    return ok


async def pulse_snapshot_job() -> None:
    """Ежедневная фиксация снапшота (23:57 МСК) — чтобы день не потерялся.

    E2 (круг 11): снимок 23:57 не видит последние минуты суток и помечен
    `complete=false`; отчёт 09:05 пересоберёт его по полному МСК-окну
    (`pulse.get_or_build_snapshot`), так что вечерняя часть не теряется.

    Н-21: исключение НЕ глотаем — прокидываем в APScheduler, чтобы сработал
    scheduler-listener (Н-2) и владелец получил алерт, а не молча потерял день.
    """
    snap = await pulse.build_snapshot(today_msk())
    await pulse.store_snapshot(snap)
    logger.info("Pulse snapshot stored for %s", snap["date"])


async def pulse_report_job() -> None:
    """Ежедневный LLM-отчёт за вчера (09:05 МСК).

    Н-21: сбой прокидывается в scheduler-listener (Н-2) → Telegram-алерт.
    Недоступность LLM сюда не попадает — она обработана fallback'ом внутри.
    """
    await send_pulse_report()
