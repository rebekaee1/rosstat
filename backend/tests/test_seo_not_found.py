"""Брендовая 404 через /seo/not-found (nginx catch-all)."""


def test_seo_not_found_branded(client):
    r = client.get("/seo/not-found")
    assert r.status_code == 404
    html = r.text
    assert "Страница не найдена" in html
    assert 'href="/world"' in html
    assert 'href="/compare"' in html
    assert 'href="/russia/today"' in html
    assert "seo-topbar" in html or "Forecast" in html
    assert "noindex" in html
