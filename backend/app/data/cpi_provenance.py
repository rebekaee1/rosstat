"""Public provenance for CPI annual changes reconstructed from monthly indices."""
CPI_YOY_CODES = frozenset(f'{base}-yoy' for base in ('cpi', 'cpi-food', 'cpi-nonfood', 'cpi-services'))


def cpi_provenance(code: str, locale: str = 'ru') -> str | None:
    if code not in CPI_YOY_CODES:
        return None
    if locale == 'en':
        return ('Calculated by Forecast Economy from Rosstat monthly indices. '
                'May differ from the annual change published by Rosstat because the input indices are rounded.')
    return ('Расчёт Forecast Economy по месячным индексам Росстата. '
            'Может отличаться от опубликованного Росстатом годового изменения из-за округления исходных индексов.')
