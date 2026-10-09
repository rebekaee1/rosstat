"""Серверная выгрузка таблиц (Excel/CSV) с гейтом по лимиту (ADR-0007 Phase 2).

Генерация файла перенесена с клиента на бэкенд: это (1) даёт жёсткий лимит
гостевых скачиваний, (2) снимает ~430 КБ xlsx из фронтового бандла. Трансформы
рядов (режимы графика) остаются на клиенте — сюда приходят уже готовые точки.

Числа в CSV — через ``display.format_number_ru`` (русская запятая). В шапке
файла — название, единица, частота, страна, источник и дата выгрузки.
"""
import io
import logging
import re
from datetime import datetime
from urllib.parse import quote
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, field_validator, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import User
from app.services import cabinet as cabinet_svc
from app.security.auth import get_optional_user
from app.security import download_quota as dq
from app.services.api_i18n import api_detail
from app.services.display import format_number_ru, today_msk
from app.services.locale import get_locale
from app.services import export_grid
from app.services.export_render import ExportAdmission, render_export_async, reserve_export_admission

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/export", tags=["export"])

_MAX_POINTS = 100_000
_MSK = ZoneInfo("Europe/Moscow")


class ExportPoint(BaseModel):
    date: str
    actual: float | None = None
    forecast: float | None = None


class ExportMeta(BaseModel):
    """Опциональные поля provenance для шапки файла."""

    indicator_name: str | None = None
    unit: str | None = None
    frequency: str | None = None
    country: str | None = None
    source: str | None = None
    source_url: str | None = None
    provenance: str | None = None


class ExportHistoryHint(BaseModel):
    """Необязательная подсказка клиента для истории выгрузок в кабинете (вошедшему,
    при включённом кабинете): что нужно, чтобы построить тот же файл заново.
    Файл не хранится. Диапазонов (lower/upper) здесь нет и быть не может."""

    source: str | None = None        # table | chart | compare | rating | region | calc ...
    subject_key: str | None = None   # код показателя / страница, по которой выгружали
    params: dict | None = None       # параметры повтора (страна, период, режим), до 4 КБ


class ExportIn(BaseModel):
    format: str
    filename: str
    value_label: str = "Значение"
    points: list[ExportPoint]
    # Плоские поля (удобно для клиента) + вложенный meta.
    indicator_name: str | None = None
    unit: str | None = None
    frequency: str | None = None
    country: str | None = None
    source: str | None = None
    source_url: str | None = None
    provenance: str | None = None
    meta: ExportMeta | None = None
    history: ExportHistoryHint | None = None

    @field_validator("format")
    @classmethod
    def _fmt(cls, v: str) -> str:
        v = (v or "").lower()
        if v not in ("xlsx", "csv"):
            raise ValueError("format must be xlsx or csv")
        return v

    @field_validator("points")
    @classmethod
    def _points(cls, v: list) -> list:
        if not v:
            raise ValueError("no points")
        if len(v) > _MAX_POINTS:
            raise ValueError("too many points")
        return v


_COL_KEY_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")
GridCell = int | float | str | None


class GridColumn(BaseModel):
    key: str
    label: str
    unit: str | None = None

    @field_validator("key")
    @classmethod
    def _key(cls, v: str) -> str:
        if not _COL_KEY_RE.match(v or "") or v.lower() in export_grid.FORBIDDEN_KEYS:
            raise ValueError("invalid column key")
        return v

    @field_validator("label")
    @classmethod
    def _label(cls, v: str) -> str:
        v = (v or "").strip()
        if not v or len(v) > 200:
            raise ValueError("invalid column label")
        return v

    @field_validator("unit")
    @classmethod
    def _unit(cls, v: str | None) -> str | None:
        v = (v or "").strip()
        return v[:40] or None


class GridMeta(BaseModel):
    source: str | None = None
    source_url: str | None = None
    country: str | None = None
    frequency: str | None = None
    provenance: str | None = None
    note: str | None = None


class GridIn(BaseModel):
    """Сетка для выгрузки: колонки + строки-словари {ключ колонки: точечное значение}.

    Колонка с ключом `date` или `year` (если есть) служит осью времени: гостю при
    `download_anon_history_years` > 0 отдаются только последние годы, как в /export/table.
    """

    format: str
    filename: str
    title: str = ""
    columns: list[GridColumn]
    rows: list[dict[str, GridCell]]
    meta: GridMeta | None = None
    history: ExportHistoryHint | None = None

    @field_validator("format")
    @classmethod
    def _fmt(cls, v: str) -> str:
        v = (v or "").lower()
        if v not in ("xlsx", "csv"):
            raise ValueError("format must be xlsx or csv")
        return v

    @field_validator("filename")
    @classmethod
    def _filename(cls, v: str) -> str:
        v = (v or "").strip()
        if not v or len(v) > 200:
            raise ValueError("invalid filename")
        return v

    @field_validator("title")
    @classmethod
    def _title(cls, v: str) -> str:
        return (v or "").strip()[:300]

    @field_validator("columns")
    @classmethod
    def _columns(cls, v: list[GridColumn]) -> list[GridColumn]:
        if not v or len(v) > export_grid.MAX_COLUMNS:
            raise ValueError("invalid columns")
        if len({c.key for c in v}) != len(v):
            raise ValueError("duplicate column keys")
        return v

    @field_validator("rows")
    @classmethod
    def _rows(cls, v: list[dict]) -> list[dict]:
        if not v:
            raise ValueError("no rows")
        if len(v) > export_grid.MAX_ROWS:
            raise ValueError("too many rows")
        for row in v:
            if len(row) > export_grid.MAX_COLUMNS or any(
                str(k).lower() in export_grid.FORBIDDEN_KEYS for k in row
            ):
                raise ValueError("invalid row")
        return v

    @model_validator(mode="after")
    def _cells(self):
        if len(self.rows) * len(self.columns) > export_grid.MAX_CELLS:
            raise ValueError("too many cells")
        return self


def _round(x: float | None) -> float | None:
    return None if x is None else round(float(x), 4)


def _point_year(date_str: str) -> int | None:
    """Год из ISO-даты точки ('2024-01-01', '2024', '2024-W03') — для гейта глубины."""
    head = (date_str or "").strip()[:4]
    return int(head) if head.isdigit() else None


def _limit_history(points: list[ExportPoint]) -> list[ExportPoint]:
    """Гостю отдаём только последние N лет истории; полный период — за регистрацию.

    Отсчёт от самой поздней точки набора (а не от текущей даты): прогноз уходит
    в будущее, поэтому ориентир — максимальный год среди переданных точек.
    """
    years = settings.download_anon_history_years
    if years <= 0:
        return points
    yrs = [y for p in points if (y := _point_year(p.date)) is not None]
    if not yrs:
        return points
    cutoff = max(yrs) - years
    limited = [p for p in points if (y := _point_year(p.date)) is None or y > cutoff]
    return limited or points


def _split(points: list[ExportPoint]):
    facts = [(p.date, _round(p.actual)) for p in points if p.actual is not None]
    forecasts = [
        (p.date, _round(p.forecast))
        for p in points
        if p.forecast is not None and p.actual is None
    ]
    return facts, forecasts


def _resolve_meta(body: ExportIn | None = None, **kwargs) -> dict[str, str]:
    """Собрать поля шапки из body / kwargs."""
    m = (body.meta if body is not None else None) or ExportMeta()
    get = lambda k: (
        kwargs.get(k)
        or (getattr(body, k, None) if body is not None else None)
        or getattr(m, k, None)
        or ""
    )
    exported_at = datetime.now(_MSK).strftime("%Y-%m-%d %H:%M %Z")
    return {
        "indicator_name": str(get("indicator_name") or "").strip(),
        "unit": str(get("unit") or "").strip(),
        "frequency": str(get("frequency") or "").strip(),
        "country": str(get("country") or "").strip(),
        "source": str(get("source") or "").strip(),
        "source_url": str(get("source_url") or "").strip(),
        "provenance": str(get("provenance") or "").strip(),
        "exported_at": exported_at,
        "exported_date": today_msk().isoformat(),
    }


def _export_labels() -> dict[str, str]:
    if get_locale() == "en":
        return {
            "indicator": "Indicator",
            "unit": "Unit",
            "frequency": "Frequency",
            "country": "Country",
            "source": "Source",
            "source_url": "Source URL",
            "exported_at": "Exported at",
            "value": "Value",
            "date": "Date",
            "type": "Type",
            "actual": "actual",
            "forecast": "forecast",
            "description": "Description",
            "facts": "Actual",
            "forecasts": "Forecast",
            "forecast_value": "Forecast {label}",
            "default_source": "Not specified",
            "provenance": "Calculation",
        }
    return {
        "indicator": "Показатель",
        "unit": "Единица",
        "frequency": "Частота",
        "country": "Страна",
        "source": "Источник",
        "source_url": "URL источника",
        "exported_at": "Дата выгрузки",
        "value": "Значение",
        "date": "Дата",
        "type": "Тип",
        "actual": "факт",
        "forecast": "прогноз",
        "description": "Описание",
        "facts": "Факт",
        "forecasts": "Прогноз",
        "forecast_value": "Прогноз {label}",
        "default_source": "Не указан",
        "provenance": "Расчёт",
    }


def _meta_rows(meta: dict[str, str], value_label: str) -> list[tuple[str, str]]:
    """Пары (поле, значение) для шапки файла."""
    labels = _export_labels()
    name = meta.get("indicator_name") or value_label or labels["value"]
    rows: list[tuple[str, str]] = [
        (labels["indicator"], name),
    ]
    if meta.get("unit"):
        rows.append((labels["unit"], meta["unit"]))
    if meta.get("frequency"):
        rows.append((labels["frequency"], meta["frequency"]))
    if meta.get("country"):
        rows.append((labels["country"], meta["country"]))
    source = meta.get("source") or labels["default_source"]
    rows.append((labels["source"], source))
    if meta.get("provenance"):
        rows.append((labels["provenance"], meta["provenance"]))
    if meta.get("source_url"):
        rows.append((labels["source_url"], meta["source_url"]))
    rows.append((labels["exported_at"], meta.get("exported_at") or meta.get("exported_date") or ""))
    return rows


def _format_csv_value(val: float | None) -> str:
    if val is None:
        return ""
    return format_number_ru(val, locale=get_locale())


def _build_xlsx(
    facts,
    forecasts,
    value_label: str,
    meta: dict[str, str] | None = None,
) -> bytes:
    from openpyxl import Workbook

    meta = meta or _resolve_meta()
    labels = _export_labels()
    wb = Workbook()
    ws_meta = wb.active
    ws_meta.title = labels["description"]
    for label, value in _meta_rows(meta, value_label):
        ws_meta.append([label, value])

    ws = wb.create_sheet(labels["facts"], 1)
    ws.append([labels["date"], value_label])
    for date, val in facts:
        # Excel хранит число нативно; подпись единицы — в «Описание».
        ws.append([date, val])
    if forecasts:
        ws2 = wb.create_sheet(labels["forecasts"])
        ws2.append([labels["date"], labels["forecast_value"].format(label=value_label)])
        for date, val in forecasts:
            ws2.append([date, val])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _build_csv(
    facts,
    forecasts,
    value_label: str,
    meta: dict[str, str] | None = None,
) -> bytes:
    meta = meta or _resolve_meta()
    labels = _export_labels()
    lines: list[str] = []
    for label, value in _meta_rows(meta, value_label):
        # экранируем ';' в значениях
        safe = str(value).replace(";", ",")
        lines.append(f"# {label};{safe}")
    lines.append(";".join([labels["date"], value_label, labels["type"]]))
    for date, val in facts:
        lines.append(";".join([date, _format_csv_value(val), labels["actual"]]))
    for date, val in forecasts:
        lines.append(";".join([date, _format_csv_value(val), labels["forecast"]]))
    return ("\ufeff" + "\n".join(lines)).encode("utf-8")


def _build_table(body: ExportIn, authenticated: bool) -> bytes:
    """All O(points) preparation and file construction belong to the worker."""
    points = body.points if authenticated else _limit_history(body.points)
    facts, forecasts = _split(points)
    meta = _resolve_meta(body)
    if not meta.get("indicator_name") and body.value_label:
        meta["indicator_name"] = body.value_label
    builder = _build_xlsx if body.format == "xlsx" else _build_csv
    return builder(facts, forecasts, body.value_label, meta)


def _grid_rows_for(body: GridIn, authenticated: bool) -> list[dict]:
    """Гостю — последние годы по оси `date`/`year` (как _limit_history); вошедшему всё."""
    rows = body.rows
    years = settings.download_anon_history_years
    axis = next((c.key for c in body.columns if c.key in ("date", "year")), None)
    if authenticated or years <= 0 or axis is None:
        return rows
    ys = [y for r in rows if (y := _point_year(str(r.get(axis) or ""))) is not None]
    if not ys:
        return rows
    cutoff = max(ys) - years
    kept = [r for r in rows if (y := _point_year(str(r.get(axis) or ""))) is None or y > cutoff]
    return kept or rows


def _build_grid(body: GridIn, authenticated: bool) -> bytes:
    """Вся O(cells) работа и сборка файла — в рабочем потоке."""
    locale = get_locale()
    columns = [c.model_dump() for c in body.columns]
    rows = _grid_rows_for(body, authenticated)
    meta = {k: (v or "").strip() for k, v in (body.meta.model_dump() if body.meta else {}).items()}
    exported_at = datetime.now(_MSK).strftime("%Y-%m-%d %H:%M %Z")
    builder = export_grid.build_xlsx if body.format == "xlsx" else export_grid.build_csv
    return builder(body.title or body.filename, columns, rows, meta, exported_at, locale)


def _content_disposition(filename: str) -> str:
    ascii_fallback = "export." + (filename.rsplit(".", 1)[-1] if "." in filename else "dat")
    return f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{quote(filename)}"


async def consume_anon_quota(request: Request, user: User | None) -> str | None:
    """Гостевой лимит выгрузок (общий для /export/table и /export/grid).

    Вошедшему ничего не списывается. Возвращает id нового cookie `fe_dl`, если его
    нужно выставить в ответе; при исчерпании лимита — 403 `download_limit`.
    """
    if user is not None:
        return None
    set_cookie_id: str | None = None
    dl_id = request.cookies.get(dq.DL_COOKIE)
    if not dl_id:
        dl_id = dq.new_download_id()
        set_cookie_id = dl_id
    allowed = await dq.consume_anon_download(dl_id)
    if not allowed:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "download_limit",
                "message": api_detail(
                    "Лимит бесплатных выгрузок исчерпан. Войдите в аккаунт для безлимитного скачивания.",
                    "Free download limit reached. Sign in for unlimited downloads.",
                ),
            },
        )
    return set_cookie_id


async def decorate_download(resp: Response, request: Request, user: User | None, set_cookie_id: str | None) -> None:
    """Заголовок остатка гостевых выгрузок и cookie `fe_dl` (как в /export/table)."""
    if user is None:
        remaining = await dq.remaining_anon_downloads(set_cookie_id or request.cookies.get(dq.DL_COOKIE))
        resp.headers["X-Download-Remaining"] = str(remaining)
        resp.headers["Access-Control-Expose-Headers"] = "X-Download-Remaining"
    if set_cookie_id is not None:
        kw = {"httponly": True, "secure": settings.auth_cookie_secure, "samesite": "lax", "path": "/"}
        if settings.auth_cookie_domain:
            kw["domain"] = settings.auth_cookie_domain
        resp.set_cookie(dq.DL_COOKIE, set_cookie_id, max_age=settings.download_anon_window_seconds, **kw)


async def record_history_safe(
    db: AsyncSession, user: User | None, *, source: str, subject_key: str | None,
    fmt: str, params: dict | None, rows_count: int | None,
) -> None:
    """История выгрузок кабинета: только вошедшему и при включённом кабинете.

    Отдельный try: сбой записи истории НЕ ломает уже построенную выгрузку.
    """
    if user is None or not settings.cabinet_enabled:
        return
    try:
        await cabinet_svc.record_export(
            db, user.id, source=source, subject_key=subject_key, fmt=fmt,
            params=params, rows_count=rows_count)
    except Exception:
        logger.warning("export history write failed", exc_info=True)
        try:
            await db.rollback()
        except Exception:  # pragma: no cover
            pass


async def _record_history_safe(db: AsyncSession, user: User | None, body: ExportIn) -> None:
    if user is None or not settings.cabinet_enabled:
        return
    hint = body.history
    dates = [p.date for p in body.points if p.date]
    meta = _resolve_meta(body)
    params = {
        "filename": body.filename[:200],
        "value_label": (body.value_label or "")[:200],
        "indicator_name": meta.get("indicator_name") or None,
        "unit": meta.get("unit") or None,
        "frequency": meta.get("frequency") or None,
        "country": meta.get("country") or None,
        "period": {"from": min(dates), "to": max(dates)} if dates else None,
    }
    params = {k: v for k, v in params.items() if v}
    if hint and hint.params:
        params.update(hint.params)
    await record_history_safe(
        db, user, source=(hint.source if hint and hint.source else "table"),
        subject_key=(hint.subject_key if hint and hint.subject_key else meta.get("indicator_name") or body.filename),
        fmt=body.format, params=params, rows_count=len(body.points))


@router.get("/quota")
async def export_quota(
    request: Request,
    user: User | None = Depends(get_optional_user),
):
    """Сколько гостевых выгрузок осталось — для состояния кнопок UI (без инкремента).

    Авторизованный пользователь: unlimited=True. Гость: remaining из счётчика fe_dl.
    """
    if user is not None:
        return {"unlimited": True, "remaining": None, "limit": settings.download_anon_limit,
                "history_years": 0}
    dl_id = request.cookies.get(dq.DL_COOKIE)
    remaining = await dq.remaining_anon_downloads(dl_id)
    return {"unlimited": False, "remaining": remaining, "limit": settings.download_anon_limit,
            "history_years": settings.download_anon_history_years}


@router.post("/table")
async def export_table(
    body: ExportIn,
    request: Request,
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
    admission: ExportAdmission = Depends(reserve_export_admission),
):
    set_cookie_id = await consume_anon_quota(request, user)

    data = await render_export_async(_build_table, body, user is not None, admission=admission)
    media = ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
             if body.format == "xlsx" else "text/csv; charset=utf-8")

    resp = Response(content=data, media_type=media)
    resp.headers["Content-Disposition"] = _content_disposition(body.filename)
    await decorate_download(resp, request, user, set_cookie_id)
    await _record_history_safe(db, user, body)
    return resp


@router.post("/grid")
async def export_grid_file(
    body: GridIn,
    request: Request,
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
    admission: ExportAdmission = Depends(reserve_export_admission),
):
    """Универсальная выгрузка таблицы (сравнение, рейтинг, регион, график платежей).

    Тот же допуск (`reserve_export_admission`) и тот же гостевой лимит
    (`download_anon_limit`), что у /export/table. Только точечные значения: `lower` /
    `upper` отклоняются (422). Вошедшему при включённом кабинете параметры выгрузки
    попадают в историю (без файла)."""
    set_cookie_id = await consume_anon_quota(request, user)

    data = await render_export_async(_build_grid, body, user is not None, admission=admission)
    media = ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
             if body.format == "xlsx" else "text/csv; charset=utf-8")
    resp = Response(content=data, media_type=media)
    resp.headers["Content-Disposition"] = _content_disposition(body.filename)
    await decorate_download(resp, request, user, set_cookie_id)

    if user is not None and settings.cabinet_enabled:
        hint = body.history
        params = {
            "filename": body.filename[:200],
            "title": body.title[:200] or None,
            "columns": [c.label for c in body.columns][:20],
        }
        params = {k: v for k, v in params.items() if v}
        if hint and hint.params:
            params.update(hint.params)
        await record_history_safe(
            db, user, source=(hint.source if hint and hint.source else "grid"),
            subject_key=(hint.subject_key if hint and hint.subject_key else body.title or body.filename),
            fmt=body.format, params=params, rows_count=len(body.rows))
    return resp
