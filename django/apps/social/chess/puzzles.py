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
        "id": "mate1-epaulette",
        "title": "Мат «эполеты» ферзём",
        "theme": "мат",
        "level": "средне",
        "side": "w",
        "fen": "3rkr2/8/4KQ2/8/8/8/8/8 w - - 0 1",
        "goal": "Мат в 1 ход",
        "answer": ("f6", "e7"),
        "hint": "Ферзь встаёт перед королём — ладьи как эполеты мешают убежать.",
        "explain": "Qe7#: король зажат своими ладьями, ферзь защищён королём.",
    },
    {
        "id": "mate1-smother",
        "title": "Спёртый мат конём",
        "theme": "мат",
        "level": "сложно",
        "side": "w",
        "fen": "6rk/5ppp/8/4N3/8/8/8/4K3 w - - 0 1",
        "goal": "Мат в 1 ход",
        "answer": ("e5", "f7"),
        "hint": "Конь прыгает на f7 — короля запирают свои же фигуры.",
        "explain": "Nf7#: спёртый мат — король задохнулся за ладьёй и пешками.",
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
        "id": "fork-pawn1",
        "title": "Пешечная вилка",
        "theme": "вилка",
        "level": "легко",
        "side": "w",
        "fen": "4k3/8/2n1n3/3P4/8/8/8/4K3 w - - 0 1",
        "goal": "Заберите коня пешкой",
        "answer": ("d5", "c6"),
        "hint": "Пешка с d5 бьёт по диагонали.",
        "explain": "dxc6 — пешка забирает коня.",
    },
    {
        "id": "fork-royal",
        "title": "Королевская вилка конём",
        "theme": "вилка",
        "level": "средне",
        "side": "w",
        "fen": "4k3/8/8/1q6/2N5/8/8/4K3 w - - 0 1",
        "goal": "Найдите вилку на короля и ферзя",
        "answer": ("c4", "d6"),
        "hint": "Конь с шахом бьёт и ферзя на b5.",
        "explain": "Nd6+: шах и удар по ферзю.",
    },
    {
        "id": "fork-queen",
        "title": "Вилка ферзём",
        "theme": "вилка",
        "level": "средне",
        "side": "w",
        "fen": "r3k3/8/8/8/8/4Q3/8/4K3 w q - 0 1",
        "goal": "Двойной удар ферзём",
        "answer": ("e3", "a7"),
        "hint": "Ферзь бьёт ладью с шахом.",
        "explain": "Qa7+: шах и удар по ладье a8.",
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
        "id": "pin-rook1",
        "title": "Связка ладьёй по вертикали",
        "theme": "связка",
        "level": "средне",
        "side": "w",
        "fen": "4k3/4n3/8/8/8/8/8/4R1K1 w - - 0 1",
        "goal": "Заберите связанного коня",
        "answer": ("e1", "e7"),
        "hint": "Конь на линии ладьи и короля.",
        "explain": "Rxe7+: абсолютная связка — конь не может уйти.",
    },
    {
        "id": "pin-bishop2",
        "title": "Связка слоном: берите коня",
        "theme": "связка",
        "level": "средне",
        "side": "w",
        "fen": "4k3/3n4/8/1B6/8/8/8/4K3 w - - 0 1",
        "goal": "Используйте связку",
        "answer": ("b5", "d7"),
        "hint": "Конь связан к королю по диагонали.",
        "explain": "Bxd7+: конь не мог уйти из‑за короля позади.",
    },
    {
        "id": "skewer-rook1",
        "title": "Рентген ладьёй",
        "theme": "рентген",
        "level": "средне",
        "side": "w",
        "fen": "4k2q/8/8/8/8/8/8/4K2R w - - 0 1",
        "goal": "Найдите рентген",
        "answer": ("h1", "h8"),
        "hint": "Шах по линии — король уйдёт, ферзь останется.",
        "explain": "Rh8+: король обязан отойти, затем берётся ферзь.",
    },
    {
        "id": "skewer-bishop1",
        "title": "Рентген слоном",
        "theme": "рентген",
        "level": "средне",
        "side": "w",
        "fen": "8/5q2/8/3k4/8/8/4B3/4K3 w - - 0 1",
        "goal": "Найдите рентген",
        "answer": ("e2", "c4"),
        "hint": "Шах по диагонали король–ферзь.",
        "explain": "Bc4+: король отойдёт — ферзь на той же диагонали под боем.",
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
        "id": "disc-check2",
        "title": "Ещё один вскрытый шах",
        "theme": "вскрытый",
        "level": "сложно",
        "side": "w",
        "fen": "4k3/8/8/8/4N3/8/4R3/4K3 w - - 0 1",
        "goal": "Откройте шах",
        "answer": ("e4", "f6"),
        "hint": "Конь уходит с линии ладьи и сам даёт шах.",
        "explain": "Nf6+: вскрытый шах ладьёй плюс удар конём.",
    },
    {
        "id": "distract1",
        "title": "Отвлечение на последней линии",
        "theme": "отвлечение",
        "level": "средне",
        "side": "w",
        "fen": "6k1/5ppp/5Q2/8/8/8/8/4R1K1 w - - 0 1",
        "goal": "Отвлеките защиту последней горизонтали",
        "answer": ("e1", "e8"),
        "hint": "Ладья врывается на 8-ю — защита не справляется.",
        "explain": "Re8#: идея отвлечения/прорыва на последней горизонтали.",
    },
    {
        "id": "decoy1",
        "title": "Завлечение на край",
        "theme": "завлечение",
        "level": "средне",
        "side": "w",
        "fen": "5k2/8/5R2/8/8/8/8/4K2R w - - 0 1",
        "goal": "Завлеките короля под удар",
        "answer": ("h1", "h8"),
        "hint": "Шах с края заставляет короля выбрать поле.",
        "explain": "Rh8+: короля тянут на линию, где работает вторая ладья.",
    },
    {
        "id": "hanging1",
        "title": "Висячая ладья",
        "theme": "висячие",
        "level": "легко",
        "side": "w",
        "fen": "4k3/8/8/2r5/8/2Q5/8/4K3 w - - 0 1",
        "goal": "Заберите незащищённую ладью",
        "answer": ("c3", "c5"),
        "hint": "Ладья на c5 без защиты.",
        "explain": "Qxc5: ферзь забирает висячую ладью.",
    },
    {
        "id": "hanging2",
        "title": "Висячий конь",
        "theme": "висячие",
        "level": "легко",
        "side": "w",
        "fen": "4k3/8/8/3n4/8/8/8/3QK3 w - - 0 1",
        "goal": "Заберите незащищённого коня",
        "answer": ("d1", "d5"),
        "hint": "Конь в центре без защиты.",
        "explain": "Qxd5: ферзь забирает висячего коня.",
    },
]

THEMES = ("мат", "вилка", "связка", "рентген", "вскрытый", "отвлечение", "завлечение", "висячие")


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


def theme_counts() -> dict[str, int]:
    out = {t: 0 for t in THEMES}
    for p in PUZZLES:
        t = p.get("theme")
        if t in out:
            out[t] += 1
    return out


def next_unsolved(solved_ids, theme: str | None = None, after_id: str | None = None):
    items = puzzles_by_theme(theme)
    if after_id:
        ids = [p["id"] for p in items]
        if after_id in ids:
            i = ids.index(after_id)
            items = items[i + 1 :] + items[: i + 1]
    for p in items:
        if p["id"] not in (solved_ids or set()):
            return p
    return None


def related_puzzles(ids: list[str] | None) -> list[dict]:
    out = []
    for pid in ids or []:
        pz = puzzle_by_id(pid)
        if pz:
            out.append(pz)
    return out


def daily_puzzle(d: date | None = None) -> dict:
    d = d or date.today()
    raw = hashlib.md5(f"chess-daily-{d.isoformat()}".encode()).hexdigest()
    idx = int(raw[:8], 16) % len(PUZZLES)
    pz = dict(PUZZLES[idx])
    pz["daily"] = True
    pz["daily_on"] = d.isoformat()
    return pz
