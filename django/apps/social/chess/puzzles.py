"""Tactical puzzles: mates, forks, pins, skewers + daily challenge."""
from __future__ import annotations

from datetime import date
import hashlib

PUZZLES = [
    {
        "id": "mate1-backrank",
        "title": "Мат на последней горизонтали",
        "theme": "мат",
        "level": "легко",
        "side": "w",
        "fen": "6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1",
        "goal": "Мат в 1 ход",
        "answer": ("a1", "a8"),
        "hint": "Ладья использует слабость последней горизонтали.",
        "explain": "Ладья на a8: король заперт своими пешками.",
    },
    {
        "id": "mate1-queen",
        "title": "Мат ферзём",
        "theme": "мат",
        "level": "легко",
        "side": "w",
        "fen": "7k/6pp/8/8/8/5Q2/8/6K1 w - - 0 1",
        "goal": "Мат в 1 ход",
        "answer": ("f3", "f8"),
        "hint": "Ферзь бьёт по последней горизонтали.",
        "explain": "Ферзь на f8 — пешки мешают королю, взять некем.",
    },
    {
        "id": "mate1-ladder",
        "title": "Линейный мат двумя ладьями",
        "theme": "мат",
        "level": "легко",
        "side": "w",
        "fen": "7k/6R1/7R/8/8/8/8/7K w - - 0 1",
        "goal": "Мат в 1 ход",
        "answer": ("h6", "h8"),
        "hint": "Одна ладья отрезает, вторая ставит мат на краю.",
        "explain": "Ладья h6–h8 под защитой второй ладьи.",
    },
    {
        "id": "mate1-rook-cut",
        "title": "Мат ладьёй с отрезанием",
        "theme": "мат",
        "level": "легко",
        "side": "w",
        "fen": "5k2/6R1/5R2/8/8/8/8/4K3 w - - 0 1",
        "goal": "Мат в 1 ход",
        "answer": ("f6", "f8"),
        "hint": "Ладья на 8-й, другая держит 7-ю.",
        "explain": "Ладья f6–f8 при отрезанной 7-й горизонтали.",
    },
    {
        "id": "mate1-queen-support",
        "title": "Мат ферзём при поддержке короля",
        "theme": "мат",
        "level": "средне",
        "side": "w",
        "fen": "5k2/8/5KQ1/8/5B2/8/8/8 w - - 0 1",
        "goal": "Мат в 1 ход",
        "answer": ("g6", "f7"),
        "hint": "Ферзь рядом с королём — под защитой своего короля.",
        "explain": "Ферзь на f7 защищён королём.",
    },
    {
        "id": "mate1-backrank2",
        "title": "Ещё один мат на последней линии",
        "theme": "мат",
        "level": "средне",
        "side": "w",
        "fen": "6k1/5ppp/8/8/8/8/5PPP/4R1K1 w - - 0 1",
        "goal": "Мат в 1 ход",
        "answer": ("e1", "e8"),
        "hint": "Снова последняя горизонталь без «форточки».",
        "explain": "Ладья e1–e8.",
    },
    {
        "id": "mate1-corner",
        "title": "Мат в углу",
        "theme": "мат",
        "level": "средне",
        "side": "w",
        "fen": "7k/5Q2/6K1/8/8/8/8/8 w - - 0 1",
        "goal": "Мат в 1 ход",
        "answer": ("f7", "f8"),
        "hint": "Король уже отрезал поля — ферзю добить.",
        "explain": "Ферзь f7–f8.",
    },
    {
        "id": "mate1-rook-king",
        "title": "Мат ладьёй с королём",
        "theme": "мат",
        "level": "средне",
        "side": "w",
        "fen": "5k2/8/5K2/8/8/8/8/7R w - - 0 1",
        "goal": "Мат в 1 ход",
        "answer": ("h1", "h8"),
        "hint": "Оппозиция королей — ладья бьёт по краю.",
        "explain": "Ладья h1–h8.",
    },
    {
        "id": "fork-knight1",
        "title": "Вилка конём: король и ладья",
        "theme": "вилка",
        "level": "легко",
        "side": "w",
        "fen": "r3k3/8/8/3N4/8/8/8/4K3 w q - 0 1",
        "goal": "Найдите вилку",
        "answer": ("d5", "c7"),
        "hint": "Клетка, с которой конь бьёт e8 и a8.",
        "explain": "Nc7+: шах королю и удар по ладье a8.",
    },
    {
        "id": "fork-knight2",
        "title": "Вилка конём с шахом",
        "theme": "вилка",
        "level": "средне",
        "side": "w",
        "fen": "r3k3/8/8/8/4N3/8/8/4K3 w q - 0 1",
        "goal": "Найдите вилку",
        "answer": ("e4", "d6"),
        "hint": "Шах с одновременным ударом по ладье.",
        "explain": "Nd6+: король в шахе, ладья a8 под боем.",
    },
    {
        "id": "pin-bishop1",
        "title": "Связка: берите связанного коня",
        "theme": "связка",
        "level": "легко",
        "side": "w",
        "fen": "r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 1",
        "goal": "Используйте связку",
        "answer": ("b5", "c6"),
        "hint": "Конь на c6 связан к королю слоном с b5.",
        "explain": "Bxc6: конь не может уйти — абсолютная связка к королю.",
    },
    {
        "id": "skewer-rook1",
        "title": "Рентген ладьёй",
        "theme": "рентген",
        "level": "средне",
        "side": "w",
        "fen": "q3k3/8/8/8/8/8/8/R3K3 w Q - 0 1",
        "goal": "Найдите рентген",
        "answer": ("a1", "a8"),
        "hint": "Шах по линии — король уйдёт, ферзь останется.",
        "explain": "Ra8+: король обязан отойти, затем берётся ферзь.",
    },
    {
        "id": "disc-check1",
        "title": "Вскрытый шах конём",
        "theme": "вскрытый",
        "level": "средне",
        "side": "w",
        "fen": "4k3/8/8/3N4/8/8/4R3/4K3 w - - 0 1",
        "goal": "Откройте шах",
        "answer": ("d5", "f6"),
        "hint": "Уберите коня с линии ладьи с темпом.",
        "explain": "Nf6+: ладья на e даёт вскрытый шах, конь бьёт с темпом.",
    },
    {
        "id": "mate1-epaulette",
        "title": "Мат по краю с ладьёй",
        "theme": "мат",
        "level": "средне",
        "side": "w",
        "fen": "1k1r3r/8/8/8/8/8/8/R3K3 w Q - 0 1",
        "goal": "Решающий шах по линии",
        "answer": ("a1", "a8"),
        "hint": "Ладья на 8-ю — король зажат.",
        "explain": "Ra8+: тяжёлое давление на запертого короля.",
    },
    {
        "id": "fork-pawn1",
        "title": "Пешечная вилка",
        "theme": "вилка",
        "level": "легко",
        "side": "w",
        "fen": "4k3/8/2n1n3/3P4/8/8/8/4K3 w - - 0 1",
        "goal": "Заберите коня пешкой",
        "answer": ("d5", "c6"),
        "hint": "Пешка с d5 бьёт по диагонали.",
        "explain": "dxc6 — пешка забирает коня; идея вилки пешкой в центре типична для миттельшпиля.",
    },
]

# Fix fork-pawn1 - validate
THEMES = ("мат", "вилка", "связка", "рентген", "вскрытый")


def puzzle_by_id(pid: str):
    for p in PUZZLES:
        if p["id"] == pid:
            return p
    return None


def check_answer(puzzle: dict, frm: str, to: str) -> bool:
    a, b = puzzle["answer"]
    return frm.lower() == a and to.lower() == b


def puzzles_by_theme(theme: str | None = None) -> list[dict]:
    if not theme or theme == "все":
        return list(PUZZLES)
    return [p for p in PUZZLES if p.get("theme") == theme]


def daily_puzzle(d: date | None = None) -> dict:
    d = d or date.today()
    raw = hashlib.md5(f"chess-daily-{d.isoformat()}".encode()).hexdigest()
    idx = int(raw[:8], 16) % len(PUZZLES)
    pz = dict(PUZZLES[idx])
    pz["daily"] = True
    pz["daily_on"] = d.isoformat()
    return pz
