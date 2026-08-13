"""RF tax/social constants used by calculators (kept current for 2026)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

# НДС: ФЗ от 28.11.2025 № 425-ФЗ — основная ставка 22% с 01.01.2026 (п. 3 ст. 164 НК РФ).
# Льготная 10% (п. 2 ст. 164) и 0% сохранены. Расчётные ставки: 22/122, 20/120, 10/110.
VAT_STANDARD_FROM = date(2026, 1, 1)
VAT_RATE_STANDARD = Decimal("22")
VAT_RATE_LEGACY = Decimal("20")  # до 31.12.2025
VAT_RATE_REDUCED = Decimal("10")
# УСН: пониженные ставки НДС 5% и 7% (для плательщиков на УСН при превышении порогов / выборе ставки).
VAT_RATE_USN_5 = Decimal("5")
VAT_RATE_USN_7 = Decimal("7")
VAT_LAW_NOTE = (
    "С 01.01.2026 основная ставка НДС — 22% (ФЗ № 425-ФЗ от 28.11.2025; п. 3 ст. 164 НК РФ). "
    "Ключевой критерий — дата отгрузки/оказания услуг, а не дата договора. "
    "Льготная 10% (п. 2 ст. 164) и 0% сохранены; для части УСН — 5% и 7% "
    "(вычеты входного НДС при 5%/7% по общему правилу недоступны). "
    "Письмо ФНС от 29.12.2025 № СД-4-3/11802@; разъяснения ФНС о переходе на 22%."
)

# НДФЛ: прогрессия с 01.01.2025 (ФЗ № 176-ФЗ), действует в 2026 (п. 1 ст. 224 НК РФ).
# Пороги — верхние границы ступеней основной налоговой базы (резидент).
NDFL_BRACKETS: list[tuple[Decimal | None, Decimal]] = [
    (Decimal("2400000"), Decimal("0.13")),
    (Decimal("5000000"), Decimal("0.15")),
    (Decimal("20000000"), Decimal("0.18")),
    (Decimal("50000000"), Decimal("0.20")),
    (None, Decimal("0.22")),
]
NDFL_LAW_NOTE = (
    "Прогрессивная шкала основной базы (ст. 224 НК РФ, с 2025 г.): "
    "13% до 2,4 млн; 15% 2,4–5 млн; 18% 5–20 млн; 20% 20–50 млн; 22% свыше 50 млн. "
    "Повышенная ставка — только на сумму превышения. Без учёта вычетов и особых баз (дивиденды и т.п.)."
)

# Страховые взносы 2026: единый тариф 30% / 15,1% сверх предельной базы 2 979 000 ₽
# (Постановление Правительства РФ от 31.10.2025 № 1705; ст. 421, 425 НК РФ).
CONTRIB_BASE_LIMIT_2026 = Decimal("2979000")
CONTRIB_RATE_WITHIN = Decimal("30")
CONTRIB_RATE_OVER = Decimal("15.1")
CONTRIB_LAW_NOTE = (
    "2026: единый тариф 30% в пределах базы 2 979 000 ₽ на физлицо нарастающим итогом; "
    "15,1% с суммы превышения (Постановление Правительства № 1705 от 31.10.2025). "
    "Взносы на травматизм — отдельно, без предельной базы."
)

# ТК РФ: средний дневной заработок для отпуска — / 29,3 (ст. 139).
VACATION_AVG_DAYS = Decimal("29.3")

# Больничный: знаменатель для СДЗ — 730 (ч. 3 ст. 14 255-ФЗ).
SICK_DAY_DIVISOR = Decimal("730")


def vat_default_rate(on: date | None = None) -> Decimal:
    d = on or date.today()
    return VAT_RATE_STANDARD if d >= VAT_STANDARD_FROM else VAT_RATE_LEGACY


def vat_fraction_label(rate: Decimal) -> str:
    """Расчётная ставка вида 22/122."""
    r = rate.quantize(Decimal("1")) if rate == rate.to_integral_value() else rate
    denom = Decimal("100") + rate
    # pretty ints when possible
    if rate == rate.to_integral_value() and denom == denom.to_integral_value():
        return f"{int(rate)}/{int(denom)}"
    return f"{r}/{denom}"
