"""Shared parsing/formatting for calculator suite."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any


TWOPLACES = Decimal("0.01")
FOURPLACES = Decimal("0.0001")


class CalcError(ValueError):
    pass


def D(value: Any, default: str | None = None) -> Decimal:
    if value is None or str(value).strip() == "":
        if default is not None:
            return Decimal(default)
        raise CalcError("Укажите числовое значение")
    s = str(value).strip().replace(" ", "").replace(",", ".")
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError) as exc:
        raise CalcError(f"Некорректное число: {value}") from exc


def money(value: Decimal) -> str:
    q = value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    return f"{q:,.2f}".replace(",", " ").replace(".", ",")


def num(value: Decimal, places: Decimal = FOURPLACES) -> str:
    q = value.quantize(places, rounding=ROUND_HALF_UP)
    s = f"{q:f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


def parse_date(value: Any, *, allow_empty: bool = False) -> date | None:
    if value is None or str(value).strip() == "":
        if allow_empty:
            return None
        raise CalcError("Укажите дату в формате ГГГГ-ММ-ДД")
    s = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise CalcError(f"Некорректная дата: {value}")


def today() -> date:
    return date.today()


def add_business_days(start: date, n: int) -> date:
    step = 1 if n >= 0 else -1
    left = abs(n)
    cur = start
    while left:
        cur += timedelta(days=step)
        if cur.weekday() < 5:
            left -= 1
    return cur


def years_months_days(start: date, end: date) -> tuple[int, int, int]:
    if end < start:
        start, end = end, start
    y = end.year - start.year
    m = end.month - start.month
    d = end.day - start.day
    if d < 0:
        m -= 1
        # days in previous month of end
        prev_month = end.month - 1 or 12
        prev_year = end.year if end.month > 1 else end.year - 1
        from calendar import monthrange
        d += monthrange(prev_year, prev_month)[1]
    if m < 0:
        y -= 1
        m += 12
    return y, m, d


def ok(title: str, lines: list[str], notes: list[str] | None = None) -> dict:
    return {"ok": True, "title": title, "lines": lines, "notes": notes or []}


def fail(msg: str) -> dict:
    return {"ok": False, "error": msg, "title": "", "lines": [], "notes": []}
