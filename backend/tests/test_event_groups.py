"""Единые группы событий (круг 11, E4/E5): без пересечений и без выдуманных имён."""
from app.services import goal_taxonomy as tax


def test_event_groups_disjoint():
    seen: dict[str, str] = {}
    for group, names in tax.EVENT_GROUPS.items():
        for name in names:
            assert name not in seen, f"{name} одновременно в {seen[name]} и {group}"
            seen[name] = group


def test_every_grouped_event_is_classified_explicitly():
    missing = tax.all_grouped_events() - tax.explicit_events()
    assert not missing, f"события групп без явного tier: {sorted(missing)}"


def test_walls_and_errors_are_technical_downloads_are_not():
    """Упоры в стену и ошибки — знаменатель, не цель; скачивания — ценное действие."""
    for name in tax.events_in_group(tax.GROUP_WALL):
        assert tax.tier_for_event(name) == tax.TIER_TECHNICAL, name
    for name in tax.events_in_group(tax.GROUP_FRONT_ERROR):
        assert tax.tier_for_event(name) == tax.TIER_TECHNICAL, name
    for name in tax.events_in_group(tax.GROUP_DOWNLOAD):
        assert tax.is_conversion(name), name


def test_known_lost_names_are_gone():
    assert "compare_csv_download" not in tax.all_grouped_events()
    assert "api_error" not in tax.all_grouped_events()
    assert "download_limit" not in tax.events_in_group(tax.GROUP_DOWNLOAD)
    assert "regions_map_gif_download" in tax.events_in_group(tax.GROUP_DOWNLOAD)
    assert "demographics_csv" in tax.events_in_group(tax.GROUP_DOWNLOAD)
    assert "download_ical" in tax.events_in_group(tax.GROUP_DOWNLOAD)


def test_group_of_event():
    assert tax.group_of_event("download_csv") == tax.GROUP_DOWNLOAD
    assert tax.group_of_event("chart_image_blocked") == tax.GROUP_WALL
    assert tax.group_of_event("scroll_depth") is None


def test_report_modules_use_the_shared_groups():
    from app.services import admin_bi, analytics_report_bundle, pulse

    for module in (admin_bi, analytics_report_bundle, pulse):
        assert module._DOWNLOAD_EVENTS == tax.events_in_group(tax.GROUP_DOWNLOAD), module.__name__
        assert module._ERROR_EVENTS == tax.events_in_group(tax.GROUP_FRONT_ERROR), module.__name__
