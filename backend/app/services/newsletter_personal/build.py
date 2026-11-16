"""Сборка персонального выпуска (ADR-0033): сигналы → профиль → блоки → выпуск в формате почты.

Публичный интерфейс:
* ``build_personal_issue(db, user_id, issue)`` → содержимое на языке человека (словарь в формате
  файла выпуска ADR-0032: subject, preheader, title, intro, masthead, blocks, cta_*, outro, signoff,
  personal_note) или ``None``, если у выпуска нет языка человека;
* ``Builder`` — то же пакетом с общими кэшами фактов (запуск по всем подписчикам);
* ``per_recipient_hook(issue)`` — функция для ``mail.campaign.run(per_recipient=…)``: берёт снимок,
  при устаревших числах пересобирает, соблюдает тихие часы и частоту;
* ``build_campaign`` — снимки по всем подписчикам пакетами (задача четверга или команда).

Отказоустойчивость: любая ошибка у человека → честный общий выпуск редакции (`status=fallback`),
ряд без данных или со старыми данными — блок не ставится; без снимка — сборка на лету.
"""
from __future__ import annotations

import asyncio
import copy
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.newsletter_personal import ab, store
from app.services.newsletter_personal import compose as C
from app.services.newsletter_personal import texts as T
from app.services.newsletter_personal.facts import FactCache
from app.services.newsletter_personal.profile import (
    BEHAVIOR, PROFILE_VERSION, Profile, build_profile, explicit_region,
)
from app.services.newsletter_personal.signals import UserSignals, collect
from app.services.newsletter_personal.subjects import parse_key, topic_label

logger = logging.getLogger(__name__)

MSK = timezone(timedelta(hours=3))
ON_THE_FLY_TIMEOUT = 8.0


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _today_msk() -> date:
    return datetime.now(MSK).date()


# --- формат выпуска почты ----------------------------------------------------------

def digest_to_dict(digest) -> dict:
    """Digest (mail/templates) → словарь языка файла выпуска. Старые выпуски (только items) → блоки story."""
    blocks = [dict(b) for b in (digest.blocks or [])]
    if not blocks:
        blocks = [{"type": "story", "title": i.title, "text": i.text, "url": i.url, "value": i.value}
                  for i in digest.items]
    return {
        "subject": digest.subject, "preheader": digest.preheader, "title": digest.title, "intro": digest.intro,
        "masthead": getattr(digest, "masthead", ""), "blocks": blocks, "cta_label": digest.cta_label,
        "cta_url": digest.cta_url, "outro": digest.outro, "signoff": getattr(digest, "signoff", ""),
    }


def section_supported() -> bool:
    from app.services.mail import blocks as mail_blocks

    return "section" in getattr(mail_blocks, "TYPES", ())


def _path(url: str | None) -> str:
    return urlsplit(url or "").path.rstrip("/") if url else ""


def _abs(path_or_url: str, locale: str) -> str:
    if not path_or_url:
        return ""
    if path_or_url.startswith("http"):
        return path_or_url
    from app.services.mail import service

    return service.site_link(locale, path_or_url)


def _utm(url: str, key: str, content: str, token: str | None) -> str:
    from app.services.mail.campaign import with_utm

    out = with_utm(url, key, content)
    if token and out != url:
        sep = "&" if "?" in out else "?"
        out = f"{out}{sep}utm_term={token}"
    return out


# --- проверка блока ----------------------------------------------------------------

def check_block(block: dict, locale: str) -> str | None:
    """Причина отказа или None. Числа берутся из фактов; здесь — форма и правила редакции."""
    from app.services.display import contains_cyrillic
    from app.services.mail import blocks as mail_blocks

    try:
        mail_blocks.validate_block(block)
    except Exception as exc:  # noqa: BLE001
        return f"invalid:{str(exc)[:60]}"
    text_fields = [str(block.get(k) or "") for k in ("kicker", "title", "text", "value", "why", "source",
                                                       "last_actual", "target")]
    for row in block.get("rows") or []:
        text_fields += [str(c) for c in row]
    blob = " ".join(text_fields)
    if block.get("type") in ("story", "forecast", "lead") and not str(block.get("value") or "").strip():
        return "no_value"
    if block.get("type") in ("story", "forecast", "table") and block.get("kicker") != T.t(locale, "kicker.check") \
            and not str(block.get("source") or "").strip():
        return "no_source"
    if locale == "en" and contains_cyrillic(blob):
        return "cyrillic_in_en"
    if T.FORBIDDEN_WORDS.search(blob if block.get("type") == "forecast" else blob.replace("range", "")):
        return "forbidden_words"
    return None


# --- результат -----------------------------------------------------------------------

@dataclass
class BuildResult:
    user_id: str
    locale: str
    status: str                       # built / general / fallback / control / off
    tier: str
    arm: str
    subject_arm: str | None
    payload: dict | None
    blocks_meta: list[dict] = field(default_factory=list)
    data_as_of: date | None = None
    error: str | None = None
    profile: Profile | None = None

    def summary(self) -> dict:
        return {"status": self.status, "tier": self.tier, "arm": self.arm, "subject_arm": self.subject_arm,
                "personal_blocks": sum(1 for m in self.blocks_meta if m.get("origin") == "personal"),
                "error": self.error}


class Builder:
    """Сборка для многих людей с общими кэшами: факты по языку, витрина прогнозов, связанные ряды."""

    def __init__(self, db: AsyncSession, issue, *, today: date | None = None, now: datetime | None = None,
                 behavior: bool | None = None, holdout_pct: int | None = None, subject_ab_pct: int | None = None,
                 dormant: bool | None = None, click_tokens: bool | None = None):
        self.db = db
        self.issue = issue
        self.today = today or _today_msk()
        self.now = now or _utcnow()
        self.behavior = settings.newsletter_personal_behavior_signals if behavior is None else behavior
        self.holdout_pct = holdout_pct
        self.subject_ab_pct = subject_ab_pct
        self.dormant_enabled = settings.newsletter_personal_dormant_enabled if dormant is None else dormant
        self.click_tokens = ab.click_tokens_enabled() if click_tokens is None else click_tokens
        self._caches: dict[str, FactCache] = {}
        self._showcase: dict[str, list[dict]] = {}
        self._query_map: dict[str, str] | None = None

    def cache(self, locale: str) -> FactCache:
        loc = "en" if locale == "en" else "ru"
        if loc not in self._caches:
            self._caches[loc] = FactCache(self.db, loc, self.today)
        return self._caches[loc]

    async def showcase(self, locale: str) -> list[dict]:
        loc = "en" if locale == "en" else "ru"
        if loc not in self._showcase:
            try:
                from app.services.forecast_showcase import build_showcase

                self._showcase[loc] = (await build_showcase(self.db, loc)).get("items") or []
            except Exception as exc:  # noqa: BLE001 — без витрины просто нет блока прогноза
                logger.warning("newsletter: forecast showcase unavailable: %s", type(exc).__name__)
                await self.cache(loc)._recover()
                self._showcase[loc] = []
        return self._showcase[loc]

    async def query_map(self, hashes: list[str]) -> dict[str, str]:
        if not hashes or not await store.tables_ready(self.db):
            return {}
        from app.models import NewsletterQueryMap

        return {h: s for h, s in (await self.db.execute(
            select(NewsletterQueryMap.q_hash, NewsletterQueryMap.subject)
            .where(NewsletterQueryMap.q_hash.in_(hashes)))).all()}

    # --- профиль ---------------------------------------------------------------------

    async def profile_for(self, us: UserSignals, locale: str) -> Profile:
        signals = us.signals if self.behavior else [s for s in us.signals if s.kind not in BEHAVIOR]
        keys = sorted({s.subject.key for s in signals})
        hints = await self.cache("ru").topics(keys)
        fatigue = _fatigue(us)
        region = explicit_region(signals)
        country = us.home_country or ("russia" if (us.country_code or "RU") == "RU" and locale == "ru" else None)
        if not country:
            c_scores: dict[str, float] = {}
            for s in signals:
                if s.subject.kind in ("c", "w") and s.subject.place:
                    c_scores[s.subject.place] = c_scores.get(s.subject.place, 0) + 1
            country = max(c_scores, key=c_scores.get) if c_scores else ("russia" if locale == "ru" else None)
        stats = {"events": us.events if self.behavior else 0, "explicit": us.explicit, "behavior": self.behavior,
                 "last_visit": us.last_visit.date().isoformat() if us.last_visit else None,
                 "signals": len(signals)}
        return build_profile(us.user_id, signals, now=self.now, locale=locale, fatigue=fatigue, topic_hint=hints,
                             geo={"country": country, "region": region,
                                  "region_source": "explicit" if region else None},
                             timezone=us.timezone, stats=stats)

    # --- выпуск ----------------------------------------------------------------------

    async def build(self, us: UserSignals, locale: str) -> BuildResult:
        loc = "en" if locale == "en" else "ru"
        if loc not in self.issue.by_locale:
            return BuildResult(us.user_id, loc, "no_locale", "cold", "personal", None, None)
        base = digest_to_dict(self.issue.by_locale[loc])
        arm = ab.arm(us.user_id, self.holdout_pct)
        try:
            profile = await self.profile_for(us, loc)
        except Exception as exc:  # noqa: BLE001
            logger.warning("newsletter profile failed %s: %s", ab.user_hash(us.user_id), type(exc).__name__)
            await self.cache(loc)._recover()
            return _general(us.user_id, loc, base, "fallback", "cold", arm, error=f"profile:{type(exc).__name__}")
        if us.personal_off:
            return _general(us.user_id, loc, base, "off", profile.tier, arm, profile=profile)
        if arm == "control":
            return _general(us.user_id, loc, base, "control", profile.tier, arm, profile=profile)
        try:
            return await self._compose(us, profile, base, loc, arm)
        except Exception as exc:  # noqa: BLE001 — честный общий выпуск вместо ошибки
            logger.warning("newsletter compose failed %s: %s", ab.user_hash(us.user_id), type(exc).__name__,
                           exc_info=True)
            await self.cache(loc)._recover()
            return _general(us.user_id, loc, base, "fallback", profile.tier, arm, profile=profile,
                            error=f"compose:{type(exc).__name__}")

    async def _compose(self, us: UserSignals, profile: Profile, base: dict, loc: str, arm: str) -> BuildResult:
        key = self.issue.key
        dormant = bool(self.dormant_enabled and us.last_visit
                       and (self.now - us.last_visit).days >= settings.newsletter_personal_dormant_days)
        tier = profile.tier
        if tier == "cold" and not dormant:
            return _general(us.user_id, loc, base, "general", tier, arm, profile=profile)
        series_keys = [s["key"] for s in profile.series()[:5]]
        ctx = C.Context(profile=profile, us=us, cache=self.cache(loc), locale=loc, today=self.today,
                        issue_key=key, showcase=await self.showcase(loc),
                        related=await store.related_for(self.db, series_keys),
                        query_map=await self.query_map(list(dict.fromkeys(us.gaps))) if self.behavior else {},
                        dormant=dormant)
        blocks = base["blocks"]
        lead = blocks[0] if blocks and blocks[0].get("type") == "lead" else None
        calendar = next((b for b in blocks if b.get("type") == "calendar"), None)
        editorial = [b for b in blocks if b is not lead and b is not calendar]
        editorial_fc = {str(b.get("url") or "") for b in editorial if b.get("type") == "forecast"}

        cands: list[C.Candidate] = []
        cands += C.check_candidates(ctx)
        series = await C.series_candidates(ctx)
        cands += series
        taken = {c.subject for c in cands if c.subject}
        cands += await C.region_candidates(ctx, taken)
        cands += await C.related_candidates(ctx, taken)
        if self.behavior:
            cands += await C.gap_candidates(ctx, taken)
        fc_ids = {it["id"] for it in ctx.showcase if _abs(it.get("path") or "", loc).split("?")[0] in
                  {u.split("?")[0] for u in editorial_fc}}
        cands += C.forecast_candidates(ctx, fc_ids)

        # Проверка до отбора: блок, не прошедший правила, в выбор не попадает; ряд, о котором уже
        # пишет редакция в этом выпуске, — тоже (у редакции текст богаче, повтор не нужен).
        editorial_paths = {_path(b.get("url")) for b in blocks if b.get("url") and b.get("type") != "calendar"}
        dropped = []
        ok_cands = []
        for c in cands:
            if c.gen not in ("forecast", "check") and _path(_abs(c.block.get("url") or "", loc)) in editorial_paths:
                dropped.append({"gen": c.gen, "subject": c.subject, "reason": "covered_by_editorial"})
                continue
            reason = check_block(c.block, loc)
            if reason:
                dropped.append({"gen": c.gen, "subject": c.subject, "reason": reason})
            else:
                ok_cands.append(c)
        limit, with_table, min_share = C.LIMITS[tier if tier in C.LIMITS else "light"]
        if dormant:
            limit, with_table, min_share = 3, False, 1 / 3
            if tier == "cold":
                limit = 2
        chosen = C.pick(ok_cands, limit)
        table, table_used = (None, [])
        if with_table:
            rest = [c for c in sorted(ok_cands, key=lambda c: -c.score) if c not in chosen and c.subject not in
                    {x.subject for x in chosen}]
            table, table_used = C.table_block(rest, loc)
            if table and check_block(table, loc):
                dropped.append({"gen": "table", "reason": check_block(table, loc)})
                table, table_used = None, []
        if not chosen and not table:
            res = _general(us.user_id, loc, base, "general", tier, arm, profile=profile)
            res.blocks_meta += [{"origin": "dropped", **d} for d in dropped]
            return res

        # Блоки редакции: без дублей личных рядов; доля редакции — не меньше min_share.
        personal_paths = {_path(_abs(c.block.get("url") or "", loc)) for c in chosen + table_used}
        editorial = [b for b in editorial if _path(b.get("url")) not in personal_paths or not b.get("url")]
        if dormant:
            editorial = editorial[:1]
        n_personal = len(chosen) + (1 if table else 0)
        n_editorial = (1 if lead else 0) + len(editorial)
        cap = C.MAX_CONTENT_BLOCKS
        if n_personal + n_editorial > cap and editorial:
            # Лишние блоки редакции уходят с конца по близости к интересам человека (порядок редакции сохраняется).
            relevance = await self._editorial_relevance(editorial, profile)
            order = sorted(range(len(editorial)), key=lambda i: (relevance[i], -i))
            drop = set(order[:max(0, n_personal + n_editorial - cap)])
            editorial = [b for i, b in enumerate(editorial) if i not in drop]
            n_editorial = (1 if lead else 0) + len(editorial)
        while not C.editorial_share_ok(n_editorial, n_personal + n_editorial, min_share) and n_personal > 1:
            if table:
                table, table_used = None, []
            else:
                chosen.pop()
            n_personal -= 1

        # Сборка.
        out_blocks: list[dict] = []
        meta: list[dict] = []

        def add(block: dict, origin: str, cand: C.Candidate | None = None, gen: str | None = None) -> None:
            pos = len(out_blocks) + 1
            b = copy.deepcopy(block)
            content = None
            if origin == "personal":
                g = cand.gen if cand else (gen or "table")
                content = f"p{pos}-{g}"
                if b.get("url"):
                    token = ab.click_token(us.user_id, key) if self.click_tokens else None
                    b["url"] = _utm(_abs(b["url"], loc), key, content, token)
                for k in ("kicker", "title", "text", "why", "value", "last_actual"):
                    if isinstance(b.get(k), str):
                        b[k] = T.typo(b[k], loc)
            out_blocks.append(b)
            m = {"pos": pos, "origin": origin, "type": b.get("type"), "utm_content": content or _content_of(b)}
            if cand is not None:
                m.update({"gen": cand.gen, "subject": cand.subject, "as_of": cand.as_of, "reason": cand.why,
                          "score": round(cand.score, 4), "topic": cand.topic})
                for k in ("item_id", "target", "value", "value_text", "period"):
                    if k in cand.extra:
                        m[k] = cand.extra[k]
            elif gen:
                m.update({"gen": gen, "subjects": [c.subject for c in table_used],
                          "as_of": max((c.as_of or "" for c in table_used), default=None)})
            meta.append(m)

        if lead:
            add(lead, "editorial")
        if section_supported():
            add({"type": "section", "title": T.t(loc, "section.title"), "text": T.t(loc, "section.text")},
                "personal", gen="section")
        for c in sorted(chosen, key=lambda c: (c.gen != "check", c.gen == "forecast" and c.why == "topic", -c.score)):
            add(c.block, "personal", c)
        if table:
            add(table, "personal", gen="table")
            for c in table_used:  # строки таблицы — тоже показанные факты (защита от повторов)
                meta.append({"pos": None, "origin": "personal", "gen": "table_row", "subject": c.subject,
                             "as_of": c.as_of, "reason": c.why, "score": round(c.score, 4), "topic": c.topic,
                             "utm_content": None})
        for b in editorial:
            add(b, "editorial")
        cal = await self._calendar(calendar, profile, loc, ctx)
        if cal:
            add(cal, "editorial" if cal is calendar else "personal", gen=None if cal is calendar else "calendar")
        meta += [{"origin": "dropped", **d} for d in dropped]

        payload = {k: v for k, v in base.items() if k != "blocks"}
        payload["blocks"] = out_blocks
        topics = [topic_label(c.topic, loc).lower() for c in chosen if c.topic]
        topics = list(dict.fromkeys(topics))[:3]
        n_numbers = len(chosen) + (len(table_used) if table else 0)
        extra_intro = (T.t(loc, "intro.since", date=T.typo(_date_text(us.last_visit.date(), loc), loc)) if dormant
                       else T.t(loc, "intro.more", n=T.plural(n_numbers, loc), topics=", ".join(topics)) if topics
                       else "")
        if extra_intro:
            payload["intro"] = (payload.get("intro") or "").rstrip() + "\n\n" + T.typo(extra_intro, loc)
        payload["personal_note"] = T.t(loc, "note")
        subject_arm = ab.subject_arm(us.user_id, key, self.subject_ab_pct)
        if subject_arm == "subj_personal":
            _personal_subject(payload, chosen, loc)
        data_as_of = max((date.fromisoformat(c.as_of[:10]) for c in chosen + table_used
                          if c.as_of and len(c.as_of) >= 10), default=None)
        # Последняя проверка формой почты: не прошло — общий выпуск.
        from app.services.mail.campaign import parse_issue

        try:
            parse_issue({"key": key, loc: copy.deepcopy(payload)})
        except Exception as exc:  # noqa: BLE001
            return _general(us.user_id, loc, base, "fallback", tier, arm, profile=profile,
                            error=f"parse:{str(exc)[:80]}")
        return BuildResult(us.user_id, loc, "built", tier, arm, subject_arm, payload, meta, data_as_of,
                           profile=profile)

    async def _editorial_relevance(self, editorial: list[dict], profile: Profile) -> list[float]:
        from app.services.newsletter_personal.subjects import subjects_from_path

        keys = []
        for b in editorial:
            subs = [s for s in subjects_from_path(_path(b.get("url"))) if s.is_series]
            keys.append(subs[0].key if subs else None)
        hints = await self.cache("ru").topics([k for k in keys if k])
        out = []
        for k in keys:
            if not k:
                out.append(0.0)
                continue
            out.append(profile.score(k) + profile.topics.get(hints.get(k, ""), 0.0))
        return out

    async def _calendar(self, calendar: dict | None, profile: Profile, loc: str, ctx: C.Context) -> dict | None:
        codes = [parse_key(s["key"]).code for s in profile.series()[:10]
                 if parse_key(s["key"]) is not None and parse_key(s["key"]).kind == "ru"]
        mine = await ctx.cache.upcoming_events(codes)
        if not mine:
            return calendar
        entries = list((calendar or {}).get("entries") or [])
        seen = {(e.get("date_iso"), (e.get("title") or "").lower()[:40]) for e in entries}
        added = 0
        for e in mine:
            k = (e["date_iso"], e["title"].lower()[:40])
            if k in seen or len(entries) >= C.MAX_CAL_ENTRIES:
                continue
            seen.add(k)
            entry = {"date": e["date"], "title": T.typo(e["title"], loc), "date_iso": e["date_iso"]}
            if e.get("time"):
                entry["time"] = e["time"]
            entries.append(entry)
            added += 1
        if not added:
            return calendar
        undated = [e for e in entries if not e.get("date_iso")]
        dated = sorted((e for e in entries if e.get("date_iso")), key=lambda e: e["date_iso"])
        block = dict(calendar or {"type": "calendar", "kicker": "Calendar" if loc == "en" else "Календарь",
                                  "title": "What comes next" if loc == "en" else "Что выйдет дальше",
                                  "url": _abs("/russia/calendar", loc)})
        block["entries"] = undated + dated
        return block


def _content_of(block: dict) -> str | None:
    from urllib.parse import parse_qs

    url = block.get("url") or ""
    q = parse_qs(urlsplit(url).query)
    return (q.get("utm_content") or [None])[0]


def _date_text(d: date, loc: str) -> str:
    from app.services.newsletter_personal.facts import full_date

    return full_date(d, loc)


def _personal_subject(payload: dict, chosen: list[C.Candidate], loc: str) -> None:
    """Личная тема/прехедер по правилам редакции: тема до 50 знаков, число в первых 35; прехедер ≤ 110."""
    top = next((c for c in chosen if c.block.get("value") and c.gen in
                ("series", "download", "search", "region", "since", "check")), None)
    if top is None:
        return
    title = T.clean_title(str(top.extra.get("title") or top.block.get("title") or ""), 60)
    value = str(top.block.get("value") or "")
    subj = f"{title}: {value}"
    # Тема с единицей «индекс» или «единиц» («…: 341,06 индекс») читается как сбой — остаётся тема редакции.
    plain_unit = not any(w in value.lower() for w in ("индекс", "index", "единиц", "units"))
    if len(subj) <= 50 and subj.find(value) <= 35 and plain_unit:
        payload["subject"] = T.typo(subj, loc)
    lead_in = f"{title} — {value.rstrip('.')}. "
    pre = lead_in + (payload.get("preheader") or "")
    if len(pre) > 110:
        pre = pre[:110].rsplit(" ", 1)[0].rstrip(",;:—- ") + "…"
    payload["preheader"] = T.typo(pre, loc)


def _fatigue(us: UserSignals) -> dict[str, int]:
    """Сколько последних выпусков подряд предмет был показан без клика."""
    clicked = {(c["campaign"], c["content"]) for c in us.clicks}
    streak: dict[str, int] = {}
    broken: set[str] = set()
    for h in sorted(us.history, key=lambda h: h["built_at"], reverse=True):
        shown = {}
        for m in h.get("blocks_meta") or []:
            if m.get("origin") == "personal" and m.get("subject"):
                shown[m["subject"]] = (h["campaign"], m.get("utm_content")) in clicked
        for subj, was_clicked in shown.items():
            if subj in broken:
                continue
            if was_clicked:
                broken.add(subj)
            else:
                streak[subj] = streak.get(subj, 0) + 1
    return streak


def _general(user_id: str, loc: str, base: dict, status: str, tier: str, arm: str, *,
             profile: Profile | None = None, error: str | None = None) -> BuildResult:
    payload = copy.deepcopy(base)
    meta = [{"pos": i + 1, "origin": "editorial", "type": b.get("type"), "utm_content": _content_of(b)}
            for i, b in enumerate(payload["blocks"])]
    return BuildResult(user_id, loc, status, tier, arm, None, payload, meta, None, error, profile)


# --- публичные функции -----------------------------------------------------------------

async def locale_for(db: AsyncSession, user_id: uuid.UUID) -> str:
    from app.services.mail import audience

    rec = await audience.resolve(db, user_id)
    return rec.locale if rec else "ru"


async def build_personal_issue(db: AsyncSession, user_id: uuid.UUID | str, issue, *, locale: str | None = None,
                               behavior: bool | None = None, today: date | None = None) -> dict | None:
    """Персональный выпуск на языке человека (без сохранения и отправки) или None (нет языка в выпуске)."""
    uid = uuid.UUID(str(user_id))
    builder = Builder(db, issue, today=today, behavior=behavior)
    us = (await collect(db, [uid], now=builder.now, behavior=builder.behavior))[str(uid)]
    res = await builder.build(us, locale or await locale_for(db, uid))
    return res.payload


@dataclass
class CampaignReport:
    key: str
    users: int = 0
    statuses: dict = field(default_factory=dict)
    tiers: dict = field(default_factory=dict)
    personal_blocks: dict = field(default_factory=dict)
    dropped: dict = field(default_factory=dict)
    fact_reads: int = 0
    seconds: float = 0.0
    stopped: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def _bump(d: dict, k, n: int = 1) -> None:
    d[k] = d.get(k, 0) + n


async def build_campaign(db: AsyncSession, issue, *, persist: bool = True, behavior: bool | None = None,
                         limit: int | None = None, deadline: datetime | None = None,
                         user_ids: list[uuid.UUID] | None = None) -> CampaignReport:
    """Снимки по всем подписчикам пакетами; адресов не читает и не выводит."""
    import time

    from app.services import host_pressure
    from app.services.mail import audience

    started = time.monotonic()
    builder = Builder(db, issue, behavior=behavior)
    report = CampaignReport(key=issue.key)
    ids = user_ids if user_ids is not None else await audience.subscriber_ids(db)
    if limit:
        ids = ids[:limit]
    can_store = persist and await store.tables_ready(db)
    batch = max(1, int(settings.newsletter_personal_batch_size))
    for i in range(0, len(ids), batch):
        if deadline and _utcnow() >= deadline:
            report.stopped = "deadline"
            break
        while host_pressure.io_degraded():
            await asyncio.sleep(5)
        chunk = ids[i:i + batch]
        sigs = await collect(db, chunk, now=builder.now, behavior=builder.behavior)
        locales = {}
        for uid in chunk:
            rec = await audience.resolve(db, uid)
            locales[str(uid)] = rec.locale if rec else "ru"
        for uid in chunk:
            us = sigs[str(uid)]
            res = await builder.build(us, locales[str(uid)])
            report.users += 1
            _bump(report.statuses, res.status)
            _bump(report.tiers, res.tier)
            for m in res.blocks_meta:
                if m.get("origin") == "personal" and m.get("gen"):
                    _bump(report.personal_blocks, m["gen"])
                if m.get("origin") == "dropped":
                    _bump(report.dropped, m.get("reason") or "?")
            if can_store and res.status != "no_locale":
                if res.profile is not None:
                    await store.save_profile(db, uid, res.profile.as_row(), version=PROFILE_VERSION, now=builder.now)
                await store.save_issue(db, campaign=issue.key, user_id=uid, locale=res.locale, arm=res.arm,
                                       subject_arm=res.subject_arm, tier=res.tier, status=res.status,
                                       payload=res.payload, blocks_meta=res.blocks_meta,
                                       data_as_of=res.data_as_of, error=res.error, now=builder.now)
        if can_store:
            await db.commit()
        pause = float(settings.newsletter_personal_batch_pause_seconds)
        if pause > 0 and i + batch < len(ids):
            await asyncio.sleep(pause)
    report.fact_reads = sum(c.reads for c in builder._caches.values())
    report.seconds = round(time.monotonic() - started, 2)
    return report


# --- отправка: функция для mail.campaign.run(per_recipient=…) ---------------------------------

def _local_hour(tz_name: str | None, now: datetime) -> int:
    try:
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(tz_name or "Europe/Moscow")
    except Exception:  # noqa: BLE001
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("Europe/Moscow")
    return now.replace(tzinfo=timezone.utc).astimezone(tz).hour


def in_send_window(tz_name: str | None, now: datetime) -> bool:
    h = _local_hour(tz_name, now)
    return settings.newsletter_personal_send_start_hour <= h < settings.newsletter_personal_send_end_hour


async def sent_recently(db: AsyncSession, user_id: uuid.UUID, campaign: str, now: datetime) -> bool:
    from app.models import MailMessage

    days = int(settings.newsletter_personal_min_days_between)
    if days <= 0:
        return False
    row = await db.scalar(select(MailMessage.id).where(
        MailMessage.user_id == user_id, MailMessage.kind == "newsletter", MailMessage.status == "sent",
        MailMessage.campaign != campaign, MailMessage.sent_at >= now - timedelta(days=days)).limit(1))
    return row is not None


async def snapshot_fresh(db: AsyncSession, builder: Builder, snap) -> bool:
    """Числа снимка совпадают с базой (ряд не обновился после сборки)."""
    cache = builder.cache(snap.locale)
    for m in snap.blocks_meta or []:
        if m.get("origin") != "personal" or not m.get("subject") or not m.get("as_of"):
            continue
        sub = parse_key(m["subject"])
        if sub is None or not sub.is_series:
            continue
        fact = await cache.get(m["subject"])
        if fact is None or fact.as_of.isoformat() != m["as_of"]:
            return False
    return True


def per_recipient_hook(issue, *, behavior: bool | None = None, respect_quiet_hours: bool = True):
    """Функция для ``campaign.run(per_recipient=…)``: снимок или сборка на лету; тихие часы и частота.

    Возвращает словарь языка, ``campaign.DEFER`` (если почта его поддерживает) или None —
    отложить/пропустить. Без включённой персонализации (`newsletter_personal_enabled`) —
    выпуск редакции как есть.
    """
    holder: dict = {}

    async def hook(db: AsyncSession, rec, _issue) -> dict | None:
        from app.services.mail import campaign as mail_campaign

        defer = getattr(mail_campaign, "DEFER", None)
        loc = rec.locale if rec.locale in issue.by_locale else None
        if loc is None:
            return None
        if not settings.newsletter_personal_enabled:
            return digest_to_dict(issue.by_locale[loc])
        builder = holder.get("b")
        if builder is None:
            builder = holder["b"] = Builder(db, issue, behavior=behavior)
        now = _utcnow()
        if await sent_recently(db, rec.user_id, issue.key, now):
            return defer
        snap = await store.load_issue(db, issue.key, rec.user_id)
        tz = None
        if snap is not None and await store.tables_ready(db):
            from app.models import NewsletterProfile

            tz = await db.scalar(select(NewsletterProfile.timezone).where(NewsletterProfile.user_id == rec.user_id))
        if respect_quiet_hours and not in_send_window(tz, now):
            return defer
        if snap is not None and snap.payload and snap.locale == loc and await snapshot_fresh(db, builder, snap):
            return copy.deepcopy(snap.payload)
        try:
            us = (await asyncio.wait_for(collect(db, [rec.user_id], now=now, behavior=builder.behavior),
                                         ON_THE_FLY_TIMEOUT))[str(rec.user_id)]
            res = await asyncio.wait_for(builder.build(us, loc), ON_THE_FLY_TIMEOUT)
        except Exception as exc:  # noqa: BLE001 — честный общий выпуск
            logger.warning("newsletter on-the-fly build failed %s: %s", ab.user_hash(str(rec.user_id)),
                           type(exc).__name__)
            return digest_to_dict(issue.by_locale[loc])
        if await store.tables_ready(db):
            await store.save_issue(db, campaign=issue.key, user_id=rec.user_id, locale=res.locale, arm=res.arm,
                                   subject_arm=res.subject_arm, tier=res.tier, status=res.status,
                                   payload=res.payload, blocks_meta=res.blocks_meta, data_as_of=res.data_as_of,
                                   error=res.error, now=now)
        return res.payload

    return hook


__all__ = ["Builder", "BuildResult", "build_personal_issue", "build_campaign", "per_recipient_hook",
           "digest_to_dict", "check_block", "section_supported", "in_send_window"]
