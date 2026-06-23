"""Контракт hook'ов BaseParser.

Регрессия 2026-06-22: `base_parser.run()` зовёт `_handle_forecasts(..., pruned)`
(7 позиционных c self), а override в `CbrKeyRateParser` принимал 6 → daily ETL
key-rate падал «takes 6 positional arguments but 7 were given». Любой override
hook'а обязан принимать ту же сигнатуру, что и база.
"""

import inspect

from app.services.base_parser import BaseParser
from app.services.rosstat_cpi_parser import PARSER_REGISTRY  # noqa: F401  (триггерит импорт всех парсеров)

_HOOKS = ("_handle_forecasts", "_post_upsert", "_after_storage", "_validate", "_fetch_and_parse")


def _all_subclasses(cls):
    for sub in cls.__subclasses__():
        yield sub
        yield from _all_subclasses(sub)


def test_parser_hook_overrides_match_base_signature():
    subclasses = set(_all_subclasses(BaseParser))
    assert subclasses, "PARSER_REGISTRY импорт не подтянул ни одного парсера"
    problems: list[str] = []
    for hook in _HOOKS:
        base_params = list(inspect.signature(getattr(BaseParser, hook)).parameters)
        for sub in subclasses:
            fn = sub.__dict__.get(hook)
            if fn is None:
                continue
            params = list(inspect.signature(fn).parameters)
            if params[: len(base_params)] != base_params:
                problems.append(
                    f"{sub.__name__}.{hook} {params} != base {base_params}"
                )
    assert not problems, "Несовместимые сигнатуры hook'ов:\n" + "\n".join(problems)
