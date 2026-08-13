"""Interactive add-ons for lessons: diagrams, quizzes, board drills."""
from __future__ import annotations

from apps.social.chess.engine import START_FEN

# Merged into lessons by slug (see lessons.CATALOG.get).
INTERACTIVES: dict[str, dict] = {
    "board": {
        "diagram": START_FEN,
        "diagram_caption": "Стартовая позиция. Правый нижний угол у белых — светлая клетка h1.",
        "quiz": {
            "question": "Как называется клетка на пересечении вертикали e и 4-й горизонтали?",
            "choices": [
                ("a1", "a1"),
                ("e4", "e4"),
                ("h8", "h8"),
                ("d5", "d5"),
            ],
            "answer": "e4",
            "explain": "Буква вертикали + цифра горизонтали: e4 — классический центр.",
        },
        "related_puzzles": ["mate1-backrank"],
    },
    "pieces": {
        "diagram": START_FEN,
        "diagram_caption": "Запомните «стоимость»: ♙1 · ♘♗3 · ♖5 · ♕9.",
        "quiz": {
            "question": "Что обычно ценнее: ладья или конь?",
            "choices": [
                ("rook", "Ладья (~5) ценнее коня (~3)"),
                ("knight", "Конь ценнее ладьи"),
                ("equal", "Всегда равны"),
            ],
            "answer": "rook",
            "explain": "Ориентир новичка: ладья ≈ 5, конь ≈ 3. Исключения бывают, но редко в дебюте.",
        },
    },
    "goal": {
        "quiz": {
            "question": "Главная цель партии — это…",
            "choices": [
                ("all", "Съесть все фигуры соперника"),
                ("mate", "Поставить мат королю соперника"),
                ("queen", "Провести пешку в ферзи любой ценой"),
            ],
            "answer": "mate",
            "explain": "Мат заканчивает партию. Материал и превращения — лишь средства.",
        },
        "related_puzzles": ["mate1-queen", "mate1-corner"],
    },
    "pawn": {
        "diagram": "4k3/8/8/8/8/8/4P3/4K3 w - - 0 1",
        "diagram_caption": "Белая пешка на e2: из начальной горизонтали можно шагнуть на две клетки.",
        "drill": {
            "prompt": "Сделайте ход пешкой на две клетки вперёд (e2 → e4).",
            "fen": "4k3/8/8/8/8/8/4P3/4K3 w - - 0 1",
            "side": "w",
            "answer": ("e2", "e4"),
            "hint": "Пешка с 2-й горизонтали может сразу на e4.",
            "explain": "e2–e4 — классический шаг к центру.",
        },
        "quiz": {
            "question": "Как пешка бьёт?",
            "choices": [
                ("fwd", "Прямо вперёд на одну клетку"),
                ("diag", "По диагонали вперёд на одну клетку"),
                ("any", "В любую сторону как король"),
            ],
            "answer": "diag",
            "explain": "Ходит вперёд, бьёт по диагонали — важное отличие.",
        },
    },
    "knight-bishop": {
        "diagram": "4k3/8/8/3N4/8/8/8/4K3 w - - 0 1",
        "diagram_caption": "Конь в центре ходит буквой «Г».",
        "drill": {
            "prompt": "Перейдите конём с d5 на e7.",
            "fen": "4k3/8/8/3N4/8/8/8/4K3 w - - 0 1",
            "side": "w",
            "answer": ("d5", "e7"),
            "hint": "Две клетки вперёд и одна вбок.",
            "explain": "Конь меняет цвет поля и умеет перепрыгивать.",
        },
        "related_puzzles": ["fork-knight1", "fork-knight2"],
    },
    "rook-queen-king": {
        "diagram": "4k3/8/8/8/8/8/8/R3K3 w Q - 0 1",
        "diagram_caption": "Ладья любит открытые линии; король в центре — повод подумать о рокировке.",
        "quiz": {
            "question": "Ферзь ходит…",
            "choices": [
                ("rook", "Только как ладья"),
                ("both", "Как ладья и как слон"),
                ("king", "Только на одну клетку"),
            ],
            "answer": "both",
            "explain": "Ферзь = ладья + слон.",
        },
    },
    "castling": {
        "diagram": "r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQkq - 0 1",
        "diagram_caption": "Обе стороны ещё могут рокировать в обе стороны.",
        "drill": {
            "prompt": "Сделайте короткую рокировку белых (король e1 → g1).",
            "fen": "r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQkq - 0 1",
            "side": "w",
            "answer": ("e1", "g1"),
            "hint": "Ход короля на две клетки к ладье на h1.",
            "explain": "Короткая рокировка: король на g1, ладья сама встанет на f1.",
        },
        "quiz": {
            "question": "Можно ли рокироваться, если король под шахом?",
            "choices": [
                ("yes", "Да, это способ уйти"),
                ("no", "Нет, сначала уберите шах"),
            ],
            "answer": "no",
            "explain": "Под шахом рокировка запрещена.",
        },
    },
    "check-mate": {
        "diagram": "6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1",
        "diagram_caption": "Учебная позиция: мат на последней горизонтали.",
        "drill": {
            "prompt": "Поставьте мат в один ход ладьёй.",
            "fen": "6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1",
            "side": "w",
            "answer": ("a1", "a8"),
            "hint": "Последняя горизонталь без «форточки».",
            "explain": "Ладья a1–a8#: король заперт своими пешками.",
        },
        "related_puzzles": ["mate1-backrank", "mate1-backrank2", "mate1-ladder"],
    },
    "stalemate-draw": {
        "quiz": {
            "question": "Пат — это когда…",
            "choices": [
                ("check", "Королю шах и нет защиты"),
                ("stale", "Нет легальных ходов, но шаха нет"),
                ("repeat", "Трижды повторилась позиция"),
            ],
            "answer": "stale",
            "explain": "Пат = ничья. Не оставляйте сопернику нуль ходов без шаха.",
        },
    },
    "opening-ideas": {
        "diagram": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
        "diagram_caption": "После 1.e4 белые занимают центр.",
        "drill": {
            "prompt": "Ответьте за чёрных классически: e7–e5.",
            "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
            "side": "b",
            "answer": ("e7", "e5"),
            "hint": "Симметричный захват центра.",
            "explain": "1…e5 — понятный и крепкий ответ.",
        },
    },
    "tactics-basic": {
        "diagram": "r3k3/8/8/3N4/8/8/8/4K3 w q - 0 1",
        "diagram_caption": "Конь готов сделать вилку на короля и ладью.",
        "drill": {
            "prompt": "Сделайте вилку конём: шах королю и удар по ладье.",
            "fen": "r3k3/8/8/3N4/8/8/8/4K3 w q - 0 1",
            "side": "w",
            "answer": ("d5", "c7"),
            "hint": "Клетка c7 бьёт e8 и a8.",
            "explain": "Nc7+: король в шахе, ладья a8 висит — классическая вилка.",
        },
        "quiz": {
            "question": "Вилка — это…",
            "choices": [
                ("pin", "Фигура не может уйти из‑за короля позади"),
                ("fork", "Одна фигура атакует сразу две цели"),
                ("sac", "Любая жертва ферзя"),
            ],
            "answer": "fork",
            "explain": "Чаще всего вилку делает конь.",
        },
        "related_puzzles": ["fork-knight1", "fork-knight2", "pin-bishop1"],
    },
    "mate-patterns": {
        "related_puzzles": ["mate1-ladder", "mate1-rook-king", "mate1-queen-support"],
        "quiz": {
            "question": "Линейный мат делают чаще всего…",
            "choices": [
                ("bishops", "Двумя слонами"),
                ("rooks", "Двумя ладьями"),
                ("pawns", "Одними пешками"),
            ],
            "answer": "rooks",
            "explain": "«Лесенка» ладьями — базовый матовый навык.",
        },
    },
    "protect-king": {
        "quiz": {
            "question": "При обычном шахе какой вариант НЕ защита?",
            "choices": [
                ("block", "Закрыться фигурой"),
                ("take", "Взять нападающую"),
                ("castle", "Рокироваться из-под шаха"),
                ("run", "Уйти королём"),
            ],
            "answer": "castle",
            "explain": "Рокировка под шахом запрещена.",
        },
        "related_puzzles": ["mate1-backrank"],
    },
    "common-mistakes": {
        "quiz": {
            "question": "Самый частый «слив» новичка в дебюте?",
            "choices": [
                ("earlyq", "Ранний выход ферзя под удары"),
                ("castle", "Рокировка на 6–8 ходу"),
                ("center", "Ход e2–e4"),
            ],
            "answer": "earlyq",
            "explain": "Сначала развивайте коней и слонов, ферзя берегите.",
        },
    },
    "notation": {
        "quiz": {
            "question": "Что означает запись Nf3?",
            "choices": [
                ("pawn", "Пешка пошла на f3"),
                ("knight", "Конь пошёл на f3"),
                ("king", "Король пошёл на f3"),
            ],
            "answer": "knight",
            "explain": "N — knight (конь). K — король, Q — ферзь, R — ладья, B — слон.",
        },
    },
    "illegal-moves": {
        "quiz": {
            "question": "Ход, после которого ваш король оказывается под боем…",
            "choices": [
                ("ok", "Разрешён, если вы сами даёте шах"),
                ("illegal", "Запрещён всегда"),
            ],
            "answer": "illegal",
            "explain": "Нельзя «подставлять» короля. Движок такие ходы отклонит.",
        },
    },
}


def attach(lesson: dict | None) -> dict | None:
    if not lesson:
        return None
    extra = INTERACTIVES.get(lesson["slug"]) or {}
    if not extra:
        return lesson
    return {**lesson, **extra}


def interactive_slugs() -> list[str]:
    return list(INTERACTIVES.keys())
