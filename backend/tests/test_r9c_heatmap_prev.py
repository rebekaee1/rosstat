from app.api.regions import prev_year_month


def test_prev_year_month_keeps_month():
    assert prev_year_month(202609) == 202509
    assert prev_year_month(202601) == 202501
