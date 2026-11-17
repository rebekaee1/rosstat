"""Кандидаты в блоки, отбор и сборка персонального выпуска (ADR-0033).

Порядок письма: строка выпуска, тема, заголовок и вступление редакции; «Число недели» редакции;
раздел «Для вас» (личные блоки, при уровне «много» — ещё таблица «Ваши показатели»); оставшиеся
блоки редакции без дублей; календарь (редакция + выходы данных по его рядам); кнопка, финал, подпись.

Отбор: балл = интерес профиля × новизна значения × (усталость уже в профиле); не больше одного
блока на тему и двух от одного генератора; тот же факт (ряд и дата значения), уже показанный
человеку, не повторяется; доля блоков редакции — не меньше трети при уровне «много», не меньше
половины при «мало» (решение 15.11.2026); при «нет данных» — выпуск редакции целиком.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from app.services import freshness
from app.services.newsletter_personal import texts as T
from app.services.newsletter_personal.facts import Fact, FactCache, _is_share_unit, day_label, full_date, number, with_unit
from app.services.newsletter_personal.profile import Profile
from app.services.newsletter_personal.signals import UserSignals
from app.services.newsletter_personal.subjects import parse_key, topic_label

# Сигнал → причина блока (что сказать читателю). Порядок — сила причины.
REASON_ORDER = ("watch", "favorite", "export", "download", "download_limit", "search_select", "search_query",
                "mail_click", "saved_compare", "compare", "forecast_view", "view", "related_click",
                "landing_gate", "landing", "tile_click")
REASON_WHY = {
    "watch": "why.watch", "favorite": "why.favorite", "saved_compare": "why.favorite", "export": "why.download",
    "download": "why.download", "download_limit": "why.download", "search_select": "why.search",
    "search_query": "why.search", "mail_click": "why.mail_click", "compare": "why.view",
    "forecast_view": "why.view", "view": "why.view", "related_click": "why.view", "landing": "why.view",
    "landing_gate": "why.download", "tile_click": "why.view",
}
REASON_KICKER = {
    "watch": "kicker.watch", "favorite": "kicker.favorite", "saved_compare": "kicker.favorite",
    "export": "kicker.download", "download": "kicker.download", "download_limit": "kicker.download",
    "landing_gate": "kicker.download", "search_select": "kicker.search", "search_query": "kicker.search",
}
SHOWCASE_THEME_TOPIC = {"inflation": "prices", "gdp": "gdp", "unemployment": "labor", "rates": "rates", "wages": "wages"}
TOPIC_SHOWCASE_THEME = {"prices": "inflation", "fuel": "inflation", "gdp": "gdp", "business": "gdp",
                        "labor": "unemployment", "wages": "wages", "rates": "rates", "housing": "rates"}
# Региональный показатель по теме (если человек сам смотрел регион, а ряда темы у него нет).
REGION_TOPIC_CODE = {
    # Без «цены → бензин» (16.11.2026): человек, читавший инфляцию, бензин региона не смотрел.
    "fuel": "ceni-ai95",
    "wages": "srednemesyachnaya-nominalnaya-nachislennaya-zarabotnaya-plata-rabotnikov-organizatsiy",
}
LIMITS = {
    # уровень: (личных блоков, таблица, минимальная доля редакции)
    "rich": (4, True, 1 / 3),
    "light": (3, False, 1 / 2),
    "cold": (0, False, 1.0),
}
MAX_CONTENT_BLOCKS = 8
# Три, а не два (16.11.2026): у человека, который смотрел только данные регионов, все кандидаты
# одного вида, и при пределе «два» третий и четвёртый личные блоки оставались пустыми.
MAX_PER_GEN = 3
MAX_TABLE_ROWS = 5
MAX_CAL_ENTRIES = 6


@dataclass
class Candidate:
    gen: str
    subject: str | None
    block: dict
    score: float
    topic: str | None = None
    as_of: str | None = None
    why: str = ""
    extra: dict = field(default_factory=dict)


@dataclass
class Context:
    profile: Profile
    us: UserSignals
    cache: FactCache
    locale: str
    today: date
    issue_key: str
    showcase: list[dict]
    related: dict[str, list[str]]
    query_map: dict[str, str]
    dormant: bool = False

    @property
    def shown_facts(self) -> set[tuple[str, str]]:
        out = set()
        for h in self.us.history:
            for m in h.get("blocks_meta") or []:
                if m.get("subject") and m.get("as_of") and m.get("origin") == "personal":
                    out.add((m["subject"], m["as_of"]))
        return out

    def last_shown_as_of(self, key: str) -> str | None:
        best = None
        for h in self.us.history:
            for m in h.get("blocks_meta") or []:
                if m.get("subject") == key and m.get("as_of") and (best is None or m["as_of"] > best):
                    best = m["as_of"]
        return best


def _reason(us: UserSignals, key: str) -> str:
    kinds = {s.kind for s in us.signals if s.subject.key == key}
    for r in REASON_ORDER:
        if r in kinds:
            return r
    return "view"


def _last_signal(us: UserSignals, key: str, kinds: tuple[str, ...]) -> datetime | None:
    ats = [s.at for s in us.signals if s.subject.key == key and s.kind in kinds]
    return max(ats) if ats else None


def _news_factor(ctx: Context, fact: Fact) -> float:
    last = ctx.last_shown_as_of(fact.key)
    if last is not None:
        return 1.0 if fact.as_of.isoformat() > last else 0.0
    level = freshness.freshness_level(fact.as_of, fact.frequency, ctx.today)
    return {"fresh": 1.0, "aging": 0.45}.get(level or "", 0.0)


def _story(fact: Fact, ctx: Context, *, kicker: str, why: str, text: str | None = None,
           delta_in_text: bool = False) -> dict:
    loc = ctx.locale
    body = text if text is not None else T.sentence(
        fact.period, T.t(loc, "compare.text", value=fact.compare["value_text"]) if fact.compare else "")
    block = {
        "type": "story", "kicker": kicker, "title": T.clean_title(fact.title), "value": fact.value_text,
        "text": T.typo(body, loc), "source": fact.source, "as_of": fact.as_of.isoformat(),
        "url": fact.path, "why": why,
    }
    # Изменение — отдельной строкой блока со стрелкой (правила письма, глава «Анатомия блока»).
    if fact.change_text and not delta_in_text:
        block["delta"] = T.typo(T.cap(fact.change_text), loc)
        block["delta_dir"] = fact.change_dir
    # Мини-график: последние значения самого ряда (у рядов «за год» точки — базовый индекс, не рисуем).
    if not fact.headline_yoy and len(fact.points) >= 4:
        block["spark"] = [round(v, 4) for _d, v in fact.points[-8:]]
    return block


async def series_candidates(ctx: Context) -> list[Candidate]:
    out: list[Candidate] = []
    shown = ctx.shown_facts
    for item in ctx.profile.series()[:14]:
        key = item["key"]
        fact = await ctx.cache.get(key)
        if fact is None or fact.stale or (key, fact.as_of.isoformat()) in shown:
            continue
        news = _news_factor(ctx, fact)
        reason = _reason(ctx.us, key)
        gen = "series"
        why = T.t(ctx.locale, REASON_WHY.get(reason, "why.view"))
        kicker = T.t(ctx.locale, REASON_KICKER.get(reason, "kicker.view"))
        text = None
        if fact.kind == "r":
            gen, kicker, why = "region", T.t(ctx.locale, "kicker.region"), T.t(ctx.locale, "why.region")
        elif reason in ("download", "export", "download_limit", "landing_gate"):
            downloaded = _last_signal(ctx.us, key, ("download", "export", "download_limit", "landing_gate"))
            if downloaded and fact.as_of > downloaded.date():
                gen = "download"
                text = T.sentence(T.t(ctx.locale, "download.text", day=full_date(downloaded.date(), ctx.locale),
                                      period_cap=T.cap(fact.period)))
                news = max(news, 0.9)
        elif reason in ("search_select", "search_query"):
            gen = "search"
        if ctx.dormant and ctx.us.last_visit:
            then = fact.value_on_or_before(ctx.us.last_visit.date())
            if then and then[0] < fact.as_of and then[1] != fact.value:
                gen, kicker, why = "since", T.t(ctx.locale, "kicker.since"), T.t(ctx.locale, "why.since")
                then_text = with_unit(number(then[1], ctx.locale), fact.unit, ctx.locale) if not fact.headline_yoy else None
                if then_text:
                    from app.services.display import value_period_phrase

                    text = T.sentence(T.t(ctx.locale, "since.text",
                                          then_period=T.cap(value_period_phrase(then[0], fact.frequency, locale=ctx.locale)),
                                          then=then_text, now=fact.value_text, period=fact.period))
                    news = 1.0
        if news <= 0:
            continue
        score = float(item["score"]) * news
        block = _story(fact, ctx, kicker=kicker, why=why, text=text)
        out.append(Candidate(gen=gen, subject=key, block=block, score=score, topic=fact.topic,
                             as_of=fact.as_of.isoformat(), why=reason,
                             extra={"change": fact.change_text, "value": fact.value_text, "title": fact.title,
                                    "change_dir": fact.change_dir, "fact": fact}))
    return out


async def region_candidates(ctx: Context, taken: set[str]) -> list[Candidate]:
    region = (ctx.profile.geo or {}).get("region")
    if not region:
        return []
    keys = []
    for item in ctx.profile.subjects:
        sub = parse_key(item["key"])
        if sub is not None and sub.kind == "ri":
            keys.append((f"r:{region}:{sub.code}", item["score"]))
    for topic in ctx.profile.top_topics(3):
        code = REGION_TOPIC_CODE.get(topic)
        if code and region != "russia":   # «регион Россия» по теме — дубль общероссийского ряда
            keys.append((f"r:{region}:{code}", ctx.profile.topics.get(topic, 0) * 0.6))
    # Без догадки по умолчанию (16.11.2026): раньше сюда вставал бензин региона, даже если человек
    # смотрел демографию. Его собственные ряды региона приходят из `series_candidates`.
    out = []
    shown = ctx.shown_facts
    for key, base in keys:
        if key in taken:
            continue
        fact = await ctx.cache.get(key)
        if fact is None or fact.stale or (key, fact.as_of.isoformat()) in shown:
            continue
        news = _news_factor(ctx, fact)
        if news <= 0:
            continue
        block = _story(fact, ctx, kicker=T.t(ctx.locale, "kicker.region"), why=T.t(ctx.locale, "why.region"))
        out.append(Candidate(gen="region", subject=key, block=block, score=max(base, 0.5) * news, topic=fact.topic,
                             as_of=fact.as_of.isoformat(), why="region",
                             extra={"change": fact.change_text, "value": fact.value_text, "title": fact.title,
                                    "fact": fact}))
        taken.add(key)
    return out


async def related_candidates(ctx: Context, taken: set[str]) -> list[Candidate]:
    out = []
    shown = ctx.shown_facts
    mine = {s["key"] for s in ctx.profile.subjects}
    for item in ctx.profile.series()[:3]:
        for rel in ctx.related.get(item["key"], []):
            if rel in mine or rel in taken:
                continue
            fact = await ctx.cache.get(rel)
            if fact is None or fact.stale or (rel, fact.as_of.isoformat()) in shown:
                continue
            news = _news_factor(ctx, fact)
            if news <= 0:
                continue
            block = _story(fact, ctx, kicker=T.t(ctx.locale, "kicker.related"), why=T.t(ctx.locale, "why.related"))
            out.append(Candidate(gen="related", subject=rel, block=block, score=float(item["score"]) * 0.5 * news,
                                 topic=fact.topic, as_of=fact.as_of.isoformat(), why="related",
                                 extra={"change": fact.change_text, "value": fact.value_text, "title": fact.title,
                                        "fact": fact}))
            taken.add(rel)
            break
    return out


async def gap_candidates(ctx: Context, taken: set[str]) -> list[Candidate]:
    out = []
    for h in dict.fromkeys(ctx.us.gaps):
        key = ctx.query_map.get(h)
        if not key or key in taken:
            continue
        fact = await ctx.cache.get(key)
        if fact is None or fact.stale or ctx.last_shown_as_of(key):
            continue
        block = _story(fact, ctx, kicker=T.t(ctx.locale, "kicker.now"), why=T.t(ctx.locale, "why.now"),
                       text=T.sentence(fact.period, T.t(ctx.locale, "now.text")))
        out.append(Candidate(gen="now", subject=key, block=block, score=1.2, topic=fact.topic,
                             as_of=fact.as_of.isoformat(), why="gap", extra={"fact": fact}))
        taken.add(key)
        if len(out) >= 1:
            break
    return out


def _forecast_period(day: date, frequency: str, locale: str) -> str:
    from app.services.display import value_period_phrase

    phrase = value_period_phrase(day, frequency, locale=locale)
    return phrase.replace("за ", "", 1) if locale != "en" else phrase.replace("for ", "", 1)


def _fmt_forecast_value(item: dict, value: float, locale: str) -> str:
    unit = (item.get("unit") or "").strip()
    # До двух знаков, без хвостовых нулей — как число того же ряда в других блоках письма.
    num = number(round(value, 2) if abs(value) < 1000 else round(value), locale)
    if unit.startswith("%"):
        return with_unit(num, "%", locale)
    return with_unit(num, unit, locale)


# Прогноз «по теме» (человек не открывал сам прогноз) не должен вытеснять ряды, которые он смотрел:
# вес темы — сумма по всем её рядам, поэтому без множителя прогноз всегда вставал первым.
TOPIC_FORECAST_FACTOR = 0.35


def skip_forecasts() -> frozenset[str]:
    """Прогнозы витрины, которые редакция не ставит в письма (`RUSTATS_NEWSLETTER_PERSONAL_SKIP_FORECASTS`)."""
    from app.config import settings

    raw = getattr(settings, "newsletter_personal_skip_forecasts", "") or ""
    return frozenset(x.strip() for x in raw.split(",") if x.strip())


def forecast_candidates(ctx: Context, editorial_forecast_ids: set[str]) -> list[Candidate]:
    if not ctx.showcase:
        return []
    country = (ctx.profile.geo or {}).get("country") or "russia"
    want = {code for code in (s.subject.code for s in ctx.us.signals if s.kind == "forecast_view")}
    out = []
    for item in ctx.showcase:
        if item.get("id") in editorial_forecast_ids or item.get("id") in skip_forecasts():
            continue
        topic = SHOWCASE_THEME_TOPIC.get(item.get("theme"))
        tscore = max(ctx.profile.topics.get(topic or "", 0.0),
                     *(ctx.profile.topics.get(t, 0.0) for t, th in TOPIC_SHOWCASE_THEME.items() if th == item.get("theme")))
        slug = (item.get("country") or {}).get("slug")
        if slug != country and not (slug == "russia" and country == "russia"):
            tscore *= 0.4
        code = (item.get("path") or "").rstrip("/").rsplit("/", 1)[-1]
        viewed = code in want
        if viewed:
            tscore += 1.0
        if tscore <= 0.3:
            continue
        end = item["forecast_end"]
        last = item["last_actual"]
        end_day, last_day = date.fromisoformat(end["date"]), date.fromisoformat(last["date"])
        freq = item.get("frequency") or "monthly"
        period = _forecast_period(end_day, freq, ctx.locale)
        title = f"{item['title']}, {period}"
        from app.services.display import value_period_phrase

        last_text = f"{_fmt_forecast_value(item, float(last['value']), ctx.locale)} " \
                    f"{value_period_phrase(last_day, freq, locale=ctx.locale)}"
        block = {
            "type": "forecast", "kicker": T.t(ctx.locale, "kicker.forecast"), "title": T.clean_title(title),
            "value": _fmt_forecast_value(item, float(end["value"]), ctx.locale), "target": period,
            "last_actual": T.typo(last_text, ctx.locale), "text": T.t(ctx.locale, "forecast.note"),
            "source": item.get("source") or "", "url": item.get("path") or "",
            "why": (T.t(ctx.locale, "why.forecast") if viewed
                    else T.t(ctx.locale, "why.topic", topic=T.soft_lower(topic_label(topic, ctx.locale))) if topic else ""),
        }
        out.append(Candidate(gen="forecast", subject=f"fc:{item['id']}", block=block, score=tscore * (0.9 if viewed else TOPIC_FORECAST_FACTOR),
                             topic=topic, as_of=last["date"], why="forecast_view" if viewed else "topic",
                             extra={"item_id": item["id"], "target": end["date"], "value": float(end["value"]),
                                    "value_text": block["value"], "period": period}))
    out.sort(key=lambda c: -c.score)
    return out[:1]


def check_candidates(ctx: Context) -> list[Candidate]:
    """«Сверка»: прогноз из прошлого письма человека и вышедший факт за тот же период."""
    if not ctx.showcase:
        return []
    by_id = {it["id"]: it for it in ctx.showcase}
    done = {(m.get("item_id"), m.get("target")) for h in ctx.us.history for m in h.get("blocks_meta") or []
            if m.get("gen") == "check"}
    out = []
    for h in ctx.us.history:
        sent = h.get("built_at")
        for m in h.get("blocks_meta") or []:
            if m.get("gen") != "forecast" or (m.get("item_id"), m.get("target")) in done:
                continue
            item = by_id.get(m.get("item_id"))
            if not item:
                continue
            # Сверка по тому же расчёту: факт витрины за ту же дату, что и прогноз.
            facts = [p for p in item.get("history") or [] if p["date"] == m.get("target")]
            if item["last_actual"]["date"] == m.get("target"):
                facts = [item["last_actual"]]
            if not facts:
                continue
            actual = _fmt_forecast_value(item, float(facts[0]["value"]), ctx.locale)
            sent_text = full_date(sent.date() if isinstance(sent, datetime) else date.fromisoformat(str(sent)[:10]),
                                  ctx.locale)
            text = T.t(ctx.locale, "check.text", sent=sent_text, period=m.get("period") or "",
                       forecast=m.get("value_text") or "", actual=actual)
            block = {"type": "story", "kicker": T.t(ctx.locale, "kicker.check"), "title": T.clean_title(item["title"]),
                     "value": actual, "text": T.typo(text, ctx.locale), "source": item.get("source") or "",
                     "as_of": m.get("target"), "url": item.get("path") or "", "why": T.t(ctx.locale, "why.check")}
            out.append(Candidate(gen="check", subject=f"fc:{item['id']}", block=block, score=3.0,
                                 topic=SHOWCASE_THEME_TOPIC.get(item.get("theme")), as_of=m.get("target"),
                                 why="check", extra={"item_id": item["id"], "target": m.get("target")}))
            done.add((m.get("item_id"), m.get("target")))
    return out[:1]


def pick(cands: list[Candidate], limit: int) -> list[Candidate]:
    """Жадный отбор с разнообразием: тема — один раз, генератор — не больше ``MAX_PER_GEN`` раз."""
    chosen: list[Candidate] = []
    topics: dict[str, int] = {}
    gens: dict[str, int] = {}
    subjects: set[str] = set()
    paths: set[str] = set()
    for strict in (True, False):
        for c in sorted(cands, key=lambda c: (-c.score, c.gen, c.subject or "")):
            if len(chosen) >= limit:
                break
            path = str(c.block.get("url") or "").split("?")[0].rstrip("/")
            # Один показатель — один блок: прогноз и факт той же карточки не идут вместе.
            if c in chosen or (c.subject and c.subject in subjects) or (path and path in paths):
                continue
            if gens.get(c.gen, 0) >= MAX_PER_GEN and c.gen not in ("check",):
                continue
            if strict and c.topic and topics.get(c.topic, 0) >= 1:
                continue
            chosen.append(c)
            subjects.add(c.subject or "")
            if path:
                paths.add(path)
            gens[c.gen] = gens.get(c.gen, 0) + 1
            if c.topic:
                topics[c.topic] = topics.get(c.topic, 0) + 1
    return chosen


def table_block(rest: list[Candidate], locale: str) -> tuple[dict | None, list[Candidate]]:
    rows, used = [], []
    for c in rest:
        if c.gen not in ("series", "search", "download", "region", "related") or "fact" not in c.extra:
            continue
        fact: Fact = c.extra["fact"]
        change = (fact.change_text.split(" за ")[0].split(" over ")[0].split(" (")[0]
                  if fact.change_text and not fact.change_text.startswith(("без", "unchanged")) else "—")
        rows.append([T.clean_title(fact.title, 48), fact.value_text, change])
        used.append(c)
        if len(rows) >= MAX_TABLE_ROWS:
            break
    if len(rows) < 2:
        return None, []
    summary = "; ".join(f"{r[0]} — {r[1]}" + (f" ({r[2]})" if r[2] != "—" else "") for r in rows)
    block = {"type": "table", "kicker": T.t(locale, "kicker.table"), "title": T.t(locale, "table.title"),
             "columns": T.t(locale, "table.cols"), "rows": rows, "text": T.typo(summary + ".", locale),
             "row_urls": [c.extra["fact"].path for c in used],
             "source": ", ".join(dict.fromkeys(c.extra["fact"].source for c in used if c.extra["fact"].source)),
             "why": T.t(locale, "why.view")}
    return block, used


# --- «С вашей регистрации»: личный блок для человека без действий на сайте (17.11.2026) ---------
# Одинаковое письмо редакции всем, о ком нет сигналов, почтовый сервер счёл массовой рассылкой, а
# владелец просил личное письмо каждому. О таком человеке известна дата регистрации — от неё и
# считаем: что было с главными рядами в тот день и что сейчас. Ряды — дневные и недельные, чтобы
# «было» находилось для любой даты; короткие имена — для темы письма.
SIGNUP_SERIES = (   # код, имя по-русски, имя по-английски, единица в таблице (ru, en)
    ("key-rate", "ключевая ставка", "key rate", "%", "%"),
    ("usd-rub", "доллар", "US dollar", "₽", "RUB"),
    ("fuel-ai92", "бензин АИ-92", "AI-92 petrol", "₽/л", "RUB/l"),
    ("imoex", "индекс МосБиржи", "MOEX index", "", ""),
    ("gold-price", "золото", "gold", "₽/г", "RUB/g"),
    ("brent", "нефть Brent", "Brent oil", "$", "USD"),
    ("eur-rub", "евро", "euro", "₽", "RUB"),
    ("cny-rub", "юань", "yuan", "₽", "RUB"),
)
SIGNUP_ALWAYS = 2       # ставка и доллар — всегда, если есть
SIGNUP_ROWS = 4
SIGNUP_MIN_DAYS = 3


def _signup_move(fact: Fact, then: float, locale: str) -> tuple[float, str]:
    """(сила изменения для отбора, подпись изменения): ставки — в п. п., остальное — в процентах."""
    if _is_share_unit(fact.unit):
        delta = round(fact.value - then, 2)
        if not delta:
            return 0.0, ""
        text = number(delta, locale, signed=True, digits=2).rstrip("0").rstrip(",.")
        return abs(delta) * 2.0, f"{text}{T.NBSP}{'pp' if locale == 'en' else 'п. п.'}"
    if then <= 0:
        return 0.0, ""
    pct = (fact.value / then - 1.0) * 100.0
    if abs(pct) > 200 or abs(pct) < 0.05:
        return 0.0, ""
    return abs(pct), with_unit(number(pct, locale, signed=True, digits=1), "%", locale)


def _signup_pair(then: float, now: float, unit: str, locale: str) -> tuple[str, str]:
    """«Было» и «сейчас» с одним числом знаков: тысячи — без копеек, одинаковые хвостовые нули убраны."""
    digits = 0 if max(abs(then), abs(now)) >= 1000 else 2
    a, b = number(then, locale, digits=digits), number(now, locale, digits=digits)
    while digits and a[-1] == "0" and b[-1] == "0":
        a, b, digits = a[:-1], b[:-1], digits - 1
    if unit == "%" and digits:   # ставка: «14,5 % → 14 %», без «14,0»
        a, b = (x.rstrip("0").rstrip(",.") for x in (a, b))
    a, b = a.rstrip(",."), b.rstrip(",.")
    return (with_unit(a, unit, locale), with_unit(b, unit, locale)) if unit else (a, b)


async def signup_block(ctx: Context) -> tuple[dict | None, list[Candidate], dict]:
    """Таблица «было в день регистрации → сейчас» и сведения для темы письма."""
    created = ctx.us.created_at
    if created is None:
        return None, [], {}
    day = (created + timedelta(hours=3)).date()   # время в базе — UTC; день регистрации называем по Москве
    if (ctx.today - day).days < SIGNUP_MIN_DAYS:
        return None, [], {}
    loc = ctx.locale
    found = []
    for pos, (code, ru_name, en_name, ru_unit, en_unit) in enumerate(SIGNUP_SERIES):
        fact = await ctx.cache.get(f"ru:{code}")
        if fact is None or fact.stale:
            continue
        then = await ctx.cache.value_at(fact, day)
        if then is None or then[0] >= fact.as_of:
            continue
        strength, move = _signup_move(fact, then[1], loc)
        then_text, now_text = _signup_pair(then[1], fact.value, en_unit if loc == "en" else ru_unit, loc)
        found.append({"pos": pos, "fact": fact, "then": then, "strength": strength, "move": move,
                      "then_text": then_text, "now_text": now_text, "name": en_name if loc == "en" else ru_name})
    always = [f for f in found if f["pos"] < SIGNUP_ALWAYS]
    rest = sorted((f for f in found if f["pos"] >= SIGNUP_ALWAYS and f["move"]), key=lambda f: -f["strength"])
    picked = always + rest[:max(0, SIGNUP_ROWS - len(always))]
    if len(picked) < 2 or not any(f["move"] for f in picked):
        return None, [], {}
    day_text = day_label(day, loc)
    rows, used, parts = [], [], []
    for f in picked:
        fact: Fact = f["fact"]
        rows.append([T.cap(f["name"]), f["then_text"], f["now_text"]])
        f["part"] = (T.t(loc, "signup.part", name=f["name"], then=f["then_text"], now=f["now_text"]) if f["move"]
                     else T.t(loc, "signup.same", name=f["name"], now=f["now_text"]))
        parts.append(f["part"])
        used.append(Candidate(gen="signup", subject=fact.key, block={}, score=f["strength"], topic=fact.topic,
                              as_of=fact.as_of.isoformat(), why="signup",
                              extra={"fact": fact, "value": f["now_text"], "then": f["then_text"],
                                     "then_as_of": f["then"][0].isoformat(), "then_value": f["then"][1],
                                     "now_value": fact.value}))
    block = {"type": "table", "kicker": T.t(loc, "signup.kicker", day=day_text), "title": T.t(loc, "signup.title"),
             "columns": [T.t(loc, "table.cols")[0], day_text, T.t(loc, "signup.now")], "rows": rows,
             "text": T.typo(T.t(loc, "signup.lead", day=day_text) + " " + "; ".join(parts).rstrip(".") + ".", loc),
             "row_urls": [f["fact"].path for f in picked],
             "source": ", ".join(dict.fromkeys(f["fact"].source for f in picked if f["fact"].source)),
             "why": T.t(loc, "why.signup", date=full_date(day, loc))}
    movers = sorted((f for f in picked if f["move"]), key=lambda f: -f["strength"])
    return block, used, {"day": day_text, "date": full_date(day, loc),
                         "movers": [(f["name"], f["move"]) for f in movers],
                         "first": movers[0]["part"].rstrip(".") if movers else ""}


def editorial_share_ok(n_editorial: int, n_total: int, min_share: float) -> bool:
    return n_total == 0 or n_editorial >= math.ceil(min_share * n_total - 1e-9)
