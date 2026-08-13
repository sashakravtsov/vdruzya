"""Multi-way Texas Hold'em state machine (2–6 seats) with side pots."""
from __future__ import annotations

import json
from copy import deepcopy

from . import engine

MAX_SEATS = 6
MIN_SEATS = 2


def empty_room_seats(max_seats: int) -> list:
    n = max(MIN_SEATS, min(MAX_SEATS, int(max_seats or 2)))
    return [None] * n


def dumps(obj) -> str:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def loads_list(raw, default=None):
    if default is None:
        default = []
    if not raw:
        return list(default)
    if isinstance(raw, (list, dict)):
        return raw
    try:
        data = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return list(default)
    return data if isinstance(data, list) else list(default)


def room_seat_count(seats: list) -> int:
    return sum(1 for s in seats if s)


def room_add_user(seats: list, user_id: int) -> list:
    seats = list(seats)
    if user_id in seats:
        return seats
    for i, s in enumerate(seats):
        if s is None:
            seats[i] = user_id
            return seats
    raise ValueError("Нет свободных мест")


def room_remove_user(seats: list, user_id: int) -> list:
    return [None if s == user_id else s for s in seats]


def next_idx(i: int, n: int) -> int:
    return (i + 1) % n


def prev_idx(i: int, n: int) -> int:
    return (i - 1) % n


def active_indices(seats: list[dict]) -> list[int]:
    return [i for i, s in enumerate(seats) if not s.get("folded")]


def can_act_indices(seats: list[dict]) -> list[int]:
    return [
        i for i, s in enumerate(seats)
        if not s.get("folded") and not s.get("all_in") and int(s.get("stack") or 0) >= 0
    ]


def new_hand_seats(user_ids: list[int], buy_in: int, deck: list[str]) -> list[dict]:
    seats = []
    for uid in user_ids:
        hole = [deck.pop(), deck.pop()]
        seats.append({
            "u": int(uid),
            "stack": int(buy_in),
            "bet": 0,
            "invested": 0,
            "hole": engine.join_cards(hole),
            "folded": False,
            "all_in": False,
            "acted": False,
        })
    return seats


def post_blinds(seats: list[dict], button: int, sb: int, bb: int) -> tuple[list[dict], int, int, int]:
    """Return seats, to_act, pot, current_bet."""
    n = len(seats)
    if n < 2:
        raise ValueError("Нужно минимум 2 игрока")
    if n == 2:
        sb_i = button
        bb_i = next_idx(button, n)
        to_act = button  # HU: SB/button acts first preflop
    else:
        sb_i = next_idx(button, n)
        bb_i = next_idx(sb_i, n)
        to_act = next_idx(bb_i, n)

    pot = 0
    for i, amount in ((sb_i, sb), (bb_i, bb)):
        paid = min(int(seats[i]["stack"]), amount)
        seats[i]["stack"] -= paid
        seats[i]["bet"] += paid
        seats[i]["invested"] += paid
        pot += paid
        if seats[i]["stack"] == 0:
            seats[i]["all_in"] = True
    current_bet = max(s["bet"] for s in seats)
    return seats, to_act, pot, current_bet


def _pay(seat: dict, amount: int) -> int:
    pay = min(int(seat["stack"]), max(0, int(amount)))
    seat["stack"] -= pay
    seat["bet"] += pay
    seat["invested"] += pay
    if seat["stack"] == 0:
        seat["all_in"] = True
    return pay


def betting_closed(seats: list[dict], current_bet: int) -> bool:
    contenders = active_indices(seats)
    if len(contenders) <= 1:
        return True
    actors = can_act_indices(seats)
    if not actors:
        return True  # all-in runout
    for i in actors:
        s = seats[i]
        if int(s["bet"]) < current_bet:
            return False
        if not s.get("acted"):
            return False
    return True


def next_to_act(seats: list[dict], from_i: int) -> int | None:
    n = len(seats)
    i = from_i
    for _ in range(n):
        i = next_idx(i, n)
        s = seats[i]
        if s.get("folded") or s.get("all_in"):
            continue
        return i
    return None


def apply_action(
    seats: list[dict],
    actor: int,
    action: str,
    raise_to: int,
    current_bet: int,
    big_blind: int,
    pot: int,
) -> tuple[list[dict], int, int, str, int]:
    """Apply action. Returns seats, pot, current_bet, label, paid."""
    seats = deepcopy(seats)
    s = seats[actor]
    if s.get("folded") or s.get("all_in"):
        raise ValueError("Сейчас нельзя ходить")
    action = (action or "").strip().lower()
    my_bet = int(s["bet"])
    to_call = max(0, current_bet - my_bet)
    legal = engine.legal_actions(to_call, int(s["stack"]), my_bet, to_call == 0)
    if action == "bet" and "bet" not in legal and "raise" in legal:
        action = "raise"
    if action not in legal and not (action == "raise" and "bet" in legal):
        raise ValueError("Это действие сейчас нельзя")

    paid = 0
    label = action
    if action == "fold":
        s["folded"] = True
        s["acted"] = True
        label = "фолд"
    elif action == "check":
        s["acted"] = True
        label = "чек"
    elif action == "call":
        paid = _pay(s, to_call)
        s["acted"] = True
        label = f"колл {paid}"
    elif action in ("bet", "raise", "allin"):
        if action == "allin":
            target = my_bet + int(s["stack"])
        else:
            min_to = current_bet + big_blind if current_bet > 0 else big_blind
            target = int(raise_to or 0)
            if target < min_to and target < my_bet + int(s["stack"]):
                target = min_to
            target = max(0, min(target, my_bet + int(s["stack"])))
            if target <= my_bet and action != "allin":
                raise ValueError("Укажите размер ставки")
        paid = _pay(s, target - my_bet)
        if target > current_bet:
            current_bet = int(s["bet"])
            for other in seats:
                if other is s or other.get("folded") or other.get("all_in"):
                    continue
                other["acted"] = False
        s["acted"] = True
        if s["all_in"] or action == "allin":
            label = f"олл-ин {paid}"
        elif action == "bet":
            label = f"ставка {paid}"
        else:
            label = f"рейз до {s['bet']}"
    pot += paid
    return seats, pot, current_bet, label, paid


def reset_street_bets(seats: list[dict]) -> list[dict]:
    for s in seats:
        s["bet"] = 0
        s["acted"] = False
    return seats


def only_one_left(seats: list[dict]) -> int | None:
    alive = active_indices(seats)
    return alive[0] if len(alive) == 1 else None


def best_showdown(seats: list[dict], board: list[str]) -> list[int]:
    """Indices of winners among non-folded (ties allowed)."""
    alive = active_indices(seats)
    if not alive:
        return []
    scores = []
    for i in alive:
        hole = engine.parse_cards(seats[i].get("hole") or "")
        scores.append((i, engine.best_hand(hole, board)))
    best = max(sc for _, sc in scores)
    return [i for i, sc in scores if sc == best]


def distribute_side_pots(seats: list[dict], board: list[str]) -> tuple[list[dict], list[str], int | None]:
    """
    Award chips from invested amounts via side pots.
    Returns updated seats (stacks increased), notes, primary winner user_id or None if chop.
    """
    seats = deepcopy(seats)
    notes: list[str] = []
    # Eligible contributors ordered by invested
    invested_players = [s for s in seats if int(s.get("invested") or 0) > 0]
    if not invested_players:
        return seats, notes, None

    levels = sorted({int(s["invested"]) for s in invested_players})
    prev = 0
    winner_ids: list[int] = []
    for level in levels:
        layer = level - prev
        if layer <= 0:
            continue
        contributors = [s for s in seats if int(s["invested"]) >= level]
        pot_amt = layer * len(contributors)
        eligible = [s for s in contributors if not s.get("folded")]
        if not eligible:
            # all folded oddity — return to last aggressor-like: first contributor
            eligible = contributors[:1]
        # map to indices for showdown among eligible
        el_idx = [seats.index(s) for s in eligible]
        # restrict showdown to these seats only
        if len(board) >= 3 or all(s.get("folded") for s in seats if s not in eligible):
            # compare hands among eligible; if board short (fold-win), single eligible
            if len(eligible) == 1 or len(board) < 3:
                winners = el_idx[:1] if el_idx else []
            else:
                # score only among eligible
                scores = []
                for i in el_idx:
                    hole = engine.parse_cards(seats[i].get("hole") or "")
                    scores.append((i, engine.best_hand(hole, board)))
                best = max(sc for _, sc in scores)
                winners = [i for i, sc in scores if sc == best]
        else:
            winners = el_idx[:1]

        if not winners:
            prev = level
            continue
        share = pot_amt // len(winners)
        rem = pot_amt - share * len(winners)
        for j, i in enumerate(winners):
            gain = share + (rem if j == 0 else 0)
            seats[i]["stack"] += gain
            winner_ids.append(seats[i]["u"])
        if len(winners) == 1:
            notes.append(f"банк {pot_amt} → место {winners[0] + 1}")
        else:
            notes.append(f"банк {pot_amt} · дележ x{len(winners)}")
        prev = level

    primary = None
    if winner_ids:
        # most frequent / first
        primary = max(set(winner_ids), key=winner_ids.count)
        if winner_ids.count(primary) == len(winner_ids) and len(set(winner_ids)) > 1:
            # true multi-way chop across layers
            if len(set(winner_ids)) > 1 and all(winner_ids.count(x) == winner_ids.count(primary) for x in set(winner_ids)):
                primary = None
    return seats, notes, primary


def hand_label_for(seats: list[dict], board: list[str], names: dict[int, str]) -> str:
    parts = []
    for s in seats:
        if s.get("folded"):
            continue
        hole = engine.parse_cards(s.get("hole") or "")
        if len(board) >= 3 and len(hole) == 2:
            nm = names.get(int(s["u"]), str(s["u"]))
            parts.append(f"{nm}: {engine.hand_name(engine.best_hand(hole, board))}")
    return " · ".join(parts)[:240]


def seats_to_hu_mirror(seats: list[dict]) -> dict:
    """Mirror first two seats into classic p1/p2 columns for compatibility."""
    p1 = seats[0] if seats else {}
    p2 = seats[1] if len(seats) > 1 else {}
    return {
        "p1_stack": int(p1.get("stack") or 0),
        "p2_stack": int(p2.get("stack") or 0),
        "p1_bet": int(p1.get("bet") or 0),
        "p2_bet": int(p2.get("bet") or 0),
        "p1_hole": p1.get("hole") or "",
        "p2_hole": p2.get("hole") or "",
    }
