
"""Catalog of Wordstat top-50 calculators (RU demand, 2026)."""
from __future__ import annotations

from typing import Any

# slug, name, topic, blurb, fields: list[{name,label,type,default?,choices?,hint?}]
TOOLS: list[dict[str, Any]] = [
    {
        "slug": "vacation",
        "name": "Отпускные",
        "topic": "HR / бухгалтерия",
        "blurb": "Средний дневной заработок × дни отпуска (ст. 139 ТК РФ, коэф. 29,3).",
        "fields": [
            {"name": "earnings_12m", "label": "Заработок за 12 мес., ₽", "type": "money"},
            {"name": "days", "label": "Дней отпуска", "type": "number", "default": "14"},
            {"name": "months_worked", "label": "Отработано полных месяцев", "type": "number", "default": "12", "hint": "Если меньше 12 — делим на это число"},
        ],
    },
    {
        "slug": "seniority",
        "name": "Трудовой стаж",
        "topic": "HR / бухгалтерия",
        "blurb": "Суммарный стаж между датами периодов работы.",
        "fields": [
            {"name": "start", "label": "Дата начала (ГГГГ-ММ-ДД)", "type": "date"},
            {"name": "end", "label": "Дата окончания (ГГГГ-ММ-ДД)", "type": "date", "hint": "Пусто = сегодня"},
        ],
    },
    {
        "slug": "age",
        "name": "Возраст / годы",
        "topic": "Даты / математика",
        "blurb": "Полный возраст и точная разница дат.",
        "fields": [
            {"name": "birth", "label": "Дата рождения", "type": "date"},
            {"name": "on_date", "label": "На дату (пусто = сегодня)", "type": "date", "required": False},
        ],
    },
    {
        "slug": "currency",
        "name": "Валютный калькулятор",
        "topic": "Финансы",
        "blurb": "Конвертация по курсу, который вы задаёте (без внешнего API).",
        "fields": [
            {"name": "amount", "label": "Сумма", "type": "money"},
            {"name": "rate", "label": "Курс (1 ед. → ₽ или обратно)", "type": "decimal", "default": "1"},
            {"name": "mode", "label": "Направление", "type": "choice", "choices": [("to_rub", "В рубли"), ("from_rub", "Из рублей")]},
        ],
    },
    {
        "slug": "days",
        "name": "Дни и даты",
        "topic": "Даты / математика",
        "blurb": "Число дней между датами и дата ± N дней.",
        "fields": [
            {"name": "mode", "label": "Режим", "type": "choice", "choices": [("between", "Между датами"), ("add", "Прибавить дни"), ("sub", "Вычесть дни")]},
            {"name": "start", "label": "Дата начала / база", "type": "date"},
            {"name": "end", "label": "Дата окончания (для «между»)", "type": "date", "required": False},
            {"name": "n_days", "label": "Число дней (±)", "type": "number", "default": "30", "required": False},
            {"name": "inclusive", "label": "Включить оба дня", "type": "choice", "choices": [("0", "Нет"), ("1", "Да")], "default": "0"},
        ],
    },
    {
        "slug": "credit",
        "name": "Кредит",
        "topic": "Финансы",
        "blurb": "Аннуитетный платёж и переплата (классическая формула).",
        "fields": [
            {"name": "principal", "label": "Сумма кредита, ₽", "type": "money"},
            {"name": "rate_year", "label": "Ставка, % годовых", "type": "decimal", "default": "18"},
            {"name": "months", "label": "Срок, мес.", "type": "number", "default": "36"},
        ],
    },
    {
        "slug": "sick",
        "name": "Больничный",
        "topic": "HR / бухгалтерия",
        "blurb": "Пособие = СДЗ × дни × % стажа (СДЗ = заработок за 2 года / 730).",
        "fields": [
            {"name": "earnings_2y", "label": "Заработок за 2 года, ₽", "type": "money"},
            {"name": "days", "label": "Дней нетрудоспособности", "type": "number", "default": "7"},
            {"name": "seniority_years", "label": "Стаж, полных лет", "type": "number", "default": "8", "hint": "<5 → 60%, 5–8 → 80%, ≥8 → 100%"},
        ],
    },
    {
        "slug": "vat",
        "name": "НДС",
        "topic": "Налоги / бухгалтерия",
        "blurb": "Выделить или начислить НДС (ставки 20% / 10% / 0%).",
        "fields": [
            {"name": "amount", "label": "Сумма, ₽", "type": "money"},
            {"name": "rate", "label": "Ставка, %", "type": "choice", "choices": [("20", "20%"), ("10", "10%"), ("0", "0%")], "default": "20"},
            {"name": "mode", "label": "Режим", "type": "choice", "choices": [("extract", "Выделить из суммы"), ("add", "Начислить сверху")]},
        ],
    },
    {
        "slug": "mortgage",
        "name": "Ипотека",
        "topic": "Финансы",
        "blurb": "Аннуитет по ипотеке: платёж, переплата, доля процентов.",
        "fields": [
            {"name": "principal", "label": "Сумма кредита, ₽", "type": "money"},
            {"name": "rate_year", "label": "Ставка, % годовых", "type": "decimal", "default": "16"},
            {"name": "months", "label": "Срок, мес.", "type": "number", "default": "240"},
            {"name": "down", "label": "Первый взнос, ₽ (необяз.)", "type": "money", "required": False, "default": "0"},
        ],
    },
    {
        "slug": "percent",
        "name": "Проценты",
        "topic": "Математика / финансы",
        "blurb": "Процент от числа, число от процента, разница в %.",
        "fields": [
            {"name": "mode", "label": "Режим", "type": "choice", "choices": [
                ("of", "X% от числа"), ("what", "Сколько % составляет A от B"), ("change", "Изменение A→B в %"),
            ]},
            {"name": "a", "label": "A / процент / старое", "type": "decimal"},
            {"name": "b", "label": "B / число / новое", "type": "decimal"},
        ],
    },
    {
        "slug": "severance",
        "name": "Компенсация при увольнении",
        "topic": "HR / бухгалтерия",
        "blurb": "Компенсация неиспользованного отпуска + оценка выходного пособия (1 средний месяц).",
        "fields": [
            {"name": "avg_month", "label": "Средний месячный заработок, ₽", "type": "money"},
            {"name": "unused_days", "label": "Неиспользованных дней отпуска", "type": "number", "default": "0"},
            {"name": "severance_months", "label": "Выходное пособие, мес.", "type": "decimal", "default": "1"},
        ],
    },
    {
        "slug": "penalty",
        "name": "Пени / неустойка",
        "topic": "Право / бухгалтерия",
        "blurb": "Пени = сумма × ставка/100 × дни / база (365 или 360).",
        "fields": [
            {"name": "amount", "label": "Сумма долга, ₽", "type": "money"},
            {"name": "rate_day", "label": "Ставка, % в день", "type": "decimal", "default": "0.1"},
            {"name": "days", "label": "Дней просрочки", "type": "number"},
            {"name": "base", "label": "База года", "type": "choice", "choices": [("365", "365"), ("360", "360")], "default": "365", "hint": "Если ставка годовая — укажите её и дни; формула: сумма×ставка×дни/база/100"},
            {"name": "rate_year", "label": "Или годовая ставка, % (если >0 — вместо дневной)", "type": "decimal", "default": "0", "required": False},
        ],
    },
    {
        "slug": "units",
        "name": "Конвертер величин",
        "topic": "Конвертеры",
        "blurb": "Длина, масса, объём — базовые метрические переводы.",
        "fields": [
            {"name": "kind", "label": "Величина", "type": "choice", "choices": [
                ("length", "Длина"), ("mass", "Масса"), ("volume", "Объём"),
            ]},
            {"name": "value", "label": "Значение", "type": "decimal"},
            {"name": "frm", "label": "Из", "type": "text", "default": "m", "hint": "length: mm/cm/m/km/in/ft; mass: g/kg/t/lb; volume: ml/l/m3"},
            {"name": "to", "label": "В", "type": "text", "default": "cm"},
        ],
    },
    {
        "slug": "area",
        "name": "Площадь / м²",
        "topic": "Строительство / геометрия",
        "blurb": "Площадь прямоугольника, круга или треугольника.",
        "fields": [
            {"name": "shape", "label": "Фигура", "type": "choice", "choices": [
                ("rect", "Прямоугольник"), ("circle", "Круг"), ("triangle", "Треугольник"),
            ]},
            {"name": "a", "label": "Длина / радиус / сторона a, м", "type": "decimal"},
            {"name": "b", "label": "Ширина / высота, м", "type": "decimal", "required": False, "default": "0"},
        ],
    },
    {
        "slug": "volume",
        "name": "Объём / м³",
        "topic": "Строительство / геометрия",
        "blurb": "Объём прямоугольного параллелепипеда, цилиндра или сферы.",
        "fields": [
            {"name": "shape", "label": "Фигура", "type": "choice", "choices": [
                ("box", "Параллелепипед"), ("cylinder", "Цилиндр"), ("sphere", "Сфера"),
            ]},
            {"name": "a", "label": "Длина / радиус, м", "type": "decimal"},
            {"name": "b", "label": "Ширина, м", "type": "decimal", "required": False, "default": "0"},
            {"name": "c", "label": "Высота, м", "type": "decimal", "required": False, "default": "0"},
        ],
    },
    {
        "slug": "calories",
        "name": "Калории / КБЖУ",
        "topic": "Здоровье",
        "blurb": "BMR (Mifflin–St Jeor) и TDEE по уровню активности.",
        "fields": [
            {"name": "sex", "label": "Пол", "type": "choice", "choices": [("m", "Муж"), ("f", "Жен")]},
            {"name": "age", "label": "Возраст, лет", "type": "number"},
            {"name": "height_cm", "label": "Рост, см", "type": "decimal"},
            {"name": "weight_kg", "label": "Вес, кг", "type": "decimal"},
            {"name": "activity", "label": "Активность", "type": "choice", "choices": [
                ("1.2", "Сидячий"), ("1.375", "Лёгкая"), ("1.55", "Средняя"),
                ("1.725", "Высокая"), ("1.9", "Очень высокая"),
            ], "default": "1.375"},
        ],
    },
    {
        "slug": "weight",
        "name": "Вес / масса / кг",
        "topic": "Конвертеры",
        "blurb": "Перевод массы: г, кг, т, lb, oz.",
        "fields": [
            {"name": "value", "label": "Значение", "type": "decimal"},
            {"name": "frm", "label": "Из (g/kg/t/lb/oz)", "type": "text", "default": "kg"},
            {"name": "to", "label": "В (g/kg/t/lb/oz)", "type": "text", "default": "lb"},
        ],
    },
    {
        "slug": "bmi",
        "name": "ИМТ",
        "topic": "Здоровье",
        "blurb": "Индекс массы тела: вес / рост² (кг/м²).",
        "fields": [
            {"name": "weight_kg", "label": "Вес, кг", "type": "decimal"},
            {"name": "height_cm", "label": "Рост, см", "type": "decimal"},
        ],
    },
    {
        "slug": "moonshine",
        "name": "Разбавление спирта",
        "topic": "Быт / хобби",
        "blurb": "Формула разбавления: V1·C1 = V2·C2 (температурную поправку не учитывает).",
        "fields": [
            {"name": "volume", "label": "Объём спирта, л", "type": "decimal"},
            {"name": "from_abv", "label": "Крепость сейчас, %", "type": "decimal", "default": "96"},
            {"name": "to_abv", "label": "Нужная крепость, %", "type": "decimal", "default": "40"},
        ],
    },
    {
        "slug": "early_payoff",
        "name": "Досрочное погашение",
        "topic": "Финансы",
        "blurb": "Экономия при досрочном взносе (уменьшение срока, аннуитет).",
        "fields": [
            {"name": "principal", "label": "Остаток долга, ₽", "type": "money"},
            {"name": "rate_year", "label": "Ставка, % годовых", "type": "decimal"},
            {"name": "months_left", "label": "Осталось месяцев", "type": "number"},
            {"name": "extra", "label": "Досрочный платёж, ₽", "type": "money"},
        ],
    },
    {
        "slug": "salary",
        "name": "Зарплата",
        "topic": "HR / бухгалтерия",
        "blurb": "Оклад ↔ сумма «на руки» при плоском НДФЛ 13% (для оценки).",
        "fields": [
            {"name": "mode", "label": "Режим", "type": "choice", "choices": [
                ("gross_to_net", "Оклад → на руки"), ("net_to_gross", "На руки → оклад"),
            ]},
            {"name": "amount", "label": "Сумма, ₽", "type": "money"},
            {"name": "rate", "label": "НДФЛ, %", "type": "decimal", "default": "13"},
        ],
    },
    {
        "slug": "deposit",
        "name": "Вклад / депозит",
        "topic": "Финансы",
        "blurb": "Капитализация ежемесячно или простые проценты.",
        "fields": [
            {"name": "principal", "label": "Сумма вклада, ₽", "type": "money"},
            {"name": "rate_year", "label": "Ставка, % годовых", "type": "decimal", "default": "16"},
            {"name": "months", "label": "Срок, мес.", "type": "number", "default": "12"},
            {"name": "compound", "label": "Капитализация", "type": "choice", "choices": [("1", "Ежемесячно"), ("0", "Простые %")], "default": "1"},
        ],
    },
    {
        "slug": "egfr",
        "name": "СКФ по креатинину",
        "topic": "Здоровье",
        "blurb": "CKD-EPI 2009 (креатинин в мкмоль/л).",
        "fields": [
            {"name": "sex", "label": "Пол", "type": "choice", "choices": [("f", "Жен"), ("m", "Муж")]},
            {"name": "age", "label": "Возраст, лет", "type": "number"},
            {"name": "creatinine", "label": "Креатинин, мкмоль/л", "type": "decimal"},
            {"name": "black", "label": "Афроамериканское происхождение", "type": "choice", "choices": [("0", "Нет"), ("1", "Да")], "default": "0"},
        ],
    },
    {
        "slug": "roof",
        "name": "Крыша / кровля",
        "topic": "Строительство",
        "blurb": "Площадь двускатной кровли и оценка материала с запасом.",
        "fields": [
            {"name": "length", "label": "Длина дома, м", "type": "decimal"},
            {"name": "width", "label": "Ширина дома, м", "type": "decimal"},
            {"name": "pitch_deg", "label": "Угол ската, °", "type": "decimal", "default": "30"},
            {"name": "overhang", "label": "Свес с каждой стороны, м", "type": "decimal", "default": "0.5"},
            {"name": "waste", "label": "Запас материала, %", "type": "decimal", "default": "10"},
        ],
    },
    {
        "slug": "time",
        "name": "Время / часы и минуты",
        "topic": "Даты / математика",
        "blurb": "Сложение/вычитание интервалов и перевод в минуты/часы.",
        "fields": [
            {"name": "mode", "label": "Режим", "type": "choice", "choices": [
                ("add", "Сложить"), ("sub", "Вычесть"), ("to_min", "В минуты"), ("from_min", "Из минут"),
            ]},
            {"name": "h1", "label": "Часы 1", "type": "number", "default": "1"},
            {"name": "m1", "label": "Минуты 1", "type": "number", "default": "30"},
            {"name": "h2", "label": "Часы 2", "type": "number", "default": "0", "required": False},
            {"name": "m2", "label": "Минуты 2", "type": "number", "default": "45", "required": False},
            {"name": "total_min", "label": "Всего минут (для «из минут»)", "type": "number", "required": False, "default": "0"},
        ],
    },
    {
        "slug": "cylinder",
        "name": "Цилиндр",
        "topic": "Геометрия",
        "blurb": "Объём и площадь поверхности цилиндра.",
        "fields": [
            {"name": "radius", "label": "Радиус, м", "type": "decimal"},
            {"name": "height", "label": "Высота, м", "type": "decimal"},
        ],
    },
    {
        "slug": "pregnancy",
        "name": "Беременность / ПДР",
        "topic": "Здоровье",
        "blurb": "Предполагаемая дата родов по формуле Негеле (+280 дней от 1-го дня цикла).",
        "fields": [
            {"name": "lmp", "label": "Первый день последней менструации", "type": "date"},
            {"name": "cycle", "label": "Длина цикла, дней", "type": "number", "default": "28"},
        ],
    },
    {
        "slug": "pipe",
        "name": "Трубы",
        "topic": "Строительство",
        "blurb": "Внутренний объём трубы и масса погонного метра (сталь ~7,85 т/м³).",
        "fields": [
            {"name": "od_mm", "label": "Внешний диаметр, мм", "type": "decimal"},
            {"name": "wall_mm", "label": "Толщина стенки, мм", "type": "decimal"},
            {"name": "length_m", "label": "Длина, м", "type": "decimal", "default": "1"},
            {"name": "density", "label": "Плотность, кг/м³", "type": "decimal", "default": "7850"},
        ],
    },
    {
        "slug": "fuel",
        "name": "Топливо / расход",
        "topic": "Авто",
        "blurb": "Расход л/100 км, стоимость поездки и запас хода.",
        "fields": [
            {"name": "mode", "label": "Режим", "type": "choice", "choices": [
                ("trip", "Стоимость поездки"), ("consumption", "Расход по факту"), ("range", "Запас хода"),
            ]},
            {"name": "distance_km", "label": "Дистанция, км", "type": "decimal", "default": "100"},
            {"name": "l_per_100", "label": "Расход, л/100 км", "type": "decimal", "default": "8"},
            {"name": "price", "label": "Цена 1 л, ₽", "type": "money", "default": "60"},
            {"name": "fuel_used", "label": "Израсходовано, л (для расхода)", "type": "decimal", "required": False, "default": "0"},
            {"name": "tank_l", "label": "Бак, л (для запаса)", "type": "decimal", "required": False, "default": "50"},
        ],
    },
    {
        "slug": "triangle",
        "name": "Треугольник",
        "topic": "Геометрия",
        "blurb": "По трём сторонам: площадь (Герона), углы.",
        "fields": [
            {"name": "a", "label": "Сторона a", "type": "decimal"},
            {"name": "b", "label": "Сторона b", "type": "decimal"},
            {"name": "c", "label": "Сторона c", "type": "decimal"},
        ],
    },
    {
        "slug": "ndfl",
        "name": "НДФЛ",
        "topic": "Налоги / бухгалтерия",
        "blurb": "Прогрессивный НДФЛ 2025+: 13/15/18/20/22% по годовой базе (упрощённо).",
        "fields": [
            {"name": "income", "label": "Налоговая база за год, ₽", "type": "money"},
        ],
    },
    {
        "slug": "tax_simple",
        "name": "Налоги (УСН оценка)",
        "topic": "Налоги / бухгалтерия",
        "blurb": "Оценка налога УСН «доходы» / «доходы−расходы».",
        "fields": [
            {"name": "mode", "label": "Режим", "type": "choice", "choices": [
                ("income", "УСН доходы 6%"), ("income_expense", "УСН доходы−расходы 15%"),
            ]},
            {"name": "income", "label": "Доходы, ₽", "type": "money"},
            {"name": "expense", "label": "Расходы, ₽", "type": "money", "required": False, "default": "0"},
        ],
    },
    {
        "slug": "length",
        "name": "Длина / расстояние",
        "topic": "Конвертеры",
        "blurb": "Перевод длины: мм, см, м, км, in, ft, yd, mi.",
        "fields": [
            {"name": "value", "label": "Значение", "type": "decimal"},
            {"name": "frm", "label": "Из", "type": "text", "default": "m"},
            {"name": "to", "label": "В", "type": "text", "default": "ft"},
        ],
    },
    {
        "slug": "pension",
        "name": "Пенсия (оценка)",
        "topic": "Социальные выплаты",
        "blurb": "Грубая оценка: ИПК × стоимость балла + фикс. выплата (параметры задаёте вы).",
        "fields": [
            {"name": "ipk", "label": "Индивидуальный пенсионный коэффициент", "type": "decimal"},
            {"name": "point_value", "label": "Стоимость 1 балла, ₽", "type": "money", "default": "145.69"},
            {"name": "fixed", "label": "Фиксированная выплата, ₽", "type": "money", "default": "8907.70"},
        ],
    },
    {
        "slug": "loan",
        "name": "Займ / проценты",
        "topic": "Финансы",
        "blurb": "Простые проценты по займу за N дней.",
        "fields": [
            {"name": "principal", "label": "Сумма займа, ₽", "type": "money"},
            {"name": "rate_year", "label": "Ставка, % годовых", "type": "decimal", "default": "365"},
            {"name": "days", "label": "Срок, дней", "type": "number", "default": "30"},
        ],
    },
    {
        "slug": "benefits",
        "name": "Пособия (оценка)",
        "topic": "Социальные выплаты",
        "blurb": "Оценка пособия = СДЗ × дни × коэффициент (параметры вручную).",
        "fields": [
            {"name": "avg_day", "label": "Средний дневной заработок, ₽", "type": "money"},
            {"name": "days", "label": "Дней оплаты", "type": "number"},
            {"name": "coeff", "label": "Коэффициент (0–1)", "type": "decimal", "default": "1"},
        ],
    },
    {
        "slug": "tires",
        "name": "Шинный калькулятор",
        "topic": "Авто",
        "blurb": "Внешний диаметр и окружность шины (например 205/55 R16).",
        "fields": [
            {"name": "width", "label": "Ширина, мм", "type": "number", "default": "205"},
            {"name": "aspect", "label": "Профиль, %", "type": "number", "default": "55"},
            {"name": "rim", "label": "Диаметр диска, дюймы", "type": "number", "default": "16"},
        ],
    },
    {
        "slug": "circle",
        "name": "Круг / окружность",
        "topic": "Геометрия",
        "blurb": "Длина окружности и площадь круга.",
        "fields": [
            {"name": "mode", "label": "Дано", "type": "choice", "choices": [("r", "Радиус"), ("d", "Диаметр")]},
            {"name": "value", "label": "Значение", "type": "decimal"},
        ],
    },
    {
        "slug": "metal",
        "name": "Металл / вес",
        "topic": "Строительство",
        "blurb": "Масса листа / прутка / трубы по плотности.",
        "fields": [
            {"name": "shape", "label": "Форма", "type": "choice", "choices": [
                ("sheet", "Лист"), ("bar", "Круглый пруток"), ("pipe", "Труба"),
            ]},
            {"name": "a", "label": "Длина / длина, мм", "type": "decimal"},
            {"name": "b", "label": "Ширина / диаметр, мм", "type": "decimal"},
            {"name": "c", "label": "Толщина / стенка, мм", "type": "decimal", "default": "1"},
            {"name": "density", "label": "Плотность, г/см³", "type": "decimal", "default": "7.85"},
        ],
    },
    {
        "slug": "alcohol",
        "name": "Алкоголь в крови",
        "topic": "Авто / здоровье",
        "blurb": "Оценка промилле по Видмарку (ориентир, не для суда/медосвидетельствования).",
        "fields": [
            {"name": "sex", "label": "Пол", "type": "choice", "choices": [("m", "Муж"), ("f", "Жен")]},
            {"name": "weight_kg", "label": "Вес, кг", "type": "decimal"},
            {"name": "ml", "label": "Объём напитка, мл", "type": "decimal"},
            {"name": "abv", "label": "Крепость, %", "type": "decimal", "default": "40"},
            {"name": "hours", "label": "Часов с начала приёма", "type": "decimal", "default": "1"},
        ],
    },
    {
        "slug": "osago",
        "name": "ОСАГО (оценка)",
        "topic": "Авто",
        "blurb": "Т = ТБ × КТ × КБМ × КВС × КО × КМ × КС (коэффициенты вводите вручную).",
        "fields": [
            {"name": "tb", "label": "Базовый тариф ТБ, ₽", "type": "money", "default": "7535"},
            {"name": "kt", "label": "КТ (территория)", "type": "decimal", "default": "1"},
            {"name": "kbm", "label": "КБМ", "type": "decimal", "default": "1"},
            {"name": "kvs", "label": "КВС", "type": "decimal", "default": "1"},
            {"name": "ko", "label": "КО", "type": "decimal", "default": "1"},
            {"name": "km", "label": "КМ (мощность)", "type": "decimal", "default": "1"},
            {"name": "ks", "label": "КС (срок)", "type": "decimal", "default": "1"},
        ],
    },
    {
        "slug": "deadlines",
        "name": "Сроки / дедлайны",
        "topic": "Право / даты",
        "blurb": "Рабочие или календарные дни от даты (выходные сб/вс).",
        "fields": [
            {"name": "start", "label": "Дата начала", "type": "date"},
            {"name": "days", "label": "Число дней", "type": "number"},
            {"name": "kind", "label": "Тип дней", "type": "choice", "choices": [("calendar", "Календарные"), ("business", "Рабочие")]},
            {"name": "direction", "label": "Направление", "type": "choice", "choices": [("forward", "Вперёд"), ("back", "Назад")], "default": "forward"},
        ],
    },
    {
        "slug": "expiry",
        "name": "Срок годности",
        "topic": "Быт",
        "blurb": "Дата окончания срока и оставшиеся дни.",
        "fields": [
            {"name": "produced", "label": "Дата изготовления", "type": "date"},
            {"name": "shelf_days", "label": "Срок годности, дней", "type": "number"},
        ],
    },
    {
        "slug": "contributions",
        "name": "Страховые взносы",
        "topic": "Налоги / бухгалтерия",
        "blurb": "Оценка взносов с ФОТ: ПФР/ОПС + ОМС + ВНиМ (ставки задаёте).",
        "fields": [
            {"name": "payroll", "label": "ФОТ за период, ₽", "type": "money"},
            {"name": "ops", "label": "ОПС, %", "type": "decimal", "default": "22"},
            {"name": "oms", "label": "ОМС, %", "type": "decimal", "default": "5.1"},
            {"name": "vnim", "label": "ВНиМ, %", "type": "decimal", "default": "2.9"},
        ],
    },
    {
        "slug": "stairs",
        "name": "Лестница",
        "topic": "Строительство",
        "blurb": "Число ступеней, высота/проступь и длина косоура.",
        "fields": [
            {"name": "height_m", "label": "Высота этажа, м", "type": "decimal"},
            {"name": "riser_mm", "label": "Желаемая высота ступени, мм", "type": "decimal", "default": "170"},
            {"name": "tread_mm", "label": "Проступь, мм", "type": "decimal", "default": "280"},
        ],
    },
    {
        "slug": "nmck",
        "name": "44-ФЗ / НМЦК",
        "topic": "Закупки",
        "blurb": "Среднее арифметическое ценовых предложений (метод сопоставимых цен).",
        "fields": [
            {"name": "p1", "label": "Цена 1, ₽", "type": "money"},
            {"name": "p2", "label": "Цена 2, ₽", "type": "money"},
            {"name": "p3", "label": "Цена 3, ₽", "type": "money", "required": False, "default": "0"},
            {"name": "qty", "label": "Количество", "type": "decimal", "default": "1"},
        ],
    },
    {
        "slug": "contract",
        "name": "Расчёты по договорам",
        "topic": "Право / финансы",
        "blurb": "Сумма договора с НДС и помесячная разбивка.",
        "fields": [
            {"name": "amount", "label": "Сумма без НДС, ₽", "type": "money"},
            {"name": "vat_rate", "label": "НДС, %", "type": "decimal", "default": "20"},
            {"name": "months", "label": "Срок оплаты, мес.", "type": "number", "default": "1"},
        ],
    },
    {
        "slug": "floor",
        "name": "Пол / площадь пола",
        "topic": "Строительство",
        "blurb": "Площадь пола и число упаковок покрытия.",
        "fields": [
            {"name": "length", "label": "Длина, м", "type": "decimal"},
            {"name": "width", "label": "Ширина, м", "type": "decimal"},
            {"name": "pack_m2", "label": "В упаковке, м²", "type": "decimal", "default": "2.5"},
            {"name": "waste", "label": "Запас, %", "type": "decimal", "default": "7"},
        ],
    },
    {
        "slug": "cycle",
        "name": "Менструальный цикл",
        "topic": "Здоровье",
        "blurb": "Прогноз следующей менструации и окна овуляции (ориентир).",
        "fields": [
            {"name": "lmp", "label": "Первый день последних месячных", "type": "date"},
            {"name": "cycle", "label": "Длина цикла, дней", "type": "number", "default": "28"},
            {"name": "period_len", "label": "Длительность менструации, дней", "type": "number", "default": "5"},
        ],
    },
    {
        "slug": "walls",
        "name": "Стены / площадь стен",
        "topic": "Строительство",
        "blurb": "Площадь стен комнаты минус проёмы.",
        "fields": [
            {"name": "length", "label": "Длина комнаты, м", "type": "decimal"},
            {"name": "width", "label": "Ширина комнаты, м", "type": "decimal"},
            {"name": "height", "label": "Высота, м", "type": "decimal", "default": "2.7"},
            {"name": "openings", "label": "Площадь проёмов, м²", "type": "decimal", "default": "0"},
        ],
    },
]

TOOL_BY_SLUG = {t["slug"]: t for t in TOOLS}


def get_tool(slug: str):
    return TOOL_BY_SLUG.get((slug or "").strip())


def tools_by_topic():
    groups: dict[str, list] = {}
    for t in TOOLS:
        groups.setdefault(t["topic"], []).append(t)
    return groups
