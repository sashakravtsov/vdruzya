"""Texas Hold'em rules: deck, deal, betting streets, 7-card hand evaluation."""
from __future__ import annotations

from itertools import combinations
import random

RANKS = "23456789TJQKA"
SUITS = "cdhs"
SUIT_GLYPH = {"c": "♣", "d": "♦", "h": "♥", "s": "♠"}
RANK_VALUE = {r: i for i, r in enumerate(RANKS, start=2)}

HAND_NAMES = (
    "старшая карта",
    "пара",
    "две пары",
    "сет",
    "стрит",
    "флеш",
    "фулл-хаус",
    "каре",
    "стрит-флеш",
    "роял-флеш",
)


def card_label(card: str) -> str:
    if not card or len(card) < 2:
        return card or ""
    return f"{card[0].replace('T', '10')}{SUIT_GLYPH.get(card[1], card[1])}"


def new_deck(seed: str | None = None) -> list[str]:
    deck = [r + s for r in RANKS for s in SUITS]
    rng = random.Random(seed)
    rng.shuffle(deck)
    return deck


def parse_cards(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [c.strip() for c in raw.split(",") if c.strip()]


def join_cards(cards: list[str]) -> str:
    return ",".join(cards)


def _is_straight(vals: list[int]) -> list[int] | None:
    """Return best 5-high straight values (Ace can be 1) or None."""
    uniq = sorted(set(vals), reverse=True)
    if 14 in uniq:
        uniq = uniq + [1]
    for i in range(len(uniq) - 4):
        window = uniq[i : i + 5]
        if window[0] - window[4] == 4 and len(window) == 5:
            # normalize wheel A-5 to 5-high
            if window[0] == 14 and window[4] == 1:
                return [5, 4, 3, 2, 1]
            return window
    return None


def evaluate_five(cards: list[str]) -> tuple:
    """Return comparable tuple (category, kickers...) — higher wins."""
    assert len(cards) == 5
    vals = sorted((RANK_VALUE[c[0]] for c in cards), reverse=True)
    suits = [c[1] for c in cards]
    flush = len(set(suits)) == 1
    straight = _is_straight(vals)
    counts: dict[int, int] = {}
    for v in vals:
        counts[v] = counts.get(v, 0) + 1
    by_count = sorted(counts.items(), key=lambda x: (x[1], x[0]), reverse=True)
    freqs = [c for _, c in by_count]
    ranks_by_freq = [v for v, _ in by_count]

    if flush and straight:
        if straight[0] == 14:
            return (9, 14)
        return (8, straight[0])
    if freqs[0] == 4:
        four = ranks_by_freq[0]
        kicker = max(v for v in vals if v != four)
        return (7, four, kicker)
    if freqs[0] == 3 and freqs[1] == 2:
        return (6, ranks_by_freq[0], ranks_by_freq[1])
    if flush:
        return (5, *vals)
    if straight:
        return (4, straight[0])
    if freqs[0] == 3:
        trips = ranks_by_freq[0]
        kickers = sorted((v for v in vals if v != trips), reverse=True)
        return (3, trips, *kickers[:2])
    if freqs[0] == 2 and freqs[1] == 2:
        high_p, low_p = sorted(ranks_by_freq[:2], reverse=True)
        kicker = max(v for v in vals if v not in (high_p, low_p))
        return (2, high_p, low_p, kicker)
    if freqs[0] == 2:
        pair = ranks_by_freq[0]
        kickers = sorted((v for v in vals if v != pair), reverse=True)
        return (1, pair, *kickers[:3])
    return (0, *vals)


def best_hand(hole: list[str], board: list[str]) -> tuple:
    cards = hole + board
    if len(cards) < 5:
        # pad evaluation with available (preflop strength approx not used for showdown)
        while len(cards) < 5:
            cards = cards + ["2c"]  # unreachable in showdown
    best = None
    for combo in combinations(cards, 5):
        score = evaluate_five(list(combo))
        if best is None or score > best:
            best = score
    return best or (0, 0)


def hand_name(score: tuple) -> str:
    cat = int(score[0]) if score else 0
    if 0 <= cat < len(HAND_NAMES):
        return HAND_NAMES[cat]
    return "рука"


def compare_hands(h1: list[str], h2: list[str], board: list[str]) -> int:
    """1 if h1 wins, -1 if h2 wins, 0 tie."""
    a = best_hand(h1, board)
    b = best_hand(h2, board)
    if a > b:
        return 1
    if a < b:
        return -1
    return 0


STREETS = ("preflop", "flop", "turn", "river", "showdown", "done")


def deal_hand(seed: str | None = None) -> dict:
    deck = new_deck(seed)
    p1 = [deck.pop(), deck.pop()]
    p2 = [deck.pop(), deck.pop()]
    return {
        "deck": deck,
        "p1_hole": p1,
        "p2_hole": p2,
        "board": [],
        "street": "preflop",
    }


def deal_board(deck: list[str], board: list[str], street: str) -> tuple[list[str], list[str], str]:
    deck = list(deck)
    board = list(board)
    if street == "preflop":
        # burn + 3
        if deck:
            deck.pop()
        board.extend([deck.pop(), deck.pop(), deck.pop()])
        return deck, board, "flop"
    if street == "flop":
        if deck:
            deck.pop()
        board.append(deck.pop())
        return deck, board, "turn"
    if street == "turn":
        if deck:
            deck.pop()
        board.append(deck.pop())
        return deck, board, "river"
    if street == "river":
        return deck, board, "showdown"
    return deck, board, street


def legal_actions(to_call: int, stack: int, bet: int, can_check: bool) -> list[str]:
    acts = ["fold"]
    if to_call <= 0:
        acts.append("check")
        if stack > 0:
            acts.append("bet")
            acts.append("allin")
    else:
        if stack > 0:
            if stack <= to_call:
                acts.append("allin")
            else:
                acts.append("call")
                acts.append("raise")
                acts.append("allin")
    # de-dupe preserve order
    out = []
    for a in acts:
        if a not in out:
            out.append(a)
    return out
