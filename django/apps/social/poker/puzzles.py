"""Poker decision / ranking puzzles + daily challenge."""
from __future__ import annotations

from datetime import date
import hashlib

PUZZLES = [
    {
        "id": "rank-flush-fh",
        "title": "Что сильнее?",
        "theme": "комбинации",
        "level": "легко",
        "question": "Флеш против фулл-хауса — кто побеждает?",
        "choices": [
            ("flush", "Флеш"),
            ("fh", "Фулл-хаус"),
            ("split", "Всегда делёж"),
        ],
        "answer": "fh",
        "hint": "Вспомните таблицу силы рук.",
        "explain": "Фулл-хаус выше флеша.",
    },
    {
        "id": "rank-straight-flush",
        "title": "Стрит или флеш?",
        "theme": "комбинации",
        "level": "легко",
        "question": "Обычный стрит сильнее обычного флеша?",
        "choices": [
            ("yes", "Да"),
            ("no", "Нет, флеш сильнее"),
            ("eq", "Равны"),
        ],
        "answer": "no",
        "hint": "Флеш идёт сразу после стрита.",
        "explain": "Флеш > стрит.",
    },
    {
        "id": "action-check",
        "title": "Когда чек?",
        "theme": "действия",
        "level": "легко",
        "question": "Соперник не ставил на улице. Можно ли чекнуть?",
        "choices": [
            ("yes", "Да"),
            ("no", "Нет, только фолд"),
            ("allin", "Только олл-ин"),
        ],
        "answer": "yes",
        "hint": "Чек = пас без доплаты.",
        "explain": "Если уравнивать нечего — доступен чек.",
    },
    {
        "id": "action-fold-beat",
        "title": "Зачем фолд?",
        "theme": "действия",
        "level": "легко",
        "question": "Фолд в раздаче означает…",
        "choices": [
            ("win", "Вы забираете банк"),
            ("lose", "Вы отдаёте банк сопернику"),
            ("tie", "Ничья"),
        ],
        "answer": "lose",
        "hint": "Сброс карт заканчивает ваше участие.",
        "explain": "После фолда банк уходит оставшемуся игроку.",
    },
    {
        "id": "street-flop",
        "title": "Флоп",
        "theme": "улицы",
        "level": "легко",
        "question": "Сколько карт открывают на флопе?",
        "choices": [("2", "2"), ("3", "3"), ("4", "4")],
        "answer": "3",
        "hint": "Три общие карты.",
        "explain": "Флоп = 3 карты.",
    },
    {
        "id": "bankrupt-days",
        "title": "Банкротство",
        "theme": "баланс",
        "level": "легко",
        "question": "После банкротства нельзя играть…",
        "choices": [("5", "5 дней"), ("час", "1 час"), ("вечно", "навсегда")],
        "answer": "5",
        "hint": "Потом доступен сброс профиля.",
        "explain": "Пауза 5 дней, затем сброс на 1 000 000.",
    },
    {
        "id": "bankrupt-reset",
        "title": "Сброс профиля",
        "theme": "баланс",
        "level": "средне",
        "question": "После сброса банкротства вы получаете…",
        "choices": [
            ("same", "Столько же, сколько проиграли"),
            ("1m", "1 000 000 фишек"),
            ("half", "Половину стартовых"),
        ],
        "answer": "1m",
        "hint": "Стартовый банкролл мира ВДрузья.",
        "explain": "Профиль возвращается к 1 000 000 фишек.",
    },
    {
        "id": "hu-button",
        "title": "Heads-up баттон",
        "theme": "позиция",
        "level": "средне",
        "question": "В heads-up на префлопе баттон обычно…",
        "choices": [
            ("sb", "Ставит малый блайнд и ходит первым"),
            ("bb", "Ставит большой блайнд"),
            ("none", "Не участвует в блайндах"),
        ],
        "answer": "sb",
        "hint": "Особая HU-конвенция.",
        "explain": "В HU баттон = SB и первый ход префлоп.",
    },
    {
        "id": "pot-odds-basic",
        "title": "Идея пот-оддсов",
        "theme": "стратегия",
        "level": "средне",
        "question": "Пот-оддсы помогают решить…",
        "choices": [
            ("color", "Цвет рубашки карт"),
            ("call", "Выгодно ли коллировать относительно банка"),
            ("name", "Как зовут соперника"),
        ],
        "answer": "call",
        "hint": "Сравнивают цену колла и размер банка.",
        "explain": "Пот-оддсы — цена продолжения vs размер банка.",
    },
    {
        "id": "micro-stakes",
        "title": "Выбор лимита",
        "theme": "стратегия",
        "level": "средне",
        "question": "При ~100 000 фишек разумнее…",
        "choices": [
            ("high", "Сразу высокий стол на 1 000 000"),
            ("micro", "Микро/малые столы"),
            ("all", "Олл-ин каждую раздачу"),
        ],
        "answer": "micro",
        "hint": "Берегите банкролл.",
        "explain": "Играйте лимит, где бай-ин не сжигает весь стек сразу.",
    },
    {
        "id": "royal",
        "title": "Роял-флеш",
        "theme": "комбинации",
        "level": "легко",
        "question": "Роял-флеш — это…",
        "choices": [
            ("any", "Любой стрит-флеш"),
            ("akqj10", "A‑K‑Q‑J‑10 одной масти"),
            ("pair", "Пара тузов"),
        ],
        "answer": "akqj10",
        "hint": "Самая старшая комбинация.",
        "explain": "Роял — стрит-флеш от десятки до туза.",
    },
    {
        "id": "seven-cards",
        "title": "Семь карт",
        "theme": "улицы",
        "level": "средне",
        "question": "На шоудауне сравнивают…",
        "choices": [
            ("two", "Только две карманные"),
            ("best5", "Лучшие 5 из семи"),
            ("all7", "Все 7 карт как одну комбинацию"),
        ],
        "answer": "best5",
        "hint": "2 hole + 5 board.",
        "explain": "Берут лучшую пятёрку из семи карт.",
    },
]

THEMES = ("комбинации", "действия", "улицы", "баланс", "позиция", "стратегия")


def puzzle_by_id(pid: str):
    for p in PUZZLES:
        if p["id"] == pid:
            return p
    return None


def check_answer(puzzle: dict, choice: str) -> bool:
    return (choice or "").strip() == puzzle["answer"]


def puzzles_by_theme(theme: str | None = None) -> list[dict]:
    if not theme or theme == "все":
        return list(PUZZLES)
    return [p for p in PUZZLES if p.get("theme") == theme]


def daily_puzzle(d: date | None = None) -> dict:
    d = d or date.today()
    raw = hashlib.md5(f"poker-daily-{d.isoformat()}".encode()).hexdigest()
    idx = int(raw[:8], 16) % len(PUZZLES)
    pz = dict(PUZZLES[idx])
    pz["daily"] = True
    return pz
