"""Crops, animals, shop items — game balance for Ферма."""
from __future__ import annotations

STARTING_CHIPS = 1_000_000
BANKRUPT_HOURS = 24
MIN_PLAY_CHIPS = 1_000  # below this with empty field → bankruptcy
EXPAND_BASE_COST = 25_000
MAX_PLOTS = 24
START_PLOTS = 6
MAX_ANIMALS = 6
STEAL_SHARE = 0.22  # portion of yield a neighbor can steal once
HELP_XP = 4
HELP_TIP = 200  # chips tip to helper

# slug, title, cost, grow_sec, yield, xp, color, tier
CROPS = [
    ("wheat", "Пшеница", 500, 120, 1_200, 5, "#c9a227", 1),
    ("carrot", "Морковь", 900, 180, 2_200, 8, "#e07a2f", 1),
    ("radish", "Редис", 1_400, 240, 3_400, 10, "#d64545", 1),
    ("tomato", "Томат", 2_500, 360, 6_200, 14, "#c0392b", 2),
    ("corn", "Кукуруза", 4_500, 480, 11_000, 20, "#f0c419", 2),
    ("cabbage", "Капуста", 7_000, 600, 17_500, 28, "#3d8b5a", 2),
    ("grape", "Виноград", 12_000, 900, 30_000, 40, "#6b3fa0", 3),
    ("strawberry", "Клубника", 18_000, 1_200, 46_000, 55, "#e23d5b", 3),
    ("pumpkin", "Тыква", 35_000, 1_800, 90_000, 80, "#e67e22", 4),
    ("truffle", "Трюфель", 80_000, 2_700, 210_000, 120, "#5c4033", 4),
]

# slug, title, buy, feed_cost, product_sec, product_yield, xp, emoji-ish mark
ANIMALS = [
    ("chicken", "Курица", 15_000, 400, 300, 1_800, 6, "ч"),
    ("rabbit", "Кролик", 28_000, 700, 420, 3_500, 10, "к"),
    ("goat", "Коза", 45_000, 1_200, 540, 6_000, 14, "з"),
    ("cow", "Корова", 90_000, 2_500, 720, 14_000, 22, "к"),
    ("pig", "Свинья", 120_000, 3_500, 900, 20_000, 30, "с"),
]

SHOP = [
    {"slug": "water", "title": "Лейка", "price": 300, "blurb": "Полить грядку — полный урожай."},
    {"slug": "fertilizer", "title": "Удобрение", "price": 2_000, "blurb": "Сокращает оставшееся время вдвое."},
    {"slug": "boost", "title": "Ускоритель", "price": 8_000, "blurb": "Сразу +30% к готовности грядки."},
]


def crop_by_slug(slug: str) -> dict | None:
    for c in CROPS:
        if c[0] == slug:
            return {
                "slug": c[0],
                "title": c[1],
                "cost": c[2],
                "grow_sec": c[3],
                "yield": c[4],
                "xp": c[5],
                "color": c[6],
                "tier": c[7],
            }
    return None


def animal_by_slug(slug: str) -> dict | None:
    for a in ANIMALS:
        if a[0] == slug:
            return {
                "slug": a[0],
                "title": a[1],
                "buy": a[2],
                "feed_cost": a[3],
                "product_sec": a[4],
                "product_yield": a[5],
                "xp": a[6],
                "mark": a[7],
            }
    return None


def crops_for_level(level: int) -> list[dict]:
    out = []
    for c in CROPS:
        row = crop_by_slug(c[0])
        need = 1 + (row["tier"] - 1) * 2
        row = {**row, "locked": level < need, "need_level": need}
        out.append(row)
    return out


def expand_cost(plots_unlocked: int) -> int:
    n = max(0, int(plots_unlocked) - START_PLOTS)
    return EXPAND_BASE_COST + n * 15_000


def level_from_xp(xp: int) -> int:
    xp = max(0, int(xp or 0))
    # soft curve: lvl 1 at 0, then 50, 120, 220...
    level = 1
    need = 50
    left = xp
    while left >= need and level < 50:
        left -= need
        level += 1
        need = int(50 + level * 35)
    return level


def xp_progress(xp: int) -> dict:
    xp = max(0, int(xp or 0))
    level = 1
    need = 50
    left = xp
    while left >= need and level < 50:
        left -= need
        level += 1
        need = int(50 + level * 35)
    return {
        "level": level,
        "into": left,
        "need": need,
        "pct": int(100 * left / need) if need else 0,
    }
