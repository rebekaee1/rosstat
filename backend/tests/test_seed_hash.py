"""П-12: seed_schema_hash — пропуск полного seed при неизменном desired-state.

Риск Р-3: хэш обязан покрывать сам сгенерированный payload (индикаторы,
включая развёрнутые generic-семьи, все SEO-слои, листинг, gap-fill), чтобы
«seed прошёл, но ничего не применил» был невозможен: любая правка входа
меняет хэш → полный прогон.
"""

import seed_data


def test_seed_hash_deterministic():
    assert seed_data.compute_seed_hash() == seed_data.compute_seed_hash()


def test_seed_hash_changes_on_indicator_edit(monkeypatch):
    base = seed_data.compute_seed_hash()
    tweaked = list(seed_data.INDICATORS) + [{"code": "test-new", "name": "x"}]
    monkeypatch.setattr(seed_data, "INDICATORS", tweaked)
    assert seed_data.compute_seed_hash() != base


def test_seed_hash_changes_on_seo_edit(monkeypatch):
    base = seed_data.compute_seed_hash()
    tweaked = dict(seed_data.INDICATOR_SEO)
    some_code = next(iter(tweaked))
    tweaked[some_code] = {**tweaked[some_code], "seo_title": "новый тайтл"}
    monkeypatch.setattr(seed_data, "INDICATOR_SEO", tweaked)
    assert seed_data.compute_seed_hash() != base


def test_seed_hash_changes_on_listing_edit(monkeypatch):
    base = seed_data.compute_seed_hash()
    tweaked = set(seed_data.INDICATOR_HIDDEN_FROM_LISTING) | {"test-hidden-code"}
    monkeypatch.setattr(seed_data, "INDICATOR_HIDDEN_FROM_LISTING", tweaked)
    assert seed_data.compute_seed_hash() != base
