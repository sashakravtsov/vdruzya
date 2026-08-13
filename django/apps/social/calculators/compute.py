"""Accurate compute engines for the calculator suite."""
from __future__ import annotations

import math
from datetime import timedelta
from decimal import Decimal, ROUND_CEILING

from . import helpers as H
from .catalog import get_tool


def run_tool(slug: str, data: dict) -> dict:
    tool = get_tool(slug)
    if not tool:
        return H.fail("Калькулятор не найден")
    fn = globals().get(f"calc_{slug}")
    if not fn:
        return H.fail("Расчёт не реализован")
    try:
        return fn(data or {})
    except H.CalcError as exc:
        return H.fail(str(exc))
    except Exception:
        return H.fail("Не удалось выполнить расчёт — проверьте входные данные")


def _annuity_payment(principal: Decimal, rate_year: Decimal, months: int) -> tuple[Decimal, Decimal, Decimal]:
    if months <= 0:
        raise H.CalcError("Срок должен быть больше 0")
    if principal <= 0:
        raise H.CalcError("Сумма должна быть больше 0")
    if rate_year < 0:
        raise H.CalcError("Ставка не может быть отрицательной")
    if rate_year == 0:
        pay = principal / months
        return pay, principal, Decimal("0")
    r = rate_year / Decimal("100") / Decimal("12")
    factor = (1 + r) ** months
    pay = principal * r * factor / (factor - 1)
    total = pay * months
    return pay, total, total - principal


def calc_vacation(data):
    earn = H.D(data.get("earnings_12m"))
    days = H.D(data.get("days"))
    months = H.D(data.get("months_worked"), "12")
    if days <= 0 or months <= 0:
        raise H.CalcError("Дни и месяцы должны быть > 0")
    if months > 12:
        months = Decimal("12")
    avg_day = earn / months / Decimal("29.3")
    pay = avg_day * days
    return H.ok(
        "Отпускные",
        [
            f"Средний дневной заработок: {H.money(avg_day)} ₽",
            f"К выплате за {H.num(days, H.TWOPLACES)} дн.: {H.money(pay)} ₽",
        ],
        ["Формула: заработок / отработанные месяцы / 29,3 × дни отпуска (ст. 139 ТК РФ)."],
    )


def calc_seniority(data):
    start = H.parse_date(data.get("start"))
    end = H.parse_date(data.get("end"), allow_empty=True) or H.today()
    if end < start:
        raise H.CalcError("Дата окончания раньше начала")
    y, m, d = H.years_months_days(start, end)
    total_days = (end - start).days
    return H.ok(
        "Трудовой стаж",
        [
            f"Период: {start.isoformat()} — {end.isoformat()}",
            f"Стаж: {y} лет {m} мес. {d} дн.",
            f"Всего календарных дней: {total_days}",
        ],
    )


def calc_age(data):
    birth = H.parse_date(data.get("birth"))
    on = H.parse_date(data.get("on_date"), allow_empty=True) or H.today()
    if on < birth:
        raise H.CalcError("Дата расчёта раньше рождения")
    y, m, d = H.years_months_days(birth, on)
    return H.ok(
        "Возраст",
        [
            f"На {on.isoformat()}: {y} лет {m} мес. {d} дн.",
            f"Полных лет: {y}",
            f"Дней с рождения: {(on - birth).days}",
        ],
    )


def calc_currency(data):
    amount = H.D(data.get("amount"))
    rate = H.D(data.get("rate"))
    if rate <= 0:
        raise H.CalcError("Курс должен быть > 0")
    mode = (data.get("mode") or "to_rub").strip()
    if mode == "from_rub":
        out = amount / rate
        return H.ok("Валюта", [f"{H.money(amount)} ₽ → {H.num(out)} (по курсу {H.num(rate)})"])
    out = amount * rate
    return H.ok("Валюта", [f"{H.num(amount)} → {H.money(out)} ₽ (по курсу {H.num(rate)})"])


def calc_days(data):
    mode = (data.get("mode") or "between").strip()
    start = H.parse_date(data.get("start"))
    inclusive = (data.get("inclusive") or "0") == "1"
    if mode == "between":
        end = H.parse_date(data.get("end"))
        delta = abs((end - start).days)
        if inclusive:
            delta += 1
        return H.ok("Дни между датами", [f"{delta} дн.", f"{start.isoformat()} … {end.isoformat()}"])
    n = int(H.D(data.get("n_days")))
    if mode == "sub":
        n = -n
    result = start + timedelta(days=n)
    return H.ok("Дата ± дни", [f"Результат: {result.isoformat()}", f"Сдвиг: {n:+d} дн. от {start.isoformat()}"])


def calc_credit(data):
    principal = H.D(data.get("principal"))
    rate = H.D(data.get("rate_year"))
    months = int(H.D(data.get("months")))
    pay, total, over = _annuity_payment(principal, rate, months)
    return H.ok(
        "Кредит (аннуитет)",
        [
            f"Ежемесячный платёж: {H.money(pay)} ₽",
            f"Всего выплат: {H.money(total)} ₽",
            f"Переплата: {H.money(over)} ₽",
        ],
    )


def calc_sick(data):
    earn = H.D(data.get("earnings_2y"))
    days = H.D(data.get("days"))
    years = H.D(data.get("seniority_years"))
    if days <= 0:
        raise H.CalcError("Дни должны быть > 0")
    if years < 5:
        pct = Decimal("60")
    elif years < 8:
        pct = Decimal("80")
    else:
        pct = Decimal("100")
    avg = earn / Decimal("730")
    benefit = avg * days * pct / Decimal("100")
    return H.ok(
        "Больничный",
        [
            f"СДЗ: {H.money(avg)} ₽",
            f"% оплаты по стажу: {H.num(pct, H.TWOPLACES)}%",
            f"Пособие: {H.money(benefit)} ₽",
        ],
        ["Без учёта предельной базы ФСС/СФР и районных коэффициентов — ориентир для оценки."],
    )


def calc_vat(data):
    amount = H.D(data.get("amount"))
    rate = H.D(data.get("rate"), "20")
    mode = (data.get("mode") or "extract").strip()
    if rate < 0:
        raise H.CalcError("Ставка некорректна")
    if mode == "add":
        vat = amount * rate / Decimal("100")
        total = amount + vat
        return H.ok("НДС начислен", [f"НДС: {H.money(vat)} ₽", f"Сумма с НДС: {H.money(total)} ₽"])
    vat = amount * rate / (Decimal("100") + rate)
    net = amount - vat
    return H.ok("НДС выделен", [f"НДС: {H.money(vat)} ₽", f"Без НДС: {H.money(net)} ₽"])


def calc_mortgage(data):
    principal = H.D(data.get("principal"))
    down = H.D(data.get("down"), "0")
    loan = principal - down
    if loan <= 0:
        raise H.CalcError("Сумма кредита после взноса должна быть > 0")
    rate = H.D(data.get("rate_year"))
    months = int(H.D(data.get("months")))
    pay, total, over = _annuity_payment(loan, rate, months)
    return H.ok(
        "Ипотека",
        [
            f"Тело кредита: {H.money(loan)} ₽",
            f"Ежемесячный платёж: {H.money(pay)} ₽",
            f"Всего выплат: {H.money(total)} ₽",
            f"Переплата: {H.money(over)} ₽",
        ],
    )


def calc_percent(data):
    mode = (data.get("mode") or "of").strip()
    a = H.D(data.get("a"))
    b = H.D(data.get("b"))
    if mode == "of":
        return H.ok("Процент от числа", [f"{H.num(a)}% от {H.num(b)} = {H.num(b * a / 100)}"])
    if mode == "what":
        if b == 0:
            raise H.CalcError("Деление на ноль")
        return H.ok("Доля в %", [f"{H.num(a)} составляет {H.num(a * 100 / b)}% от {H.num(b)}"])
    if b == 0:
        raise H.CalcError("Деление на ноль")
    return H.ok("Изменение %", [f"Изменение {H.num(a)} → {H.num(b)}: {H.num((b - a) * 100 / a)}%"])


def calc_severance(data):
    avg = H.D(data.get("avg_month"))
    unused = H.D(data.get("unused_days"), "0")
    months = H.D(data.get("severance_months"), "1")
    day = avg / Decimal("29.3")
    vac = day * unused
    sev = avg * months
    total = vac + sev
    return H.ok(
        "Компенсация при увольнении",
        [
            f"Компенсация отпуска: {H.money(vac)} ₽",
            f"Выходное пособие: {H.money(sev)} ₽",
            f"Итого оценка: {H.money(total)} ₽",
        ],
        ["Фактический размер зависит от основания увольнения и локальных актов."],
    )


def calc_penalty(data):
    amount = H.D(data.get("amount"))
    days = H.D(data.get("days"))
    base = H.D(data.get("base"), "365")
    rate_year = H.D(data.get("rate_year"), "0")
    if days < 0 or amount < 0:
        raise H.CalcError("Сумма и дни не могут быть отрицательными")
    if rate_year > 0:
        pen = amount * rate_year * days / base / Decimal("100")
        note = f"годовая {H.num(rate_year)}% / {H.num(base, H.TWOPLACES)}"
    else:
        rate_day = H.D(data.get("rate_day"))
        pen = amount * rate_day * days / Decimal("100")
        note = f"{H.num(rate_day)}% в день"
    return H.ok("Пени", [f"Пени: {H.money(pen)} ₽", f"Параметры: {note}, {H.num(days, H.TWOPLACES)} дн."])


_LENGTH = {
    "mm": Decimal("0.001"), "cm": Decimal("0.01"), "m": Decimal("1"), "km": Decimal("1000"),
    "in": Decimal("0.0254"), "ft": Decimal("0.3048"), "yd": Decimal("0.9144"), "mi": Decimal("1609.344"),
}
_MASS = {
    "g": Decimal("0.001"), "kg": Decimal("1"), "t": Decimal("1000"),
    "lb": Decimal("0.45359237"), "oz": Decimal("0.028349523125"),
}
_VOLUME = {
    "ml": Decimal("0.000001"), "l": Decimal("0.001"), "m3": Decimal("1"),
}


def _convert(value: Decimal, frm: str, to: str, table: dict) -> Decimal:
    f = (frm or "").strip().lower()
    t = (to or "").strip().lower()
    if f not in table or t not in table:
        raise H.CalcError(f"Неизвестные единицы: {frm} → {to}")
    return value * table[f] / table[t]


def calc_units(data):
    kind = (data.get("kind") or "length").strip()
    value = H.D(data.get("value"))
    table = {"length": _LENGTH, "mass": _MASS, "volume": _VOLUME}.get(kind)
    if not table:
        raise H.CalcError("Неизвестный тип величины")
    out = _convert(value, data.get("frm"), data.get("to"), table)
    return H.ok("Конвертер", [f"{H.num(value)} {data.get('frm')} = {H.num(out)} {data.get('to')}"])


def calc_area(data):
    shape = (data.get("shape") or "rect").strip()
    a = H.D(data.get("a"))
    b = H.D(data.get("b"), "0")
    if shape == "rect":
        if a <= 0 or b <= 0:
            raise H.CalcError("Стороны должны быть > 0")
        area = a * b
    elif shape == "circle":
        if a <= 0:
            raise H.CalcError("Радиус должен быть > 0")
        area = Decimal(str(math.pi)) * a * a
    else:
        if a <= 0 or b <= 0:
            raise H.CalcError("Основание и высота должны быть > 0")
        area = a * b / 2
    return H.ok("Площадь", [f"{H.num(area)} м²"])


def calc_volume(data):
    shape = (data.get("shape") or "box").strip()
    a = H.D(data.get("a"))
    b = H.D(data.get("b"), "0")
    c = H.D(data.get("c"), "0")
    pi = Decimal(str(math.pi))
    if shape == "box":
        if min(a, b, c) <= 0:
            raise H.CalcError("Все размеры должны быть > 0")
        vol = a * b * c
    elif shape == "cylinder":
        if a <= 0 or c <= 0:
            raise H.CalcError("Радиус и высота должны быть > 0")
        vol = pi * a * a * c
    else:
        if a <= 0:
            raise H.CalcError("Радиус должен быть > 0")
        vol = Decimal("4") / Decimal("3") * pi * a ** 3
    return H.ok("Объём", [f"{H.num(vol)} м³"])


def calc_calories(data):
    sex = (data.get("sex") or "m").strip()
    age = H.D(data.get("age"))
    h = H.D(data.get("height_cm"))
    w = H.D(data.get("weight_kg"))
    act = H.D(data.get("activity"), "1.375")
    if min(age, h, w) <= 0:
        raise H.CalcError("Параметры должны быть > 0")
    # Mifflin–St Jeor
    bmr = Decimal("10") * w + Decimal("6.25") * h - Decimal("5") * age
    bmr += Decimal("5") if sex == "m" else Decimal("-161")
    tdee = bmr * act
    # rough macros for maintenance: 30% p / 30% f / 40% c
    protein_g = tdee * Decimal("0.30") / Decimal("4")
    fat_g = tdee * Decimal("0.30") / Decimal("9")
    carb_g = tdee * Decimal("0.40") / Decimal("4")
    return H.ok(
        "Калории / КБЖУ",
        [
            f"BMR: {H.num(bmr, H.TWOPLACES)} ккал/сут",
            f"TDEE: {H.num(tdee, H.TWOPLACES)} ккал/сут",
            f"Ориентир КБЖУ: Б {H.num(protein_g, H.TWOPLACES)} г · Ж {H.num(fat_g, H.TWOPLACES)} г · У {H.num(carb_g, H.TWOPLACES)} г",
        ],
        ["Формула Mifflin–St Jeor; КБЖУ — примерное распределение 30/30/40."],
    )


def calc_weight(data):
    out = _convert(H.D(data.get("value")), data.get("frm"), data.get("to"), _MASS)
    return H.ok("Масса", [f"{H.num(H.D(data.get('value')))} {data.get('frm')} = {H.num(out)} {data.get('to')}"])


def calc_bmi(data):
    w = H.D(data.get("weight_kg"))
    h_cm = H.D(data.get("height_cm"))
    if w <= 0 or h_cm <= 0:
        raise H.CalcError("Вес и рост должны быть > 0")
    h = h_cm / Decimal("100")
    bmi = w / (h * h)
    if bmi < 18.5:
        cat = "недостаточный вес"
    elif bmi < 25:
        cat = "норма"
    elif bmi < 30:
        cat = "избыточный вес"
    else:
        cat = "ожирение"
    return H.ok("ИМТ", [f"ИМТ: {H.num(bmi)}", f"Категория: {cat}"])


def calc_moonshine(data):
    v = H.D(data.get("volume"))
    c1 = H.D(data.get("from_abv"))
    c2 = H.D(data.get("to_abv"))
    if min(v, c1, c2) <= 0 or c2 >= c1 or c1 > 100 or c2 > 100:
        raise H.CalcError("Проверьте объём и крепости (цель < исходной, ≤100%)")
    water = v * (c1 / c2 - 1)
    total = v + water
    return H.ok(
        "Разбавление спирта",
        [
            f"Добавить воды: {H.num(water)} л",
            f"Итоговый объём: {H.num(total)} л при {H.num(c2)}%",
        ],
        ["Без температурной поправки на сжатие смеси."],
    )


def calc_early_payoff(data):
    principal = H.D(data.get("principal"))
    rate = H.D(data.get("rate_year"))
    months = int(H.D(data.get("months_left")))
    extra = H.D(data.get("extra"))
    pay, total, _ = _annuity_payment(principal, rate, months)
    new_principal = principal - extra
    if new_principal <= 0:
        return H.ok("Досрочное погашение", ["Досрочный платёж полностью закрывает долг.", f"Было к выплате: {H.money(total)} ₽"])
    # keep payment, reduce term
    if rate == 0:
        new_months = int((new_principal / pay).to_integral_value(rounding=ROUND_CEILING))
    else:
        r = rate / Decimal("100") / Decimal("12")
        # n = log(pay/(pay - new_principal*r)) / log(1+r)
        denom = pay - new_principal * r
        if denom <= 0:
            raise H.CalcError("Платёж слишком мал для остатка долга")
        new_months = int(math.ceil(math.log(float(pay / denom)) / math.log(float(1 + r))))
    new_total = pay * new_months + extra
    save = total - new_total
    return H.ok(
        "Досрочное погашение",
        [
            f"Текущий платёж: {H.money(pay)} ₽",
            f"Новый срок: {new_months} мес. (было {months})",
            f"Экономия: {H.money(save)} ₽",
        ],
        ["Сценарий: уменьшение срока при том же аннуитете."],
    )


def calc_salary(data):
    amount = H.D(data.get("amount"))
    rate = H.D(data.get("rate"), "13")
    mode = (data.get("mode") or "gross_to_net").strip()
    if rate < 0 or rate >= 100:
        raise H.CalcError("Ставка НДФЛ некорректна")
    if mode == "net_to_gross":
        gross = amount / (1 - rate / 100)
        tax = gross - amount
        return H.ok("Зарплата", [f"Оклад (gross): {H.money(gross)} ₽", f"НДФЛ: {H.money(tax)} ₽"])
    tax = amount * rate / 100
    net = amount - tax
    return H.ok("Зарплата", [f"На руки: {H.money(net)} ₽", f"НДФЛ: {H.money(tax)} ₽"])


def calc_deposit(data):
    p = H.D(data.get("principal"))
    rate = H.D(data.get("rate_year"))
    months = int(H.D(data.get("months")))
    compound = (data.get("compound") or "1") == "1"
    if months <= 0 or p < 0:
        raise H.CalcError("Проверьте сумму и срок")
    if compound:
        r = rate / Decimal("100") / Decimal("12")
        final = p * ((1 + r) ** months)
    else:
        final = p * (1 + rate / Decimal("100") * Decimal(months) / Decimal("12"))
    return H.ok(
        "Вклад",
        [
            f"Итого: {H.money(final)} ₽",
            f"Доход: {H.money(final - p)} ₽",
        ],
    )


def calc_egfr(data):
    sex = (data.get("sex") or "f").strip()
    age = float(H.D(data.get("age")))
    creat_umol = float(H.D(data.get("creatinine")))
    black = (data.get("black") or "0") == "1"
    if age <= 0 or creat_umol <= 0:
        raise H.CalcError("Возраст и креатинин должны быть > 0")
    creat = creat_umol / 88.4  # to mg/dL
    if sex == "f":
        kappa, alpha, sex_f = 0.7, -0.329, 1.018
    else:
        kappa, alpha, sex_f = 0.9, -0.411, 1.0
    min_scr = min(creat / kappa, 1.0)
    max_scr = max(creat / kappa, 1.0)
    egfr = 141 * (min_scr ** alpha) * (max_scr ** -1.209) * (0.993 ** age) * sex_f
    if black:
        egfr *= 1.159
    return H.ok(
        "СКФ (CKD-EPI 2009)",
        [f"eGFR: {egfr:.1f} мл/мин/1,73 м²"],
        ["Не заменяет заключение врача; единицы креатинина — мкмоль/л."],
    )


def calc_roof(data):
    length = H.D(data.get("length"))
    width = H.D(data.get("width"))
    pitch = float(H.D(data.get("pitch_deg")))
    overhang = H.D(data.get("overhang"), "0")
    waste = H.D(data.get("waste"), "0")
    if min(length, width) <= 0 or pitch <= 0 or pitch >= 90:
        raise H.CalcError("Проверьте размеры и угол (0–90°)")
    slope = Decimal(str(1 / math.cos(math.radians(pitch))))
    L = length + 2 * overhang
    W = width + 2 * overhang
    area = L * (W / 2) * slope * 2
    with_waste = area * (1 + waste / 100)
    return H.ok(
        "Кровля",
        [
            f"Площадь скатов: {H.num(area)} м²",
            f"С запасом {H.num(waste, H.TWOPLACES)}%: {H.num(with_waste)} м²",
        ],
    )


def calc_time(data):
    mode = (data.get("mode") or "add").strip()
    h1, m1 = int(H.D(data.get("h1"), "0")), int(H.D(data.get("m1"), "0"))
    h2, m2 = int(H.D(data.get("h2"), "0")), int(H.D(data.get("m2"), "0"))
    t1 = h1 * 60 + m1
    t2 = h2 * 60 + m2
    if mode == "to_min":
        return H.ok("В минуты", [f"{h1}:{m1:02d} = {t1} мин."])
    if mode == "from_min":
        total = int(H.D(data.get("total_min")))
        if total < 0:
            raise H.CalcError("Минуты не могут быть отрицательными")
        return H.ok("Из минут", [f"{total} мин. = {total // 60}:{total % 60:02d}"])
    res = t1 + t2 if mode == "add" else t1 - t2
    sign = "-" if res < 0 else ""
    res_abs = abs(res)
    return H.ok("Время", [f"Результат: {sign}{res_abs // 60}:{res_abs % 60:02d}", f"({res} мин.)"])


def calc_cylinder(data):
    r = H.D(data.get("radius"))
    h = H.D(data.get("height"))
    if r <= 0 or h <= 0:
        raise H.CalcError("Радиус и высота должны быть > 0")
    pi = Decimal(str(math.pi))
    vol = pi * r * r * h
    side = 2 * pi * r * h
    total = side + 2 * pi * r * r
    return H.ok("Цилиндр", [f"Объём: {H.num(vol)} м³", f"Площадь боковой: {H.num(side)} м²", f"Полная поверхность: {H.num(total)} м²"])


def calc_pregnancy(data):
    lmp = H.parse_date(data.get("lmp"))
    cycle = int(H.D(data.get("cycle"), "28"))
    if cycle < 20 or cycle > 45:
        raise H.CalcError("Длина цикла обычно 20–45 дней")
    # Naegele adjusted for cycle length
    edd = lmp + timedelta(days=280 + (cycle - 28))
    today = H.today()
    weeks = (today - lmp).days // 7
    days = (today - lmp).days % 7
    return H.ok(
        "ПДР",
        [
            f"Предполагаемая дата родов: {edd.isoformat()}",
            f"Срок на сегодня: {weeks} нед. {days} дн.",
        ],
        ["Формула Негеле — ориентир, уточняет врач."],
    )


def calc_pipe(data):
    od = H.D(data.get("od_mm")) / 1000
    wall = H.D(data.get("wall_mm")) / 1000
    length = H.D(data.get("length_m"), "1")
    density = H.D(data.get("density"), "7850")
    if wall * 2 >= od or min(od, wall, length, density) <= 0:
        raise H.CalcError("Проверьте диаметр и толщину стенки")
    id_ = od - 2 * wall
    pi = Decimal(str(math.pi))
    inner_vol = pi * (id_ / 2) ** 2 * length
    metal_vol = pi * ((od / 2) ** 2 - (id_ / 2) ** 2) * length
    mass = metal_vol * density
    return H.ok(
        "Труба",
        [
            f"Внутренний объём: {H.num(inner_vol)} м³",
            f"Масса: {H.num(mass)} кг",
        ],
    )


def calc_fuel(data):
    mode = (data.get("mode") or "trip").strip()
    dist = H.D(data.get("distance_km"), "0")
    cons = H.D(data.get("l_per_100"), "0")
    price = H.D(data.get("price"), "0")
    if mode == "consumption":
        used = H.D(data.get("fuel_used"))
        if dist <= 0 or used < 0:
            raise H.CalcError("Проверьте дистанцию и расход топлива")
        l100 = used * 100 / dist
        return H.ok("Расход", [f"{H.num(l100)} л/100 км"])
    if mode == "range":
        tank = H.D(data.get("tank_l"))
        if cons <= 0 or tank <= 0:
            raise H.CalcError("Проверьте расход и объём бака")
        rng = tank * 100 / cons
        return H.ok("Запас хода", [f"≈ {H.num(rng)} км"])
    if dist < 0 or cons < 0 or price < 0:
        raise H.CalcError("Значения не могут быть отрицательными")
    liters = dist * cons / 100
    cost = liters * price
    return H.ok("Поездка", [f"Топливо: {H.num(liters)} л", f"Стоимость: {H.money(cost)} ₽"])


def calc_triangle(data):
    a, b, c = H.D(data.get("a")), H.D(data.get("b")), H.D(data.get("c"))
    if min(a, b, c) <= 0 or a + b <= c or a + c <= b or b + c <= a:
        raise H.CalcError("Стороны не образуют треугольник")
    s = (a + b + c) / 2
    area = (s * (s - a) * (s - b) * (s - c)).sqrt()
    # angles via cosine law
    def ang(x, y, z):
        cosv = float((x * x + y * y - z * z) / (2 * x * y))
        cosv = max(-1.0, min(1.0, cosv))
        return math.degrees(math.acos(cosv))
    A, B, C = ang(b, c, a), ang(a, c, b), ang(a, b, c)
    return H.ok(
        "Треугольник",
        [
            f"Площадь: {H.num(area)}",
            f"Углы: A={A:.2f}° · B={B:.2f}° · C={C:.2f}°",
            f"Периметр: {H.num(a + b + c)}",
        ],
    )


def calc_ndfl(data):
    income = H.D(data.get("income"))
    if income < 0:
        raise H.CalcError("База не может быть отрицательной")
    # Progressive RU personal income tax brackets (2025+)
    brackets = [
        (Decimal("2400000"), Decimal("0.13")),
        (Decimal("5000000"), Decimal("0.15")),
        (Decimal("20000000"), Decimal("0.18")),
        (Decimal("50000000"), Decimal("0.20")),
        (None, Decimal("0.22")),
    ]
    tax = Decimal("0")
    prev = Decimal("0")
    for cap, rate in brackets:
        chunk_top = income if cap is None else min(income, cap)
        if chunk_top <= prev:
            break
        tax += (chunk_top - prev) * rate
        prev = chunk_top
        if cap is None or income <= cap:
            break
    effective = (tax * 100 / income) if income else Decimal("0")
    return H.ok(
        "НДФЛ (прогрессия)",
        [
            f"Налог: {H.money(tax)} ₽",
            f"На руки: {H.money(income - tax)} ₽",
            f"Эффективная ставка: {H.num(effective)}%",
        ],
        ["Упрощённый расчёт по годовым порогам 13/15/18/20/22% без вычетов и особых баз."],
    )


def calc_tax_simple(data):
    mode = (data.get("mode") or "income").strip()
    income = H.D(data.get("income"))
    expense = H.D(data.get("expense"), "0")
    if mode == "income":
        tax = income * Decimal("0.06")
        return H.ok("УСН доходы 6%", [f"Налог: {H.money(tax)} ₽"], ["Без учёта страховых взносов к вычету."])
    base = income - expense
    if base < 0:
        base = Decimal("0")
    tax = base * Decimal("0.15")
    min_tax = income * Decimal("0.01")
    applied = max(tax, min_tax)
    return H.ok(
        "УСН доходы−расходы 15%",
        [
            f"База: {H.money(base)} ₽",
            f"Налог 15%: {H.money(tax)} ₽",
            f"Мин. налог 1%: {H.money(min_tax)} ₽",
            f"К уплате (оценка): {H.money(applied)} ₽",
        ],
    )


def calc_length(data):
    out = _convert(H.D(data.get("value")), data.get("frm"), data.get("to"), _LENGTH)
    return H.ok("Длина", [f"{H.num(H.D(data.get('value')))} {data.get('frm')} = {H.num(out)} {data.get('to')}"])


def calc_pension(data):
    ipk = H.D(data.get("ipk"))
    point = H.D(data.get("point_value"))
    fixed = H.D(data.get("fixed"))
    if ipk < 0 or point < 0 or fixed < 0:
        raise H.CalcError("Параметры не могут быть отрицательными")
    total = ipk * point + fixed
    return H.ok("Пенсия (оценка)", [f"Страховая пенсия: {H.money(total)} ₽/мес."], ["Параметры балла и фикса вводите актуальные на год расчёта."])


def calc_loan(data):
    p = H.D(data.get("principal"))
    rate = H.D(data.get("rate_year"))
    days = H.D(data.get("days"))
    if min(p, days) <= 0:
        raise H.CalcError("Сумма и срок должны быть > 0")
    interest = p * rate * days / Decimal("365") / Decimal("100")
    return H.ok("Займ", [f"Проценты: {H.money(interest)} ₽", f"К возврату: {H.money(p + interest)} ₽"])


def calc_benefits(data):
    avg = H.D(data.get("avg_day"))
    days = H.D(data.get("days"))
    coeff = H.D(data.get("coeff"), "1")
    if days < 0 or avg < 0 or coeff < 0:
        raise H.CalcError("Значения не могут быть отрицательными")
    return H.ok("Пособие", [f"К выплате: {H.money(avg * days * coeff)} ₽"])


def calc_tires(data):
    width = H.D(data.get("width"))
    aspect = H.D(data.get("aspect"))
    rim = H.D(data.get("rim"))
    if min(width, aspect, rim) <= 0:
        raise H.CalcError("Параметры шины должны быть > 0")
    sidewall = width * aspect / 100
    diameter_mm = rim * Decimal("25.4") + 2 * sidewall
    circ = Decimal(str(math.pi)) * diameter_mm
    return H.ok(
        "Шина",
        [
            f"Внешний диаметр: {H.num(diameter_mm)} мм ({H.num(diameter_mm / 25.4)}″)",
            f"Окружность: {H.num(circ)} мм",
            f"Высота профиля: {H.num(sidewall)} мм",
        ],
    )


def calc_circle(data):
    mode = (data.get("mode") or "r").strip()
    value = H.D(data.get("value"))
    if value <= 0:
        raise H.CalcError("Значение должно быть > 0")
    r = value if mode == "r" else value / 2
    pi = Decimal(str(math.pi))
    return H.ok("Круг", [f"Длина окружности: {H.num(2 * pi * r)}", f"Площадь: {H.num(pi * r * r)}"])


def calc_metal(data):
    shape = (data.get("shape") or "sheet").strip()
    a = H.D(data.get("a")) / 1000  # mm -> m
    b = H.D(data.get("b")) / 1000
    c = H.D(data.get("c"), "1") / 1000
    density = H.D(data.get("density"), "7.85") * 1000  # g/cm3 -> kg/m3
    pi = Decimal(str(math.pi))
    if shape == "sheet":
        if min(a, b, c) <= 0:
            raise H.CalcError("Размеры листа должны быть > 0")
        vol = a * b * c
    elif shape == "bar":
        if min(a, b) <= 0:
            raise H.CalcError("Длина и диаметр должны быть > 0")
        vol = pi * (b / 2) ** 2 * a
    else:
        if c * 2 >= b or min(a, b, c) <= 0:
            raise H.CalcError("Проверьте диаметр и стенку трубы")
        vol = pi * ((b / 2) ** 2 - ((b - 2 * c) / 2) ** 2) * a
    mass = vol * density
    return H.ok("Металл", [f"Масса: {H.num(mass)} кг", f"Объём металла: {H.num(vol)} м³"])


def calc_alcohol(data):
    sex = (data.get("sex") or "m").strip()
    weight = H.D(data.get("weight_kg"))
    ml = H.D(data.get("ml"))
    abv = H.D(data.get("abv"))
    hours = H.D(data.get("hours"), "0")
    if min(weight, ml, abv) <= 0:
        raise H.CalcError("Параметры должны быть > 0")
    alcohol_g = ml * abv / 100 * Decimal("0.789")
    r = Decimal("0.68") if sex == "m" else Decimal("0.55")
    bac = alcohol_g / (weight * r) - Decimal("0.15") * hours
    if bac < 0:
        bac = Decimal("0")
    return H.ok(
        "Оценка промилле",
        [f"≈ {H.num(bac)} ‰"],
        ["Формула Видмарка — грубая оценка, не для медосвидетельствования и вождения."],
    )


def calc_osago(data):
    coeffs = [H.D(data.get(k), "1") for k in ("tb", "kt", "kbm", "kvs", "ko", "km", "ks")]
    premium = Decimal("1")
    for c in coeffs:
        if c < 0:
            raise H.CalcError("Коэффициенты не могут быть отрицательными")
        premium *= c
    return H.ok("ОСАГО (оценка)", [f"Премия: {H.money(premium)} ₽"], ["Произведение ТБ и коэффициентов; сверьте с актуальным тарифом страховщика."])


def calc_deadlines(data):
    start = H.parse_date(data.get("start"))
    days = int(H.D(data.get("days")))
    kind = (data.get("kind") or "calendar").strip()
    direction = (data.get("direction") or "forward").strip()
    signed = days if direction == "forward" else -days
    if kind == "business":
        result = H.add_business_days(start, signed)
    else:
        result = start + timedelta(days=signed)
    return H.ok("Срок", [f"Итоговая дата: {result.isoformat()}"], ["Рабочие дни: пн–пт, без праздников РФ."])


def calc_expiry(data):
    produced = H.parse_date(data.get("produced"))
    shelf = int(H.D(data.get("shelf_days")))
    if shelf < 0:
        raise H.CalcError("Срок не может быть отрицательным")
    expires = produced + timedelta(days=shelf)
    left = (expires - H.today()).days
    return H.ok(
        "Срок годности",
        [
            f"Годен до: {expires.isoformat()}",
            f"Осталось дней: {left}" if left >= 0 else f"Просрочено на {-left} дн.",
        ],
    )


def calc_contributions(data):
    payroll = H.D(data.get("payroll"))
    ops = H.D(data.get("ops"), "22")
    oms = H.D(data.get("oms"), "5.1")
    vnim = H.D(data.get("vnim"), "2.9")
    parts = [
        ("ОПС", payroll * ops / 100),
        ("ОМС", payroll * oms / 100),
        ("ВНиМ", payroll * vnim / 100),
    ]
    total = sum((p for _, p in parts), Decimal("0"))
    lines = [f"{name}: {H.money(val)} ₽" for name, val in parts]
    lines.append(f"Итого: {H.money(total)} ₽")
    return H.ok("Страховые взносы", lines, ["Без учёта предельных баз и льготных тарифов."])


def calc_stairs(data):
    height = H.D(data.get("height_m")) * 1000
    riser = H.D(data.get("riser_mm"))
    tread = H.D(data.get("tread_mm"))
    if min(height, riser, tread) <= 0:
        raise H.CalcError("Параметры должны быть > 0")
    steps = int(math.ceil(float(height / riser)))
    actual_riser = height / steps
    run = tread * (steps - 1)
    stringer = Decimal(str(math.hypot(float(run), float(height))))
    return H.ok(
        "Лестница",
        [
            f"Ступеней: {steps}",
            f"Высота ступени: {H.num(actual_riser)} мм",
            f"Горизонтальная проекция: {H.num(run)} мм",
            f"Длина косоура: {H.num(stringer)} мм",
        ],
    )


def calc_nmck(data):
    prices = [H.D(data.get("p1")), H.D(data.get("p2"))]
    p3 = H.D(data.get("p3"), "0")
    if p3 > 0:
        prices.append(p3)
    qty = H.D(data.get("qty"), "1")
    if qty <= 0 or any(p <= 0 for p in prices):
        raise H.CalcError("Цены и количество должны быть > 0")
    avg = sum(prices) / len(prices)
    return H.ok(
        "НМЦК",
        [
            f"Средняя цена ед.: {H.money(avg)} ₽",
            f"НМЦК на {H.num(qty)}: {H.money(avg * qty)} ₽",
        ],
        ["Метод сопоставимых рыночных цен (упрощённо)."],
    )


def calc_contract(data):
    amount = H.D(data.get("amount"))
    vat_rate = H.D(data.get("vat_rate"), "20")
    months = int(H.D(data.get("months"), "1"))
    if months <= 0:
        raise H.CalcError("Срок должен быть > 0")
    vat = amount * vat_rate / 100
    total = amount + vat
    monthly = total / months
    return H.ok(
        "Договор",
        [
            f"НДС: {H.money(vat)} ₽",
            f"Всего с НДС: {H.money(total)} ₽",
            f"В месяц: {H.money(monthly)} ₽",
        ],
    )


def calc_floor(data):
    length = H.D(data.get("length"))
    width = H.D(data.get("width"))
    pack = H.D(data.get("pack_m2"))
    waste = H.D(data.get("waste"), "0")
    if min(length, width, pack) <= 0:
        raise H.CalcError("Размеры и упаковка должны быть > 0")
    area = length * width
    need = area * (1 + waste / 100)
    packs = int(math.ceil(float(need / pack)))
    return H.ok("Пол", [f"Площадь: {H.num(area)} м²", f"С запасом: {H.num(need)} м²", f"Упаковок: {packs}"])


def calc_cycle(data):
    lmp = H.parse_date(data.get("lmp"))
    cycle = int(H.D(data.get("cycle"), "28"))
    period = int(H.D(data.get("period_len"), "5"))
    if cycle < 20 or cycle > 45 or period < 1 or period > 14:
        raise H.CalcError("Проверьте длину цикла и менструации")
    next_m = lmp + timedelta(days=cycle)
    ovulation = next_m - timedelta(days=14)
    fertile_from = ovulation - timedelta(days=5)
    fertile_to = ovulation + timedelta(days=1)
    return H.ok(
        "Цикл",
        [
            f"Следующие месячные: {next_m.isoformat()}",
            f"Овуляция (оценка): {ovulation.isoformat()}",
            f"Фертильное окно: {fertile_from.isoformat()} — {fertile_to.isoformat()}",
            f"Конец текущей менструации: {(lmp + timedelta(days=period - 1)).isoformat()}",
        ],
        ["Ориентир, не метод контрацепции."],
    )


def calc_walls(data):
    length = H.D(data.get("length"))
    width = H.D(data.get("width"))
    height = H.D(data.get("height"))
    openings = H.D(data.get("openings"), "0")
    if min(length, width, height) <= 0:
        raise H.CalcError("Размеры должны быть > 0")
    area = 2 * (length + width) * height - openings
    if area < 0:
        raise H.CalcError("Площадь проёмов больше площади стен")
    return H.ok("Стены", [f"Площадь стен: {H.num(area)} м²"])
