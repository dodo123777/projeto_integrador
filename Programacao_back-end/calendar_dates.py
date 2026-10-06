"""Datas de calendário, sem converter dias em instantes UTC."""
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


def calendar_date(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('Informe uma data válida.')
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError('Informe uma data válida.') from None


def week_bounds(value=None):
    anchor = calendar_date(value) if value is not None else datetime.now(ZoneInfo('America/Sao_Paulo')).date()
    try:
        start = anchor - timedelta(days=anchor.weekday())
        return start, start + timedelta(days=6)
    except OverflowError:
        raise ValueError('Escolha uma semana dentro dos limites do calendário.') from None
