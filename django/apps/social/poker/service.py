"""Poker services: chips, rooms, rating, weekly championship, Hold'em, learning."""
from __future__ import annotations

import secrets
import string
from datetime import date, timedelta

from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.social.models import SocialProfile
from apps.social.services import now as _now

from . import engine
from .models import (
    PokerAction, PokerChampEntry, PokerChampionship, PokerGame, PokerLessonProgress,
    PokerProfile, PokerPuzzleProgress, PokerRoom,
)

STARTING_CHIPS = 1_000_000
BANKRUPT_DAYS = 5
MIN_PLAYABLE_CHIPS = 20_000

STAKE_LEVELS = (
    # key, label, SB, BB, buy_in
    ("micro", "Микро · 500/1 000 · бай-ин 20 000", 500, 1000, 20_000),
    ("small", "Малые · 2 500/5 000 · бай-ин 100 000", 2500, 5000, 100_000),
    ("mid", "Средние · 10 000/20 000 · бай-ин 400 000", 10_000, 20_000, 400_000),
    ("high", "Высокие · 25 000/50 000 · бай-ин 1 000 000", 25_000, 50_000, 1_000_000),
)


def stake_by_key(key: str) -> tuple:
    for row in STAKE_LEVELS:
        if row[0] == key:
            return row
    return STAKE_LEVELS[0]


def week_key(d: date | None = None) -> str:
    d = d or date.today()
    iso = d.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def week_bounds(d: date | None = None) -> tuple[date, date]:
    d = d or date.today()
    start = d - timedelta(days=d.weekday())
    end = start + timedelta(days=6)
    return start, end


def ensure_week_championship(d: date | None = None) -> PokerChampionship:
    d = d or date.today()
    key = week_key(d)
    cache_key = f"poker:champ:{key}"
    cached_id = cache.get(cache_key)
    if cached_id:
        obj = PokerChampionship.objects.filter(pk=cached_id).first()
        if obj:
            return obj
    start, end = week_bounds(d)
    obj = PokerChampionship.objects.filter(week_key=key).first()
    if not obj:
        title = f"Чемпионат недели {start.strftime('%d.%m')}–{end.strftime('%d.%m.%Y')}"
        obj = PokerChampionship.objects.create(
            week_key=key,
            title=title,
            starts_on=start,
            ends_on=end,
            status="open",
            created_at=_now(),
        )
    cache.set(cache_key, obj.id, 3600)
    return obj


def elo_update(winner_r: int, loser_r: int, draw: bool = False, k: int = 32) -> tuple[int, int]:
    expected_w = 1 / (1 + 10 ** ((loser_r - winner_r) / 400))
    expected_l = 1 - expected_w
    if draw:
        score_w, score_l = 0.5, 0.5
    else:
        score_w, score_l = 1.0, 0.0
    new_w = int(round(winner_r + k * (score_w - expected_w)))
    new_l = int(round(loser_r + k * (score_l - expected_l)))
    return max(100, new_w), max(100, new_l)


def get_or_create_profile(user: SocialProfile) -> PokerProfile:
    row, created = PokerProfile.objects.get_or_create(
        social_user=user,
        defaults={
            "chips": STARTING_CHIPS,
            "rating": 1200,
            "rated_games": 0,
            "created_at": _now(),
            "updated_at": _now(),
        },
    )
    if created:
        return row
    if getattr(row, "rating", None) is None:
        row.rating = 1200
        row.save(update_fields=["rating"])
    return row


def _new_join_code(n: int = 6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    for _ in range(12):
        code = "".join(secrets.choice(alphabet) for _ in range(n))
        if not PokerRoom.objects.filter(join_code=code, status__in=["open", "playing"]).exists():
            return code
    return secrets.token_hex(3).upper()


def is_bankrupt(profile: PokerProfile, at=None) -> bool:
    at = at or timezone.now()
    until = profile.bankrupt_until
    if until and until > at:
        return True
    return False


def can_reset_bankruptcy(profile: PokerProfile, at=None) -> bool:
    at = at or timezone.now()
    until = profile.bankrupt_until
    if not until:
        return False
    return until <= at


def bankrupt_remaining(profile: PokerProfile, at=None) -> timedelta | None:
    at = at or timezone.now()
    until = profile.bankrupt_until
    if not until or until <= at:
        return None
    return until - at


def _mark_bankrupt(profile: PokerProfile) -> None:
    profile.chips = 0
    profile.bankrupt_until = timezone.now() + timedelta(days=BANKRUPT_DAYS)
    profile.updated_at = _now()
    profile.save(update_fields=["chips", "bankrupt_until", "updated_at"])


@transaction.atomic
def reset_after_bankruptcy(user: SocialProfile) -> PokerProfile:
    profile = get_or_create_profile(user)
    if not can_reset_bankruptcy(profile):
        if is_bankrupt(profile):
            left = bankrupt_remaining(profile)
            days = max(1, int((left.total_seconds() + 86399) // 86400)) if left else BANKRUPT_DAYS
            raise ValueError(f"Банкротство ещё действует. Подождите ~{days} дн.")
        raise ValueError("Сброс доступен только после банкротства")
    profile.chips = STARTING_CHIPS
    profile.bankrupt_until = None
    profile.reset_count = int(profile.reset_count or 0) + 1
    profile.updated_at = _now()
    profile.save(update_fields=["chips", "bankrupt_until", "reset_count", "updated_at"])
    return profile


def skill_level(xp: int) -> dict:
    xp = int(xp or 0)
    level = 1 + xp // 100
    into = xp % 100
    return {"level": level, "xp": xp, "into": into, "next_at": level * 100}


def add_learn_xp(user: SocialProfile, amount: int) -> PokerProfile:
    profile = get_or_create_profile(user)
    profile.learn_xp = int(profile.learn_xp or 0) + max(0, int(amount))
    profile.updated_at = _now()
    profile.save(update_fields=["learn_xp", "updated_at"])
    return profile


def seat_of(game: PokerGame, user: SocialProfile) -> int | None:
    if game.p1_id == user.id:
        return 1
    if game.p2_id == user.id:
        return 2
    return None


def opp_of(game: PokerGame, user: SocialProfile) -> SocialProfile:
    return game.p2 if game.p1_id == user.id else game.p1


def game_for(user: SocialProfile, gid: int) -> PokerGame | None:
    return (
        PokerGame.objects.filter(Q(p1=user) | Q(p2=user), pk=gid)
        .select_related("p1", "p2", "invited_by", "winner")
        .first()
    )


@transaction.atomic
def challenge(
    inviter: SocialProfile,
    invitee: SocialProfile,
    stake_key: str = "micro",
    in_champ: bool = True,
) -> PokerGame:
    if inviter.id == invitee.id:
        raise ValueError("Нельзя вызвать самого себя")
    a = get_or_create_profile(inviter)
    b = get_or_create_profile(invitee)
    if is_bankrupt(a):
        raise ValueError("Вы банкрот — игра недоступна до конца срока или сброса")
    if is_bankrupt(b):
        raise ValueError("Соперник сейчас банкрот и не может принять вызов")
    _key, _label, sb, bb, buy = stake_by_key(stake_key)
    if a.chips < buy:
        raise ValueError(f"Не хватает фишек для бай-ина {buy:,}".replace(",", " "))
    if b.chips < buy:
        raise ValueError("У соперника недостаточно фишек на этот лимит")
    now = _now()
    champ = ensure_week_championship() if in_champ else None
    return PokerGame.objects.create(
        p1=inviter,
        p2=invitee,
        invited_by=inviter,
        status="pending",
        result="*",
        small_blind=sb,
        big_blind=bb,
        buy_in=buy,
        button=1,
        to_act=1,
        street="preflop",
        championship=champ,
        is_rated=True,
        created_at=now,
        updated_at=now,
    )


def _post_blinds(game: PokerGame) -> None:
    sb_seat = game.button  # heads-up: button posts SB
    bb_seat = 2 if sb_seat == 1 else 1
    sb, bb = game.small_blind, game.big_blind

    def pay(seat: int, amount: int) -> int:
        stack = game.p1_stack if seat == 1 else game.p2_stack
        paid = min(stack, amount)
        if seat == 1:
            game.p1_stack -= paid
            game.p1_bet += paid
        else:
            game.p2_stack -= paid
            game.p2_bet += paid
        game.pot += paid
        return paid

    pay(sb_seat, sb)
    pay(bb_seat, bb)
    # first to act preflop HU = button (SB)
    game.to_act = sb_seat


@transaction.atomic
def accept_challenge(user: SocialProfile, game_id: int) -> PokerGame:
    game = PokerGame.objects.select_for_update().filter(pk=game_id).first()
    if not game or game.status != "pending":
        raise ValueError("Вызов не найден")
    if game.invited_by_id == user.id:
        raise ValueError("Ждите ответа соперника")
    if seat_of(game, user) is None:
        raise ValueError("Это не ваш вызов")
    a = get_or_create_profile(game.p1)
    b = get_or_create_profile(game.p2)
    for p in (a, b):
        if is_bankrupt(p):
            raise ValueError("Банкротство мешает начать раздачу")
        if p.chips < game.buy_in:
            raise ValueError("Недостаточно фишек для бай-ина")
    # lock chips into stacks
    a.chips -= game.buy_in
    b.chips -= game.buy_in
    a.updated_at = b.updated_at = _now()
    a.save(update_fields=["chips", "updated_at"])
    b.save(update_fields=["chips", "updated_at"])

    dealt = engine.deal_hand(seed=f"poker-{game.id}-{_now().timestamp()}")
    game.p1_stack = game.buy_in
    game.p2_stack = game.buy_in
    game.p1_bet = 0
    game.p2_bet = 0
    game.pot = 0
    game.p1_hole = engine.join_cards(dealt["p1_hole"])
    game.p2_hole = engine.join_cards(dealt["p2_hole"])
    game.board = ""
    game.deck = engine.join_cards(dealt["deck"])
    game.street = "preflop"
    game.button = 1
    game.status = "active"
    game.updated_at = _now()
    _post_blinds(game)
    game.last_action = "раздача · блайнды"
    game.save()
    return game


@transaction.atomic
def decline_challenge(user: SocialProfile, game_id: int) -> None:
    game = PokerGame.objects.select_for_update().filter(pk=game_id).first()
    if not game or game.status != "pending":
        raise ValueError("Вызов не найден")
    if seat_of(game, user) is None or game.invited_by_id == user.id:
        raise ValueError("Отклонить может только приглашённый")
    game.status = "cancelled"
    game.result = "cancel"
    game.updated_at = _now()
    game.save(update_fields=["status", "result", "updated_at"])


@transaction.atomic
def cancel_challenge(user: SocialProfile, game_id: int) -> None:
    game = PokerGame.objects.select_for_update().filter(pk=game_id).first()
    if not game or game.status != "pending":
        raise ValueError("Вызов не найден")
    if game.invited_by_id != user.id:
        raise ValueError("Отменить может только пригласивший")
    game.status = "cancelled"
    game.result = "cancel"
    game.updated_at = _now()
    game.save(update_fields=["status", "result", "updated_at"])


def _stacks_bets(game: PokerGame, seat: int) -> tuple[int, int, int, int]:
    if seat == 1:
        return game.p1_stack, game.p1_bet, game.p2_stack, game.p2_bet
    return game.p2_stack, game.p2_bet, game.p1_stack, game.p1_bet


def _set_stack_bet(game: PokerGame, seat: int, stack: int, bet: int) -> None:
    if seat == 1:
        game.p1_stack, game.p1_bet = stack, bet
    else:
        game.p2_stack, game.p2_bet = stack, bet


def _log(game: PokerGame, user: SocialProfile, action: str, amount: int = 0) -> None:
    ply = PokerAction.objects.filter(game=game).count() + 1
    PokerAction.objects.create(
        game=game,
        ply=ply,
        actor=user,
        action=action,
        amount=amount,
        street=game.street,
        pot_after=game.pot,
        created_at=_now(),
    )


def _apply_rating_and_champ(game: PokerGame, p1: PokerProfile, p2: PokerProfile) -> None:
    if game.is_rated:
        r1, r2 = int(p1.rating or 1200), int(p2.rating or 1200)
        if game.result == "tie":
            n1, n2 = elo_update(r1, r2, draw=True)
        elif game.result == "p1":
            n1, n2 = elo_update(r1, r2, draw=False)
        elif game.result == "p2":
            n2, n1 = elo_update(r2, r1, draw=False)
        else:
            n1, n2 = r1, r2
        p1.rating, p2.rating = n1, n2
        p1.rated_games = int(p1.rated_games or 0) + 1
        p2.rated_games = int(p2.rated_games or 0) + 1

    if game.championship_id:
        champ = game.championship
        e1, _ = PokerChampEntry.objects.get_or_create(
            championship=champ, social_user=game.p1,
            defaults={"points": 0, "wins": 0, "losses": 0, "ties": 0},
        )
        e2, _ = PokerChampEntry.objects.get_or_create(
            championship=champ, social_user=game.p2,
            defaults={"points": 0, "wins": 0, "losses": 0, "ties": 0},
        )
        if game.result == "p1":
            e1.points += 3
            e1.wins += 1
            e2.losses += 1
        elif game.result == "p2":
            e2.points += 3
            e2.wins += 1
            e1.losses += 1
        elif game.result == "tie":
            e1.points += 1
            e2.points += 1
            e1.ties += 1
            e2.ties += 1
        e1.save()
        e2.save()


def _release_room_after_hand(game: PokerGame) -> None:
    if not game.room_id:
        return
    room = PokerRoom.objects.filter(pk=game.room_id).first()
    if not room or room.status == "closed":
        return
    room.hands_played = int(room.hands_played or 0) + 1
    room.status = "open"
    room.updated_at = _now()
    room.save(update_fields=["hands_played", "status", "updated_at"])


def _finish(game: PokerGame, winner_seat: int | None, reason: str) -> PokerGame:
    """winner_seat 1/2 or None for tie. Return chips to profiles."""
    p1 = get_or_create_profile(game.p1)
    p2 = get_or_create_profile(game.p2)
    # leftover stacks + pot distribution
    if winner_seat == 1:
        p1.chips += game.p1_stack + game.pot
        p2.chips += game.p2_stack
        game.result = "p1"
        game.winner = game.p1
        p1.wins += 1
        p2.losses += 1
        p1.biggest_pot = max(int(p1.biggest_pot or 0), int(game.pot))
    elif winner_seat == 2:
        p2.chips += game.p2_stack + game.pot
        p1.chips += game.p1_stack
        game.result = "p2"
        game.winner = game.p2
        p2.wins += 1
        p1.losses += 1
        p2.biggest_pot = max(int(p2.biggest_pot or 0), int(game.pot))
    else:
        half = game.pot // 2
        rem = game.pot - half
        p1.chips += game.p1_stack + half
        p2.chips += game.p2_stack + rem
        game.result = "tie"
        game.winner = None
        p1.ties += 1
        p2.ties += 1
    p1.games += 1
    p2.games += 1
    _apply_rating_and_champ(game, p1, p2)
    game.pot = 0
    game.p1_stack = 0
    game.p2_stack = 0
    game.status = "done"
    game.street = "done"
    game.to_act = 0
    game.last_action = reason
    game.updated_at = _now()
    game.save()
    for p in (p1, p2):
        p.updated_at = _now()
        p.save()
        if int(p.chips or 0) < MIN_PLAYABLE_CHIPS:
            _mark_bankrupt(p)
    _release_room_after_hand(game)
    return game


def _advance_street(game: PokerGame) -> None:
    game.p1_bet = 0
    game.p2_bet = 0
    if game.street == "river":
        # showdown
        h1 = engine.parse_cards(game.p1_hole)
        h2 = engine.parse_cards(game.p2_hole)
        board = engine.parse_cards(game.board)
        cmp = engine.compare_hands(h1, h2, board)
        s1 = engine.best_hand(h1, board)
        s2 = engine.best_hand(h2, board)
        game.hand_label = (
            f"{game.p1.name}: {engine.hand_name(s1)} · {game.p2.name}: {engine.hand_name(s2)}"
        )
        game.street = "showdown"
        if cmp > 0:
            _finish(game, 1, "шоудаун · победа " + game.p1.name)
        elif cmp < 0:
            _finish(game, 2, "шоудаун · победа " + game.p2.name)
        else:
            _finish(game, None, "шоудаун · ничья")
        return
    deck = engine.parse_cards(game.deck)
    board = engine.parse_cards(game.board)
    deck, board, street = engine.deal_board(deck, board, game.street)
    game.deck = engine.join_cards(deck)
    game.board = engine.join_cards(board)
    game.street = street
    # first to act postflop HU = non-button
    game.to_act = 2 if game.button == 1 else 1
    # if that seat is all-in already and both all-in, runout
    if game.p1_stack == 0 and game.p2_stack == 0:
        while game.street not in ("showdown", "done") and game.status == "active":
            if game.street == "river":
                game.p1_bet = game.p2_bet = 0
                _advance_street(game)
                return
            deck = engine.parse_cards(game.deck)
            board = engine.parse_cards(game.board)
            deck, board, street = engine.deal_board(deck, board, game.street)
            game.deck = engine.join_cards(deck)
            game.board = engine.join_cards(board)
            game.street = street
        if game.street == "river" and game.status == "active":
            game.p1_bet = game.p2_bet = 0
            _advance_street(game)


@transaction.atomic
def act(
    user: SocialProfile,
    game_id: int,
    action: str,
    raise_to: int = 0,
) -> PokerGame:
    game = PokerGame.objects.select_for_update().filter(pk=game_id).first()
    if not game or game.status != "active":
        raise ValueError("Раздача недоступна")
    seat = seat_of(game, user)
    if not seat or seat != game.to_act:
        raise ValueError("Сейчас не ваш ход")
    action = (action or "").strip().lower()
    my_stack, my_bet, opp_stack, opp_bet = _stacks_bets(game, seat)
    to_call = max(0, opp_bet - my_bet)
    legal = engine.legal_actions(to_call, my_stack, my_bet, to_call == 0)
    if action == "bet" and "bet" not in legal and "raise" in legal:
        action = "raise"
    if action not in legal and not (action == "raise" and "bet" in legal):
        raise ValueError("Это действие сейчас нельзя")

    if action == "fold":
        _log(game, user, "fold")
        winner = 2 if seat == 1 else 1
        return _finish(game, winner, f"{user.name} сбросил карты")

    if action == "check":
        prior = PokerAction.objects.filter(game=game, street=game.street).count()
        _log(game, user, "check")
        game.last_action = f"{user.name}: чек"
        other = 2 if seat == 1 else 1
        # Second check on a matched street closes the round.
        if my_bet == opp_bet and prior >= 1:
            _advance_street(game)
        else:
            game.to_act = other
        game.updated_at = _now()
        if game.status == "active":
            game.save()
        return game

    if action == "call":
        pay = min(my_stack, to_call)
        my_stack -= pay
        my_bet += pay
        game.pot += pay
        _set_stack_bet(game, seat, my_stack, my_bet)
        _log(game, user, "call", pay)
        game.last_action = f"{user.name}: колл {pay}"
        # Matched bets after a call always close the betting round.
        if my_stack == 0 or opp_stack == 0:
            game.to_act = 0
            while game.status == "active" and game.street not in ("done", "showdown"):
                prev = game.street
                _advance_street(game)
                if game.status != "active" or game.street == prev:
                    break
            game.updated_at = _now()
            if game.status == "active":
                game.save()
            return game
        _advance_street(game)
        game.updated_at = _now()
        if game.status == "active":
            game.save()
        return game

    if action in ("bet", "raise", "allin"):
        if action == "allin":
            pay = my_stack
            new_bet = my_bet + pay
        else:
            # raise_to is total bet on street for actor
            target = int(raise_to or 0)
            min_raise_to = opp_bet + game.big_blind if opp_bet > 0 else game.big_blind
            if target < min_raise_to and target < my_bet + my_stack:
                target = min_raise_to
            max_to = my_bet + my_stack
            target = max(0, min(target, max_to))
            pay = target - my_bet
            if pay <= 0:
                raise ValueError("Укажите размер ставки")
            new_bet = my_bet + pay
        my_stack -= pay
        my_bet = new_bet
        game.pot += pay
        _set_stack_bet(game, seat, my_stack, my_bet)
        label = "олл-ин" if my_stack == 0 or action == "allin" else ("ставка" if action == "bet" else "рейз")
        _log(game, user, action, pay)
        game.last_action = f"{user.name}: {label} {pay}"
        other = 2 if seat == 1 else 1
        # if opponent has 0 stack and bets matched → runout
        _os, ob, = (game.p2_stack, game.p2_bet) if other == 2 else (game.p1_stack, game.p1_bet)
        if _os == 0 and my_bet >= ob:
            while game.status == "active" and game.street not in ("done",):
                prev = game.street
                if game.street == "showdown":
                    break
                _advance_street(game)
                if game.status != "active" or game.street == prev:
                    break
            game.updated_at = _now()
            if game.status == "active":
                game.save()
            return game
        game.to_act = other
        game.updated_at = _now()
        game.save()
        return game

    raise ValueError("Неизвестное действие")


def play_hub(user: SocialProfile) -> dict:
    open_games = list(
        PokerGame.objects.filter(Q(p1=user) | Q(p2=user))
        .filter(status__in=["pending", "active"])
        .select_related("p1", "p2", "invited_by")
        .order_by("-updated_at")[:40]
    )
    your_act, waiting, incoming, outgoing = [], [], [], []
    for g in open_games:
        if g.status == "pending":
            if g.invited_by_id == user.id:
                outgoing.append(g)
            else:
                incoming.append(g)
            continue
        seat = seat_of(g, user)
        if seat and seat == g.to_act:
            your_act.append(g)
        else:
            waiting.append(g)
    return {
        "your_act": your_act,
        "waiting": waiting,
        "incoming": incoming,
        "outgoing": outgoing,
        "your_act_n": len(your_act),
        "incoming_n": len(incoming),
        "waiting_n": len(waiting),
        "outgoing_n": len(outgoing),
    }


def engagement_strip(user: SocialProfile) -> dict:
    hub = play_hub(user)
    p = get_or_create_profile(user)
    left = bankrupt_remaining(p)
    champ = ensure_week_championship()
    my_rooms = list(
        PokerRoom.objects.filter(Q(p1=user) | Q(p2=user) | Q(owner=user))
        .exclude(status="closed")
        .order_by("-updated_at")[:8]
    )
    chips = int(p.chips or 0)
    return {
        **hub,
        "chips": chips,
        "chips_fmt": engine.format_chips(chips),
        "wins": int(p.wins or 0),
        "games": int(p.games or 0),
        "rating": int(p.rating or 1200),
        "rated_games": int(p.rated_games or 0),
        "skill": skill_level(p.learn_xp),
        "puzzle_streak": int(p.puzzle_streak or 0),
        "bankrupt": is_bankrupt(p),
        "can_reset": can_reset_bankruptcy(p),
        "bankrupt_days_left": (
            max(1, int((left.total_seconds() + 86399) // 86400)) if left else 0
        ),
        "reset_count": int(p.reset_count or 0),
        "starting_chips": STARTING_CHIPS,
        "starting_chips_fmt": engine.format_chips(STARTING_CHIPS),
        "champ": champ,
        "my_rooms": my_rooms,
        "my_rooms_n": len(my_rooms),
        "win_rate": (
            int(round(100 * int(p.wins or 0) / int(p.games))) if int(p.games or 0) else 0
        ),
    }


def table_view(game: PokerGame, viewer: SocialProfile) -> dict:
    seat = seat_of(game, viewer) or 0
    board = engine.parse_cards(game.board)
    my_hole = engine.parse_cards(game.p1_hole if seat == 1 else game.p2_hole) if seat else []
    opp_hole = []
    if game.status == "done" or game.street in ("showdown", "done"):
        opp_hole = engine.parse_cards(game.p2_hole if seat == 1 else game.p1_hole) if seat else []
        if not seat:
            opp_hole = engine.parse_cards(game.p2_hole)
            my_hole = engine.parse_cards(game.p1_hole)
    my_stack, my_bet, opp_stack, opp_bet = (
        _stacks_bets(game, seat) if seat else (game.p1_stack, game.p1_bet, game.p2_stack, game.p2_bet)
    )
    to_call = max(0, opp_bet - my_bet) if seat else 0
    legal = []
    if seat and game.status == "active" and seat == game.to_act:
        legal = engine.legal_actions(to_call, my_stack, my_bet, to_call == 0)
    min_raise_to = max(opp_bet + game.big_blind, game.big_blind)
    pot = int(game.pot or 0)
    half_pot = max(min_raise_to, my_bet + max(to_call, pot // 2))
    pot_raise = max(min_raise_to, my_bet + max(to_call, pot))
    max_raise = my_bet + my_stack
    half_pot = min(half_pot, max_raise) if max_raise else half_pot
    pot_raise = min(pot_raise, max_raise) if max_raise else pot_raise

    hand_strength = ""
    if my_hole and len(board) >= 3:
        hand_strength = engine.hand_name(engine.best_hand(my_hole, board))
    elif my_hole and len(my_hole) == 2:
        # light preflop hint
        r1, r2 = my_hole[0][0], my_hole[1][0]
        suited = my_hole[0][1] == my_hole[1][1]
        if r1 == r2:
            hand_strength = "пара на руках"
        elif suited:
            hand_strength = "suited"
        else:
            hand_strength = "offsuit"

    street = game.street or "preflop"
    streets = ["preflop", "flop", "turn", "river"]
    street_idx = streets.index(street) if street in streets else (
        4 if street in ("showdown", "done") else 0
    )
    opp_seat = 2 if seat == 1 else (1 if seat == 2 else 0)
    i_am_dealer = bool(seat and seat == game.button)
    opp_is_dealer = bool(opp_seat and opp_seat == game.button)
    waiting = bool(
        game.status == "active" and seat and not legal and game.to_act and game.to_act != seat
    )
    board_slots = [engine.card_view(c) for c in board]
    while len(board_slots) < 5:
        board_slots.append(None)

    return {
        "seat": seat,
        "board": board,
        "board_labels": [engine.card_label(c) for c in board],
        "board_cards": [engine.card_view(c) for c in board],
        "board_slots": board_slots,
        "my_hole": my_hole,
        "my_labels": [engine.card_label(c) for c in my_hole],
        "my_cards": [engine.card_view(c) for c in my_hole],
        "opp_hole": opp_hole,
        "opp_labels": [engine.card_label(c) for c in opp_hole],
        "opp_cards": [engine.card_view(c) for c in opp_hole],
        "my_stack": my_stack,
        "opp_stack": opp_stack,
        "my_bet": my_bet,
        "opp_bet": opp_bet,
        "my_stack_fmt": engine.format_chips(my_stack),
        "opp_stack_fmt": engine.format_chips(opp_stack),
        "my_bet_fmt": engine.format_chips(my_bet),
        "opp_bet_fmt": engine.format_chips(opp_bet),
        "to_call": to_call,
        "to_call_fmt": engine.format_chips(to_call),
        "legal": legal,
        "pot": pot,
        "pot_fmt": engine.format_chips(pot),
        "street": street,
        "street_label": engine.street_label(street),
        "street_idx": street_idx,
        "streets": [
            {"key": s, "label": engine.street_label(s), "on": i <= street_idx}
            for i, s in enumerate(streets)
        ],
        "can_act": bool(legal),
        "waiting": waiting,
        "min_raise_to": min_raise_to,
        "min_raise_fmt": engine.format_chips(min_raise_to),
        "half_pot_to": half_pot,
        "pot_raise_to": pot_raise,
        "max_raise_to": max_raise,
        "hand_strength": hand_strength,
        "i_am_dealer": i_am_dealer,
        "opp_is_dealer": opp_is_dealer,
        "room_id": game.room_id,
        "sb_fmt": engine.format_chips(game.small_blind),
        "bb_fmt": engine.format_chips(game.big_blind),
        "buy_in_fmt": engine.format_chips(game.buy_in),
        "opp_name": (
            (game.p2.name if seat == 1 else game.p1.name) if seat
            else game.p2.name
        ),
    }


# --- learning ---

def lesson_done_slugs(user: SocialProfile) -> set[str]:
    return set(
        PokerLessonProgress.objects.filter(social_user=user, completed_at__isnull=False)
        .values_list("lesson_slug", flat=True)
    )


def learn_stats(user: SocialProfile) -> dict:
    from . import lessons as poker_lessons
    from . import puzzles as poker_puzzles

    done = lesson_done_slugs(user)
    total = len(poker_lessons.LESSONS)
    profile = get_or_create_profile(user)
    skill = skill_level(profile.learn_xp)
    next_les = None
    for les in poker_lessons.LESSONS:
        if les["slug"] not in done:
            next_les = les
            break
    chapters = []
    for ch in poker_lessons.CHAPTERS:
        items = [l for l in poker_lessons.LESSONS if l["chapter"] == ch["slug"]]
        d = sum(1 for l in items if l["slug"] in done)
        chapters.append({
            **ch,
            "lessons": items,
            "count": len(items),
            "done": d,
            "pct": int(round(100 * d / len(items))) if items else 0,
        })
    daily = poker_puzzles.daily_puzzle()
    daily_solved = PokerPuzzleProgress.objects.filter(
        social_user=user, puzzle_id=daily["id"], solved_at__isnull=False,
    ).exists()
    return {
        "done": len(done),
        "total": total,
        "pct": int(round(100 * len(done) / total)) if total else 0,
        "slugs": done,
        "next_lesson": next_les,
        "chapters": chapters,
        "skill": skill,
        "daily": daily,
        "daily_solved": daily_solved,
    }


def submit_lesson_quiz(user: SocialProfile, slug: str, choice: str) -> dict:
    from . import lessons as poker_lessons

    lesson = poker_lessons.lesson_by_slug(slug)
    if not lesson or not lesson.get("quiz"):
        raise ValueError("В этом уроке нет теста")
    quiz = lesson["quiz"]
    if (choice or "").strip() != quiz["answer"]:
        raise ValueError("Пока неверно. Перечитайте урок и попробуйте снова.")
    row, _ = PokerLessonProgress.objects.get_or_create(
        social_user=user, lesson_slug=slug[:40],
        defaults={"quiz_ok": False},
    )
    newly = False
    if not row.quiz_ok:
        row.quiz_ok = True
        row.save(update_fields=["quiz_ok"])
        add_learn_xp(user, 10)
    if not row.completed_at:
        row.completed_at = _now()
        row.save(update_fields=["completed_at"])
        add_learn_xp(user, 15)
        newly = True
    return {"ok": True, "explain": quiz.get("explain", ""), "newly_completed": newly}


def mark_lesson_done(user: SocialProfile, slug: str) -> None:
    from . import lessons as poker_lessons

    lesson = poker_lessons.lesson_by_slug(slug)
    if not lesson:
        raise ValueError("Урок не найден")
    if lesson.get("quiz"):
        raise ValueError("Сначала пройдите тест")
    row, _ = PokerLessonProgress.objects.get_or_create(
        social_user=user, lesson_slug=slug[:40],
    )
    if not row.completed_at:
        row.completed_at = _now()
        row.save(update_fields=["completed_at"])
        add_learn_xp(user, 15)


@transaction.atomic
def record_puzzle_attempt(user: SocialProfile, puzzle_id: str, solved: bool) -> dict:
    from . import puzzles as poker_puzzles

    row, _ = PokerPuzzleProgress.objects.get_or_create(
        social_user=user, puzzle_id=puzzle_id[:40],
        defaults={"attempts": 0},
    )
    row.attempts = int(row.attempts or 0) + 1
    first = False
    profile = get_or_create_profile(user)
    xp = 0
    if solved and not row.solved_at:
        row.solved_at = _now()
        first = True
        profile.puzzle_solved = int(profile.puzzle_solved or 0) + 1
        today = date.today()
        last = profile.last_puzzle_on
        if last == today - timedelta(days=1):
            profile.puzzle_streak = int(profile.puzzle_streak or 0) + 1
        elif last != today:
            profile.puzzle_streak = 1
        profile.last_puzzle_on = today
        profile.best_puzzle_streak = max(
            int(profile.best_puzzle_streak or 0), int(profile.puzzle_streak or 0),
        )
        xp = 8
        if poker_puzzles.daily_puzzle().get("id") == puzzle_id:
            xp += 17
        profile.learn_xp = int(profile.learn_xp or 0) + xp
        profile.updated_at = _now()
        profile.save()
    row.save()
    return {
        "first_solve": first,
        "streak": int(profile.puzzle_streak or 0),
        "xp_gain": xp,
    }


def puzzle_stats(user: SocialProfile) -> dict:
    from . import puzzles as poker_puzzles

    profile = get_or_create_profile(user)
    solved_ids = set(
        PokerPuzzleProgress.objects.filter(social_user=user, solved_at__isnull=False)
        .values_list("puzzle_id", flat=True)
    )
    daily = poker_puzzles.daily_puzzle()
    return {
        "solved_ids": solved_ids,
        "solved": len(solved_ids),
        "total": len(poker_puzzles.PUZZLES),
        "streak": int(profile.puzzle_streak or 0),
        "daily": daily,
        "daily_solved": daily["id"] in solved_ids,
        "themes": poker_puzzles.THEMES,
    }


def leaderboard(limit: int = 20) -> list[PokerProfile]:
    return list(
        PokerProfile.objects.select_related("social_user")
        .order_by("-chips", "-wins")[:limit]
    )


def rating_leaderboard(limit: int = 25) -> list[PokerProfile]:
    return list(
        PokerProfile.objects.select_related("social_user")
        .filter(rated_games__gt=0)
        .order_by("-rating", "-wins")[:limit]
    )


def ratings_page(page_num: int = 1, per_page: int = 25):
    qs = (
        PokerProfile.objects.select_related("social_user")
        .filter(rated_games__gt=0)
        .order_by("-rating", "-wins")
    )
    return Paginator(qs, per_page).get_page(page_num)


def championship_standings(champ: PokerChampionship, limit: int = 30):
    return list(
        PokerChampEntry.objects.select_related("social_user")
        .filter(championship=champ)
        .order_by("-points", "-wins")[:limit]
    )


def recent_championships(limit: int = 6):
    ensure_week_championship()
    return list(PokerChampionship.objects.order_by("-starts_on")[:limit])


def recent_finished(user: SocialProfile, limit: int = 10) -> list[PokerGame]:
    return list(
        PokerGame.objects.filter(Q(p1=user) | Q(p2=user), status="done")
        .select_related("p1", "p2", "winner")
        .order_by("-id")[:limit]
    )


# --- rooms ---

def list_open_rooms(limit: int = 40) -> list[PokerRoom]:
    return list(
        PokerRoom.objects.filter(status__in=["open", "playing"], is_private=False)
        .select_related("owner", "p1", "p2", "current_game")
        .order_by("-updated_at")[:limit]
    )


def room_for(user: SocialProfile, room_id: int) -> PokerRoom | None:
    return (
        PokerRoom.objects.filter(pk=room_id)
        .select_related("owner", "p1", "p2", "current_game")
        .first()
    )


def _room_seat(room: PokerRoom, user: SocialProfile) -> int | None:
    if room.p1_id == user.id:
        return 1
    if room.p2_id == user.id:
        return 2
    return None


@transaction.atomic
def create_room(
    owner: SocialProfile,
    title: str,
    stake_key: str = "micro",
    is_private: bool = False,
    in_champ: bool = True,
) -> PokerRoom:
    profile = get_or_create_profile(owner)
    if is_bankrupt(profile):
        raise ValueError("Банкротство: комнату создать нельзя")
    _key, _label, _sb, _bb, buy = stake_by_key(stake_key)
    if profile.chips < buy:
        raise ValueError(f"Не хватает фишек для бай-ина {buy:,}".replace(",", " "))
    title = (title or "").strip()[:80] or f"Стол {owner.name}"
    now = _now()
    code = _new_join_code() if is_private else ""
    return PokerRoom.objects.create(
        title=title,
        owner=owner,
        stake_key=_key,
        is_private=bool(is_private),
        join_code=code,
        p1=owner,
        p2=None,
        status="open",
        in_champ=bool(in_champ),
        hands_played=0,
        created_at=now,
        updated_at=now,
    )


@transaction.atomic
def join_room(
    user: SocialProfile,
    room_id: int | None = None,
    join_code: str = "",
) -> PokerRoom:
    profile = get_or_create_profile(user)
    if is_bankrupt(profile):
        raise ValueError("Банкротство: войти в комнату нельзя")
    room = None
    code = (join_code or "").strip().upper()
    if code:
        room = (
            PokerRoom.objects.select_for_update()
            .filter(join_code=code)
            .exclude(status="closed")
            .order_by("-id")
            .first()
        )
        if not room:
            raise ValueError("Комната с таким кодом не найдена")
    elif room_id:
        room = PokerRoom.objects.select_for_update().filter(pk=room_id).first()
    if not room or room.status == "closed":
        raise ValueError("Комната недоступна")
    if room.is_private and code and room.join_code != code:
        raise ValueError("Неверный код")
    if room.is_private and not code and _room_seat(room, user) is None and room.owner_id != user.id:
        raise ValueError("Приватная комната — нужен код")
    if _room_seat(room, user) is not None:
        return room
    _key, _label, _sb, _bb, buy = stake_by_key(room.stake_key)
    if profile.chips < buy:
        raise ValueError("Недостаточно фишек для бай-ина этой комнаты")
    if room.p1_id is None:
        room.p1 = user
    elif room.p2_id is None:
        if room.p1_id == user.id:
            return room
        room.p2 = user
    else:
        raise ValueError("Комната уже заполнена")
    room.updated_at = _now()
    room.save()
    return room


@transaction.atomic
def leave_room(user: SocialProfile, room_id: int) -> None:
    room = PokerRoom.objects.select_for_update().filter(pk=room_id).first()
    if not room or room.status == "closed":
        raise ValueError("Комната не найдена")
    if room.status == "playing":
        raise ValueError("Нельзя выйти во время раздачи")
    seat = _room_seat(room, user)
    if seat is None and room.owner_id != user.id:
        raise ValueError("Вы не в этой комнате")
    if seat == 1:
        room.p1 = room.p2
        room.p2 = None
    elif seat == 2:
        room.p2 = None
    if room.owner_id == user.id:
        if room.p1_id:
            room.owner = room.p1
        else:
            room.status = "closed"
    if not room.p1_id and not room.p2_id:
        room.status = "closed"
    room.updated_at = _now()
    room.save()


@transaction.atomic
def close_room(user: SocialProfile, room_id: int) -> None:
    room = PokerRoom.objects.select_for_update().filter(pk=room_id).first()
    if not room:
        raise ValueError("Комната не найдена")
    if room.owner_id != user.id:
        raise ValueError("Закрыть может только хозяин")
    if room.status == "playing":
        raise ValueError("Сначала доиграйте раздачу")
    room.status = "closed"
    room.updated_at = _now()
    room.save(update_fields=["status", "updated_at"])


def _deal_into_game(game: PokerGame) -> PokerGame:
    a = get_or_create_profile(game.p1)
    b = get_or_create_profile(game.p2)
    for p in (a, b):
        if is_bankrupt(p):
            raise ValueError("Банкротство мешает начать раздачу")
        if p.chips < game.buy_in:
            raise ValueError("Недостаточно фишек для бай-ина")
    a.chips -= game.buy_in
    b.chips -= game.buy_in
    a.updated_at = b.updated_at = _now()
    a.save(update_fields=["chips", "updated_at"])
    b.save(update_fields=["chips", "updated_at"])

    dealt = engine.deal_hand(seed=f"poker-{game.id}-{_now().timestamp()}")
    game.p1_stack = game.buy_in
    game.p2_stack = game.buy_in
    game.p1_bet = 0
    game.p2_bet = 0
    game.pot = 0
    game.p1_hole = engine.join_cards(dealt["p1_hole"])
    game.p2_hole = engine.join_cards(dealt["p2_hole"])
    game.board = ""
    game.deck = engine.join_cards(dealt["deck"])
    game.street = "preflop"
    game.button = 1 if (game.room_id or 0) % 2 == 0 else 2
    if game.room_id:
        room = PokerRoom.objects.filter(pk=game.room_id).first()
        if room:
            game.button = 1 if int(room.hands_played or 0) % 2 == 0 else 2
    game.status = "active"
    game.updated_at = _now()
    _post_blinds(game)
    game.last_action = "раздача · блайнды"
    game.save()
    return game


@transaction.atomic
def start_room_hand(user: SocialProfile, room_id: int) -> PokerGame:
    room = PokerRoom.objects.select_for_update().filter(pk=room_id).first()
    if not room or room.status == "closed":
        raise ValueError("Комната недоступна")
    if room.status == "playing" and room.current_game_id:
        g = PokerGame.objects.filter(pk=room.current_game_id).first()
        if g and g.status == "active":
            return g
    if not room.p1_id or not room.p2_id:
        raise ValueError("Нужны два игрока за столом")
    if _room_seat(room, user) is None:
        raise ValueError("Вы не за этим столом")
    _key, _label, sb, bb, buy = stake_by_key(room.stake_key)
    champ = ensure_week_championship() if room.in_champ else None
    now = _now()
    game = PokerGame.objects.create(
        p1=room.p1,
        p2=room.p2,
        invited_by=user,
        status="pending",
        result="*",
        small_blind=sb,
        big_blind=bb,
        buy_in=buy,
        button=1,
        to_act=1,
        street="preflop",
        room=room,
        championship=champ,
        is_rated=True,
        created_at=now,
        updated_at=now,
    )
    game = _deal_into_game(game)
    room.current_game = game
    room.status = "playing"
    room.updated_at = _now()
    room.save(update_fields=["current_game", "status", "updated_at"])
    return game


def room_view(room: PokerRoom, viewer: SocialProfile) -> dict:
    stake = stake_by_key(room.stake_key)
    seat = _room_seat(room, viewer)
    game = None
    if room.current_game_id:
        game = PokerGame.objects.filter(pk=room.current_game_id).first()
    return {
        "seat": seat,
        "stake": stake,
        "can_start": bool(
            seat and room.p1_id and room.p2_id and room.status == "open"
            and not is_bankrupt(get_or_create_profile(viewer))
        ),
        "is_owner": room.owner_id == viewer.id,
        "active_game": game if game and game.status == "active" else None,
        "last_game": game if game and game.status == "done" else None,
    }
