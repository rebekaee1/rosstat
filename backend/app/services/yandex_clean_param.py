"""GET-параметры, которые не меняют документ, для директивы Clean-param.

Справка: https://yandex.ru/support/webmaster/ru/robot-workings/clean-param
Имя параметра регистрозависимое. Длина одного правила — не больше 500 символов.
Директива межсекционная: в robots.txt она стоит вне группы User-agent.

Не включать параметры, от которых зависит документ: ``preview_locale`` (другой
язык, страницы закрыты noindex), ``year``, ``view``, ``cols``, ``amount``,
``to``, ``country``. ``mode`` включён: канон карточки — URL без этого параметра.

Директиву Host не пишем. Яндекс не учитывает её с 2018 года; главный адрес
задаётся постоянным редиректом на https без www. Хост ``ru.`` — языковая
версия, не зеркало apex.
"""

from __future__ import annotations

# Часть меток (ysclid, utm_*) Яндекс может вычищать сам. Явное правило
# всё равно склеивает сигналы на канон, если автосписок отстаёт.
CLEAN_PARAM_GROUPS: tuple[str, ...] = (
    "utm_source&utm_medium&utm_campaign&utm_term&utm_content&utm_referrer"
    "&utm_media&utm_group&utm_expid&utm_id",
    "ysclid&yrclid&yclid&yadclid&yadordid&gclid&gbraid&wbraid&fbclid"
    "&msclkid&ttclid&twclid&srsltid",
    "etext&ybaip&_openstat&openstat&clid&yandex_referrer&erid&from&ref"
    "&ref_src&source&mc_cid&mc_eid&igshid&_ga&mode",
)

# Параметры, которые меняют страницу. Тест не даёт занести их в Clean-param.
CONTENT_PARAMS = frozenset({
    "preview_locale",
    "year",
    "view",
    "cols",
    "amount",
    "to",
    "country",
    "y",
    "m",
})

_RULE_LIMIT = 500


def clean_param_lines() -> list[str]:
    lines = [f"Clean-param: {group}" for group in CLEAN_PARAM_GROUPS]
    for line in lines:
        if len(line) > _RULE_LIMIT:
            raise ValueError(f"Clean-param rule is {len(line)} characters")
    return lines


def clean_param_names() -> frozenset[str]:
    names: set[str] = set()
    for group in CLEAN_PARAM_GROUPS:
        names.update(part for part in group.split("&") if part)
    overlap = names & CONTENT_PARAMS
    if overlap:
        raise ValueError(f"content params in Clean-param: {sorted(overlap)}")
    return frozenset(names)
