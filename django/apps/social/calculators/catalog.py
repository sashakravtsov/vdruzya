
"""Catalog of 50 calculators with user-facing blurbs."""
from __future__ import annotations

from typing import Any

from . import copy as C

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
        "blurb": "Выделить или начислить НДС по ставкам 2026: 22% / 20% (до 2026) / 10% / 0%.",
        "law": "vat",
        "fields": [
            {"name": "amount", "label": "Сумма, ₽", "type": "money", "hint": "Для «выделить» — сумма с НДС; для «начислить» — без НДС"},
            {"name": "rate", "label": "Ставка", "type": "choice", "choices": C.VAT_RATE_CHOICES, "default": "22"},
            {"name": "custom_rate", "label": "Своя ставка, %", "type": "decimal", "default": "", "required": False,
             "hint": "Нужно, только если выше выбрано «Своя ставка»"},
            {"name": "mode", "label": "Режим", "type": "choice", "choices": [
                ("extract", "Выделить налог из суммы"),
                ("add", "Начислить налог сверху"),
            ], "default": "extract"},
            {"name": "ship_date", "label": "Дата отгрузки (необяз.)", "type": "date", "required": False,
             "hint": "Помогает подсказать, какая ставка обычно подходит"},
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
        "blurb": "Договорные пени или налоговые пени 1/300 ключевой ставки ЦБ за день.",
        "fields": [
            {"name": "kind", "label": "Тип", "type": "choice", "choices": [
                ("contract", "Договорная неустойка"),
                ("tax", "Налоговые пени (1/300 ст. реф. ЦБ × дни)"),
            ], "default": "contract"},
            {"name": "amount", "label": "Сумма долга / недоимки, ₽", "type": "money"},
            {"name": "days", "label": "Дней просрочки", "type": "number"},
            {"name": "key_rate", "label": "Ключевая ставка ЦБ, %", "type": "decimal", "default": "16",
             "hint": "Для налоговых пеней; актуальную ставку смотрите на cbr.ru"},
            {"name": "rate_day", "label": "Ставка, % в день (договор)", "type": "decimal", "default": "0.1", "required": False},
            {"name": "base", "label": "База года (договор, годовая ставка)", "type": "choice", "choices": [("365", "365"), ("360", "360")], "default": "365"},
            {"name": "rate_year", "label": "Годовая ставка, % (договор, если >0)", "type": "decimal", "default": "0", "required": False},
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
        "blurb": "Оклад ↔ «на руки»: плоский % или оценка по прогрессии НДФЛ 2025–2026.",
        "law": "ndfl",
        "fields": [
            {"name": "mode", "label": "Режим", "type": "choice", "choices": [
                ("gross_to_net", "Оклад → на руки"), ("net_to_gross", "На руки → оклад"),
            ]},
            {"name": "amount", "label": "Сумма за месяц, ₽", "type": "money"},
            {"name": "tax_mode", "label": "НДФЛ", "type": "choice", "choices": [
                ("flat", "Плоская ставка"),
                ("progressive", "Прогрессия за год (месяц × 12)"),
            ], "default": "flat"},
            {"name": "rate", "label": "Плоская ставка, %", "type": "decimal", "default": "13",
             "hint": "Для большинства — 13% при доходе до 2,4 млн ₽/год"},
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
        "blurb": "Прогрессия 13/15/18/20/22% по годовой основной базе (2025–2026).",
        "law": "ndfl",
        "fields": [
            {"name": "input_mode", "label": "Ввод", "type": "choice", "choices": [
                ("year", "База за год"),
                ("month", "Доход за месяц × 12"),
            ], "default": "year"},
            {"name": "income", "label": "Сумма, ₽", "type": "money"},
            {"name": "deduction", "label": "Вычеты за год, ₽ (необяз.)", "type": "money", "required": False, "default": "0",
             "hint": "Уменьшают базу до расчёта ступеней"},
        ],
    },
    {
        "slug": "tax_simple",
        "name": "Налоги (УСН оценка)",
        "topic": "Налоги / бухгалтерия",
        "blurb": "Оценка налога УСН «доходы» / «доходы−расходы» (ставки региона могут отличаться).",
        "fields": [
            {"name": "mode", "label": "Режим", "type": "choice", "choices": [
                ("income", "УСН доходы"), ("income_expense", "УСН доходы−расходы"),
            ]},
            {"name": "income", "label": "Доходы, ₽", "type": "money"},
            {"name": "expense", "label": "Расходы, ₽", "type": "money", "required": False, "default": "0"},
            {"name": "rate_income", "label": "Ставка «доходы», %", "type": "decimal", "default": "6",
             "hint": "Федеральный максимум 6%; в регионе может быть ниже"},
            {"name": "rate_diff", "label": "Ставка «доходы−расходы», %", "type": "decimal", "default": "15"},
            {"name": "contrib", "label": "Страховые взносы к вычету (УСН доходы), ₽", "type": "money", "required": False, "default": "0"},
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
        "blurb": "Единый тариф 2026: 30% до базы 2 979 000 ₽, 15,1% сверх (нарастающим итогом).",
        "law": "contrib",
        "fields": [
            {"name": "payroll", "label": "Выплаты нарастающим итогом с начала года, ₽", "type": "money"},
            {"name": "mode", "label": "Тариф", "type": "choice", "choices": [
                ("general", "Общий тариф 2026 (30% / 15,1%)"),
                ("custom", "Свои ставки (без предельной базы)"),
            ], "default": "general"},
            {"name": "injury", "label": "Травматизм, % (отдельно)", "type": "decimal", "default": "0.2", "required": False},
            {"name": "ops", "label": "Своя ставка 1, %", "type": "decimal", "default": "22", "required": False},
            {"name": "oms", "label": "Своя ставка 2, %", "type": "decimal", "default": "5.1", "required": False},
            {"name": "vnim", "label": "Своя ставка 3, %", "type": "decimal", "default": "2.9", "required": False},
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
        "blurb": "Сумма договора с НДС (по умолчанию 22% с 2026) и помесячная разбивка.",
        "law": "vat",
        "fields": [
            {"name": "amount", "label": "Сумма без НДС, ₽", "type": "money"},
            {"name": "vat_rate", "label": "НДС, %", "type": "choice", "choices": [
                ("22", "22%"), ("20", "20%"), ("10", "10%"), ("7", "7% УСН"), ("5", "5% УСН"), ("0", "0%"),
            ], "default": "22"},
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

# Classic 16×16 GIF icons (static/img/calc/ico-*.gif), keyed by topic / slug.
_TOPIC_ICON = {
    "HR / бухгалтерия": "hr",
    "Даты / математика": "date",
    "Финансы": "money",
    "Налоги / бухгалтерия": "tax",
    "Право / бухгалтерия": "legal",
    "Право / финансы": "legal",
    "Право / даты": "legal",
    "Конвертеры": "convert",
    "Строительство / геометрия": "build",
    "Строительство": "build",
    "Геометрия": "build",
    "Здоровье": "health",
    "Быт / хобби": "calc",
    "Быт": "calc",
    "Авто": "auto",
    "Авто / здоровье": "auto",
    "Социальные выплаты": "hr",
    "Закупки": "legal",
    "Математика / финансы": "calc",
}

_SLUG_ICON = {
    "vat": "tax", "ndfl": "tax", "tax_simple": "tax", "contributions": "tax",
    "credit": "money", "mortgage": "home", "deposit": "money", "loan": "money",
    "early_payoff": "money", "salary": "hr", "vacation": "hr", "sick": "hr",
    "contract": "legal", "penalty": "legal", "bmi": "health", "calories": "health",
    "roof": "home", "floor": "home", "walls": "home", "osago": "auto", "fuel": "auto",
}


def tool_icon(tool: dict[str, Any] | str) -> str:
    if isinstance(tool, str):
        if tool in _SLUG_ICON:
            return _SLUG_ICON[tool]
        known = next((t for t in TOOLS if t["slug"] == tool), None)
        if known:
            return _TOPIC_ICON.get(known.get("topic") or "", "calc")
        return "calc"
    slug = tool.get("slug") or ""
    if slug in _SLUG_ICON:
        return _SLUG_ICON[slug]
    return _TOPIC_ICON.get(tool.get("topic") or "", "calc")


# Attach icon key + static-relative path for templates; apply user blurbs.
for _t in TOOLS:
    key = tool_icon(_t)
    _t["icon"] = key
    _t["icon_src"] = f"img/calc/ico-{key}.gif"
    if _t["slug"] in C.BLURBS:
        _t["blurb"] = C.BLURBS[_t["slug"]]

TOOL_BY_SLUG = {t["slug"]: t for t in TOOLS}

POPULAR_SLUGS = (
    "vat", "ndfl", "vacation", "credit", "mortgage", "salary",
    "sick", "contributions", "bmi", "percent",
)

_RELATED = {
    "vat": ("contract", "tax_simple", "ndfl", "contributions"),
    "ndfl": ("salary", "vat", "contributions", "vacation"),
    "salary": ("ndfl", "contributions", "vacation", "sick"),
    "vacation": ("sick", "severance", "salary", "ndfl"),
    "sick": ("vacation", "benefits", "salary", "contributions"),
    "credit": ("mortgage", "early_payoff", "loan", "deposit"),
    "mortgage": ("credit", "early_payoff", "deposit", "percent"),
    "contributions": ("ndfl", "salary", "tax_simple", "vat"),
    "contract": ("vat", "penalty", "nmck", "tax_simple"),
    "penalty": ("contract", "deadlines", "loan", "vat"),
}


def get_tool(slug: str):
    return TOOL_BY_SLUG.get((slug or "").strip())


def tools_by_topic():
    groups: dict[str, list] = {}
    for t in TOOLS:
        groups.setdefault(t["topic"], []).append(t)
    return groups


def popular_tools(limit: int = 10):
    out = []
    for slug in POPULAR_SLUGS:
        t = TOOL_BY_SLUG.get(slug)
        if t:
            out.append(t)
        if len(out) >= limit:
            break
    return out


def related_tools(slug: str, limit: int = 4):
    out = []
    for s in _RELATED.get(slug or "", ()):
        t = TOOL_BY_SLUG.get(s)
        if t:
            out.append(t)
        if len(out) >= limit:
            break
    if len(out) < limit:
        tool = TOOL_BY_SLUG.get(slug or "")
        topic = (tool or {}).get("topic")
        for t in TOOLS:
            if t["slug"] == slug:
                continue
            if topic and t.get("topic") == topic and t not in out:
                out.append(t)
            if len(out) >= limit:
                break
    return out
