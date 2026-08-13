"""Poker services: chips, rooms, rating, weekly championship, Hold'em, learning."""
from __future__ import annotations

import secrets
import string
from datetime import date, timedelta

from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from apps.social.models import SocialProfile
from apps.social.services import now as _now

from . import engine
from . import multi as multi_eng
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


def _naive(dt):
    if dt is None:
        return None
    return dt.replace(tzinfo=None) if getattr(dt, "tzinfo", None) else dt


def is_bankrupt(profile: PokerProfile, at=None) -> bool:
    at = _naive(at or _now())
    until = _naive(profile.bankrupt_until)
    return bool(until and until > at)


def can_reset_bankruptcy(profile: PokerProfile, at=None) -> bool:
    at = _naive(at or _now())
    until = _naive(profile.bankrupt_until)
    if not until:
        return False
    return until <= at


def bankrupt_remaining(profile: PokerProfile, at=None) -> timedelta | None:
    at = _naive(at or _now())
    until = _naive(profile.bankrupt_until)
    if not until or until <= at:
        return None
    return until - at


def _mark_bankrupt(profile: PokerProfile) -> None:
    profile.chips = 0
    profile.bankrupt_until = _now() + timedelta(days=BANKRUPT_DAYS)
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
    if getattr(game, "mode", "hu") == "multi":
        seats = multi_eng.loads_list(game.seats_json)
        for i, s in enumerate(seats):
            if int(s.get("u") or 0) == user.id:
                return i  # 0-based for multi
        return None
    if game.p1_id == user.id:
        return 1
    if game.p2_id == user.id:
        return 2
    return None


def opp_of(game: PokerGame, user: SocialProfile) -> SocialProfile:
    return game.p2 if game.p1_id == user.id else game.p1


def _user_in_multi_game(game: PokerGame, user: SocialProfile) -> bool:
    if getattr(game, "mode", "hu") != "multi":
        return False
    return any(int(s.get("u") or 0) == user.id for s in multi_eng.loads_list(game.seats_json))


def game_for(user: SocialProfile, gid: int) -> PokerGame | None:
    game = (
        PokerGame.objects.filter(pk=gid)
        .select_related("p1", "p2", "invited_by", "winner", "room")
        .first()
    )
    if not game:
        return None
    if game.p1_id == user.id or game.p2_id == user.id or _user_in_multi_game(game, user):
        return game
    return None


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
        _touch_play_streak(p)
        p.updated_at = _now()
        p.save()
        if int(p.chips or 0) < MIN_PLAYABLE_CHIPS:
            _mark_bankrupt(p)
    unlock_achievements_for_users([p1, p2], multi=False, won=bool(winner_seat))
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
    if getattr(game, "mode", "hu") == "multi":
        return _act_multi(user, game, action, raise_to=raise_to)
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
        .order_by("-updated_at")[:50]
    )
    # Multi games where user is seat 3+ (not mirrored in p1/p2)
    extra = list(
        PokerGame.objects.filter(mode="multi", status="active")
        .exclude(Q(p1=user) | Q(p2=user))
        .select_related("p1", "p2", "invited_by")
        .order_by("-updated_at")[:30]
    )
    seen = {g.id for g in open_games}
    for g in extra:
        if g.id in seen:
            continue
        if _user_in_multi_game(g, user):
            open_games.append(g)
            seen.add(g.id)

    your_act, waiting, incoming, outgoing = [], [], [], []
    for g in open_games:
        if g.status == "pending":
            if g.invited_by_id == user.id:
                outgoing.append(g)
            else:
                incoming.append(g)
            continue
        seat = seat_of(g, user)
        if seat is None:
            continue
        if seat == g.to_act:
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
    goals = daily_goals(user)
    badges = achievement_badges(user)
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
        "play_streak": int(getattr(p, "play_streak", 0) or 0),
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
        "goals": goals,
        "badges": badges,
        "badges_n": sum(1 for b in badges if b["unlocked"]),
    }


def _table_view_multi(game: PokerGame, viewer: SocialProfile) -> dict:
    seats = multi_eng.loads_list(game.seats_json)
    board = engine.parse_cards(game.board)
    my_i = seat_of(game, viewer)
    show_all = game.status == "done" or game.street in ("showdown", "done")
    ids = [int(s["u"]) for s in seats]
    names = {sp.id: sp.name for sp in SocialProfile.objects.filter(pk__in=ids)}
    n = max(1, len(seats))
    # CSS angle positions around oval
    angles = {
        2: [0, 180],
        3: [0, 120, 240],
        4: [0, 90, 180, 270],
        5: [0, 72, 144, 216, 288],
        6: [0, 60, 120, 180, 240, 300],
    }.get(n, [i * (360 // n) for i in range(n)])

    my_hole = engine.parse_cards(seats[my_i]["hole"]) if my_i is not None else []
    my_stack = int(seats[my_i]["stack"]) if my_i is not None else 0
    my_bet = int(seats[my_i]["bet"]) if my_i is not None else 0
    current_bet = int(game.current_bet or 0)
    to_call = max(0, current_bet - my_bet) if my_i is not None else 0
    legal = []
    if my_i is not None and game.status == "active" and my_i == game.to_act:
        legal = engine.legal_actions(to_call, my_stack, my_bet, to_call == 0)

    seat_views = []
    for i, s in enumerate(seats):
        hole = engine.parse_cards(s.get("hole") or "")
        show_hole = show_all or (my_i is not None and i == my_i)
        seat_views.append({
            "idx": i,
            "user_id": int(s["u"]),
            "name": names.get(int(s["u"]), "?"),
            "stack": int(s.get("stack") or 0),
            "stack_fmt": engine.format_chips(s.get("stack")),
            "bet": int(s.get("bet") or 0),
            "bet_fmt": engine.format_chips(s.get("bet")),
            "folded": bool(s.get("folded")),
            "all_in": bool(s.get("all_in")),
            "dealer": i == int(game.button),
            "to_act": game.status == "active" and i == game.to_act,
            "me": my_i is not None and i == my_i,
            "angle": angles[i] if i < len(angles) else (i * 60) % 360,
            "cards": [engine.card_view(c) for c in hole] if show_hole else [],
            "hidden": not show_hole and not s.get("folded"),
        })

    min_raise_to = max(current_bet + game.big_blind, game.big_blind)
    pot = int(game.pot or 0)
    max_raise = my_bet + my_stack
    half_pot = min(max(min_raise_to, my_bet + max(to_call, pot // 2)), max_raise) if max_raise else min_raise_to
    pot_raise = min(max(min_raise_to, my_bet + max(to_call, pot)), max_raise) if max_raise else min_raise_to
    hand_strength = ""
    if my_hole and len(board) >= 3:
        hand_strength = engine.hand_name(engine.best_hand(my_hole, board))
    elif my_hole and len(my_hole) == 2:
        if my_hole[0][0] == my_hole[1][0]:
            hand_strength = "пара на руках"
        elif my_hole[0][1] == my_hole[1][1]:
            hand_strength = "suited"
        else:
            hand_strength = "offsuit"

    street = game.street or "preflop"
    streets = ["preflop", "flop", "turn", "river"]
    street_idx = streets.index(street) if street in streets else (
        4 if street in ("showdown", "done") else 0
    )
    board_slots = [engine.card_view(c) for c in board]
    while len(board_slots) < 5:
        board_slots.append(None)
    waiting = bool(
        game.status == "active" and my_i is not None and not legal and game.to_act != my_i
    )
    return {
        "mode": "multi",
        "multi_seats": seat_views,
        "seat": my_i if my_i is not None else -1,
        "board": board,
        "board_cards": [engine.card_view(c) for c in board],
        "board_slots": board_slots,
        "my_hole": my_hole,
        "my_cards": [engine.card_view(c) for c in my_hole],
        "my_stack": my_stack,
        "my_bet": my_bet,
        "my_stack_fmt": engine.format_chips(my_stack),
        "my_bet_fmt": engine.format_chips(my_bet),
        "opp_stack": 0,
        "opp_bet": 0,
        "opp_stack_fmt": "",
        "opp_bet_fmt": "",
        "opp_cards": [],
        "opp_name": "",
        "opp_is_dealer": False,
        "i_am_dealer": bool(my_i is not None and my_i == game.button),
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
        "room_id": game.room_id,
        "sb_fmt": engine.format_chips(game.small_blind),
        "bb_fmt": engine.format_chips(game.big_blind),
        "buy_in_fmt": engine.format_chips(game.buy_in),
        "players_n": n,
    }


def table_view(game: PokerGame, viewer: SocialProfile) -> dict:
    if getattr(game, "mode", "hu") == "multi":
        return _table_view_multi(game, viewer)

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
        "mode": "hu",
        "multi_seats": [],
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
        "players_n": 2,
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


# --- rooms (2–6 seats) ---

DAILY_BONUS_CHIPS = 25_000
SEAT_CHOICES = (2, 3, 4, 5, 6)


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


def _room_seats(room: PokerRoom) -> list:
    raw = multi_eng.loads_list(getattr(room, "seats_json", None) or "[]")
    max_seats = max(multi_eng.MIN_SEATS, min(multi_eng.MAX_SEATS, int(getattr(room, "max_seats", 2) or 2)))
    if len(raw) != max_seats:
        # migrate legacy p1/p2 rooms
        seats = multi_eng.empty_room_seats(max_seats)
        if room.p1_id:
            seats[0] = room.p1_id
        if room.p2_id and max_seats > 1:
            seats[1] = room.p2_id
        if raw and all(isinstance(x, int) or x is None for x in raw):
            for i, v in enumerate(raw[:max_seats]):
                seats[i] = v
        return seats
    return [int(x) if x else None for x in raw]


def _sync_room_p12(room: PokerRoom, seats: list) -> None:
    filled = [s for s in seats if s]
    room.p1_id = filled[0] if filled else None
    room.p2_id = filled[1] if len(filled) > 1 else None


def _room_seat(room: PokerRoom, user: SocialProfile) -> int | None:
    seats = _room_seats(room)
    for i, uid in enumerate(seats):
        if uid == user.id:
            return i
    return None


@transaction.atomic
def create_room(
    owner: SocialProfile,
    title: str,
    stake_key: str = "micro",
    is_private: bool = False,
    in_champ: bool = True,
    max_seats: int = 2,
) -> PokerRoom:
    profile = get_or_create_profile(owner)
    if is_bankrupt(profile):
        raise ValueError("Банкротство: комнату создать нельзя")
    _key, _label, _sb, _bb, buy = stake_by_key(stake_key)
    if profile.chips < buy:
        raise ValueError(f"Не хватает фишек для бай-ина {buy:,}".replace(",", " "))
    max_seats = int(max_seats or 2)
    if max_seats not in SEAT_CHOICES:
        raise ValueError("Допустимо 2–6 мест за столом")
    title = (title or "").strip()[:80] or f"Стол {owner.name}"
    now = _now()
    code = _new_join_code() if is_private else ""
    seats = multi_eng.empty_room_seats(max_seats)
    seats[0] = owner.id
    room = PokerRoom.objects.create(
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
        max_seats=max_seats,
        seats_json=multi_eng.dumps(seats),
        button_seat=0,
        created_at=now,
        updated_at=now,
    )
    return room


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
    if room.status == "playing":
        raise ValueError("Дождитесь конца раздачи")
    if room.is_private and not code and _room_seat(room, user) is None and room.owner_id != user.id:
        raise ValueError("Приватная комната — нужен код")
    seats = _room_seats(room)
    if user.id in seats:
        return room
    _key, _label, _sb, _bb, buy = stake_by_key(room.stake_key)
    if profile.chips < buy:
        raise ValueError("Недостаточно фишек для бай-ина этой комнаты")
    try:
        seats = multi_eng.room_add_user(seats, user.id)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
    room.seats_json = multi_eng.dumps(seats)
    _sync_room_p12(room, seats)
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
    seats = _room_seats(room)
    if user.id not in seats and room.owner_id != user.id:
        raise ValueError("Вы не в этой комнате")
    seats = multi_eng.room_remove_user(seats, user.id)
    filled = [s for s in seats if s]
    if room.owner_id == user.id:
        if filled:
            room.owner_id = filled[0]
        else:
            room.status = "closed"
    if not filled:
        room.status = "closed"
    room.seats_json = multi_eng.dumps(seats)
    _sync_room_p12(room, seats)
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


def _mirror_hu_columns(game: PokerGame, seats: list[dict]) -> None:
    m = multi_eng.seats_to_hu_mirror(seats)
    for k, v in m.items():
        setattr(game, k, v)


def _finish_multi(game: PokerGame, seats: list[dict], reason: str, board: list[str] | None = None) -> PokerGame:
    board = board if board is not None else engine.parse_cards(game.board)
    names = {}
    ids = [int(s["u"]) for s in seats]
    for sp in SocialProfile.objects.filter(pk__in=ids):
        names[sp.id] = sp.name

    # If fold-win before board complete
    only = multi_eng.only_one_left(seats)
    if only is not None and game.street not in ("showdown", "done"):
        winner = seats[only]
        winner["stack"] += int(game.pot or 0)
        game.pot = 0
        primary_uid = int(winner["u"])
        notes = [reason]
    else:
        seats, notes, primary_uid = multi_eng.distribute_side_pots(seats, board)
        game.pot = 0

    game.seats_json = multi_eng.dumps(seats)
    _mirror_hu_columns(game, seats)
    game.hand_label = multi_eng.hand_label_for(seats, board, names) or reason
    game.status = "done"
    game.street = "done"
    game.to_act = -1
    game.last_action = reason if not notes else f"{reason} · {'; '.join(notes)}"
    game.result = "multi"
    game.winner_id = primary_uid
    game.updated_at = _now()
    game.save()

    # Return stacks to profiles + stats / rating / champ
    profiles = {}
    for uid in ids:
        sp = SocialProfile.objects.filter(pk=uid).first()
        if sp:
            profiles[uid] = get_or_create_profile(sp)
    for s in seats:
        uid = int(s["u"])
        p = profiles[uid]
        p.chips += int(s.get("stack") or 0)
        p.games += 1
        if primary_uid and uid == primary_uid:
            p.wins += 1
            p.biggest_pot = max(int(p.biggest_pot or 0), int(s.get("invested") or 0))
        elif primary_uid:
            p.losses += 1
        else:
            p.ties += 1
        _touch_play_streak(p)
        p.updated_at = _now()
        p.save()
        if int(p.chips or 0) < MIN_PLAYABLE_CHIPS:
            _mark_bankrupt(p)

    if game.is_rated and primary_uid:
        _apply_multi_rating(profiles, primary_uid)
    if game.championship_id:
        _apply_multi_champ(game, profiles, primary_uid)

    unlock_achievements_for_users(list(profiles.values()), multi=len(seats) > 2, won=bool(primary_uid))
    _release_room_after_hand(game)
    return game


def _apply_multi_rating(profiles: dict, winner_id: int) -> None:
    winner = profiles[winner_id]
    others = [p for uid, p in profiles.items() if uid != winner_id]
    if not others:
        return
    avg = int(round(sum(int(p.rating or 1200) for p in others) / len(others)))
    nw, nl = elo_update(int(winner.rating or 1200), avg, draw=False, k=24)
    delta = nw - int(winner.rating or 1200)
    winner.rating = nw
    winner.rated_games = int(winner.rated_games or 0) + 1
    winner.save(update_fields=["rating", "rated_games", "updated_at"])
    # distribute loss among others
    each = max(1, abs(nl - avg) // max(1, len(others))) if delta else 0
    for p in others:
        p.rating = max(100, int(p.rating or 1200) - each)
        p.rated_games = int(p.rated_games or 0) + 1
        p.updated_at = _now()
        p.save(update_fields=["rating", "rated_games", "updated_at"])


def _apply_multi_champ(game: PokerGame, profiles: dict, winner_id: int | None) -> None:
    champ = game.championship
    for uid, p in profiles.items():
        e, _ = PokerChampEntry.objects.get_or_create(
            championship=champ, social_user_id=uid,
            defaults={"points": 0, "wins": 0, "losses": 0, "ties": 0},
        )
        if winner_id and uid == winner_id:
            e.points += 3
            e.wins += 1
        elif winner_id:
            e.losses += 1
        else:
            e.points += 1
            e.ties += 1
        e.save()


def _advance_multi_street(game: PokerGame, seats: list[dict]) -> PokerGame:
    seats = multi_eng.reset_street_bets(seats)
    game.current_bet = 0
    if game.street == "river":
        board = engine.parse_cards(game.board)
        game.street = "showdown"
        game.seats_json = multi_eng.dumps(seats)
        return _finish_multi(game, seats, "шоудаун", board)

    deck = engine.parse_cards(game.deck)
    board = engine.parse_cards(game.board)
    deck, board, street = engine.deal_board(deck, board, game.street)
    game.deck = engine.join_cards(deck)
    game.board = engine.join_cards(board)
    game.street = street

    # all-in runout
    if not multi_eng.can_act_indices(seats) and len(multi_eng.active_indices(seats)) >= 2:
        while game.street not in ("showdown", "done") and game.status == "active":
            if game.street == "river":
                game.seats_json = multi_eng.dumps(seats)
                return _finish_multi(game, seats, "шоудаун · олл-ин", engine.parse_cards(game.board))
            deck = engine.parse_cards(game.deck)
            board = engine.parse_cards(game.board)
            deck, board, street = engine.deal_board(deck, board, game.street)
            game.deck = engine.join_cards(deck)
            game.board = engine.join_cards(board)
            game.street = street
        if game.street == "river":
            game.seats_json = multi_eng.dumps(seats)
            return _finish_multi(game, seats, "шоудаун · олл-ин", engine.parse_cards(game.board))

    # first to act postflop = left of button
    n = len(seats)
    start = multi_eng.next_idx(int(game.button), n)
    actor = start
    chosen = None
    for _ in range(n):
        s = seats[actor]
        if not s.get("folded") and not s.get("all_in"):
            chosen = actor
            break
        actor = multi_eng.next_idx(actor, n)
    game.to_act = chosen if chosen is not None else -1
    game.seats_json = multi_eng.dumps(seats)
    _mirror_hu_columns(game, seats)
    game.updated_at = _now()
    game.save()
    return game


def _act_multi(user: SocialProfile, game: PokerGame, action: str, raise_to: int = 0) -> PokerGame:
    seats = multi_eng.loads_list(game.seats_json)
    actor = seat_of(game, user)
    if actor is None or actor != game.to_act:
        raise ValueError("Сейчас не ваш ход")
    seats, pot, current_bet, label, paid = multi_eng.apply_action(
        seats, actor, action, raise_to, int(game.current_bet or 0), int(game.big_blind), int(game.pot or 0),
    )
    game.pot = pot
    game.current_bet = current_bet
    game.last_action = f"{user.name}: {label}"
    _log(game, user, action, paid)

    only = multi_eng.only_one_left(seats)
    if only is not None:
        game.seats_json = multi_eng.dumps(seats)
        return _finish_multi(game, seats, f"{user.name} — банк без шоудауна")

    if multi_eng.betting_closed(seats, current_bet):
        return _advance_multi_street(game, seats)

    nxt = multi_eng.next_to_act(seats, actor)
    game.to_act = nxt if nxt is not None else -1
    game.seats_json = multi_eng.dumps(seats)
    _mirror_hu_columns(game, seats)
    game.updated_at = _now()
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
    seats_room = _room_seats(room)
    filled = [uid for uid in seats_room if uid]
    if len(filled) < 2:
        raise ValueError("Нужны минимум 2 игрока за столом")
    if _room_seat(room, user) is None:
        raise ValueError("Вы не за этим столом")

    _key, _label, sb, bb, buy = stake_by_key(room.stake_key)
    profiles = []
    for uid in filled:
        sp = SocialProfile.objects.filter(pk=uid).first()
        if not sp:
            raise ValueError("Игрок не найден")
        p = get_or_create_profile(sp)
        if is_bankrupt(p):
            raise ValueError(f"{sp.name}: банкротство")
        if p.chips < buy:
            raise ValueError(f"{sp.name}: не хватает фишек на бай-ин")
        profiles.append((sp, p))

    for sp, p in profiles:
        p.chips -= buy
        p.updated_at = _now()
        p.save(update_fields=["chips", "updated_at"])

    deck = engine.new_deck(seed=f"poker-room-{room.id}-{_now().timestamp()}")
    button = int(getattr(room, "button_seat", 0) or 0) % len(filled)
    hand_seats = multi_eng.new_hand_seats(filled, buy, deck)
    hand_seats, to_act, pot, current_bet = multi_eng.post_blinds(hand_seats, button, sb, bb)

    champ = ensure_week_championship() if room.in_champ else None
    now = _now()
    p1 = profiles[0][0]
    p2 = profiles[1][0]
    game = PokerGame.objects.create(
        p1=p1,
        p2=p2,
        invited_by=user,
        status="active",
        result="*",
        small_blind=sb,
        big_blind=bb,
        buy_in=buy,
        button=button,
        to_act=to_act,
        street="preflop",
        pot=pot,
        current_bet=current_bet,
        board="",
        deck=engine.join_cards(deck),
        seats_json=multi_eng.dumps(hand_seats),
        mode="multi",
        room=room,
        championship=champ,
        is_rated=True,
        last_action="раздача · блайнды",
        created_at=now,
        updated_at=now,
    )
    _mirror_hu_columns(game, hand_seats)
    game.save()

    room.current_game = game
    room.status = "playing"
    room.button_seat = (button + 1) % len(filled)
    room.updated_at = _now()
    room.save(update_fields=["current_game", "status", "button_seat", "updated_at"])
    return game


def room_view(room: PokerRoom, viewer: SocialProfile) -> dict:
    stake = stake_by_key(room.stake_key)
    seats = _room_seats(room)
    seat = _room_seat(room, viewer)
    filled_n = multi_eng.room_seat_count(seats)
    game = None
    if room.current_game_id:
        game = PokerGame.objects.filter(pk=room.current_game_id).first()
    # hydrate names
    ids = [u for u in seats if u]
    names = {sp.id: sp.name for sp in SocialProfile.objects.filter(pk__in=ids)}
    seat_rows = []
    for i, uid in enumerate(seats):
        seat_rows.append({
            "idx": i,
            "user_id": uid,
            "name": names.get(uid, "") if uid else "",
            "empty": uid is None,
            "me": uid == viewer.id,
        })
    return {
        "seat": seat,
        "seats": seat_rows,
        "filled_n": filled_n,
        "max_seats": int(getattr(room, "max_seats", 2) or 2),
        "stake": stake,
        "can_start": bool(
            seat is not None and filled_n >= 2 and room.status == "open"
            and not is_bankrupt(get_or_create_profile(viewer))
        ),
        "is_owner": room.owner_id == viewer.id,
        "active_game": game if game and game.status == "active" else None,
        "last_game": game if game and game.status == "done" else None,
    }


# --- engagement ---

def _touch_play_streak(profile: PokerProfile) -> None:
    today = date.today()
    last = getattr(profile, "last_play_on", None)
    if last == today:
        return
    if last == today - timedelta(days=1):
        profile.play_streak = int(profile.play_streak or 0) + 1
    else:
        profile.play_streak = 1
    profile.last_play_on = today


def _ach_set(profile: PokerProfile) -> set[str]:
    raw = (getattr(profile, "achievements", None) or "").strip()
    if not raw:
        return set()
    return {x for x in raw.split(",") if x}


def _ach_save(profile: PokerProfile, keys: set[str]) -> None:
    profile.achievements = ",".join(sorted(keys))[:500]
    profile.updated_at = _now()
    profile.save(update_fields=["achievements", "updated_at"])


ACHIEVEMENTS = (
    ("first_win", "Первая победа", "Выиграйте раздачу"),
    ("hands_10", "10 раздач", "Сыграйте 10 раздач"),
    ("hands_50", "Ветеран", "Сыграйте 50 раздач"),
    ("multi_win", "Мультитейбл", "Победа за столом 3+ игроков"),
    ("rating_1400", "Элита 1400", "Рейтинг 1400+"),
    ("learn_half", "Ученик", "Пройдите половину уроков"),
    ("learn_all", "Магистр", "Пройдите все уроки"),
    ("puzzle_10", "Тактик", "Решите 10 задач"),
    ("streak_3", "Серия 3", "Играйте 3 дня подряд"),
    ("host", "Хозяин стола", "Создайте комнату"),
)


def unlock_achievements_for_users(profiles: list[PokerProfile], multi: bool = False, won: bool = False) -> None:
    from . import lessons as poker_lessons

    total_lessons = len(poker_lessons.LESSONS)
    for p in profiles:
        keys = _ach_set(p)
        before = set(keys)
        if int(p.wins or 0) >= 1:
            keys.add("first_win")
        if int(p.games or 0) >= 10:
            keys.add("hands_10")
        if int(p.games or 0) >= 50:
            keys.add("hands_50")
        if multi and won and int(p.wins or 0) >= 1:
            keys.add("multi_win")
        if int(p.rating or 1200) >= 1400:
            keys.add("rating_1400")
        if int(p.puzzle_solved or 0) >= 10:
            keys.add("puzzle_10")
        if int(getattr(p, "play_streak", 0) or 0) >= 3:
            keys.add("streak_3")
        done = PokerLessonProgress.objects.filter(
            social_user_id=p.social_user_id, completed_at__isnull=False,
        ).count()
        if total_lessons and done * 2 >= total_lessons:
            keys.add("learn_half")
        if total_lessons and done >= total_lessons:
            keys.add("learn_all")
        if keys != before:
            _ach_save(p, keys)


def claim_daily_bonus(user: SocialProfile) -> dict:
    p = get_or_create_profile(user)
    if is_bankrupt(p):
        raise ValueError("Банкротство: бонус недоступен")
    today = date.today()
    if getattr(p, "daily_bonus_on", None) == today:
        raise ValueError("Сегодняшний бонус уже получен")
    last_bonus = getattr(p, "daily_bonus_on", None)
    if last_bonus == today - timedelta(days=1):
        streak = int(getattr(p, "play_streak", 0) or 0) + 1
    else:
        streak = 1
    amount = DAILY_BONUS_CHIPS + min(50_000, (streak - 1) * 5_000)
    p.chips += amount
    p.daily_bonus_on = today
    p.play_streak = streak
    if getattr(p, "last_play_on", None) != today:
        p.last_play_on = today
    p.updated_at = _now()
    p.save()
    return {"amount": amount, "chips": int(p.chips), "streak": streak}


def daily_goals(user: SocialProfile) -> dict:
    from . import lessons as poker_lessons
    from . import puzzles as poker_puzzles

    p = get_or_create_profile(user)
    today = date.today()
    lesson_today = PokerLessonProgress.objects.filter(
        social_user=user, completed_at__date=today,
    ).exists()
    puzzle_today = getattr(p, "last_puzzle_on", None) == today
    played_today = getattr(p, "last_play_on", None) == today
    bonus_claimed = getattr(p, "daily_bonus_on", None) == today
    items = [
        {"key": "bonus", "title": "Ежедневный бонус", "done": bonus_claimed},
        {"key": "lesson", "title": "Урок дня", "done": lesson_today},
        {"key": "puzzle", "title": "Задача дня", "done": puzzle_today},
        {"key": "play", "title": "Сыграть раздачу", "done": played_today},
    ]
    done_n = sum(1 for i in items if i["done"])
    return {
        "items": items,
        "done": done_n,
        "total": len(items),
        "pct": int(round(100 * done_n / len(items))),
        "bonus_ready": not bonus_claimed and not is_bankrupt(p),
        "bonus_amount": DAILY_BONUS_CHIPS,
        "daily_puzzle": poker_puzzles.daily_puzzle(),
        "next_lesson": next(
            (l for l in poker_lessons.LESSONS
             if l["slug"] not in lesson_done_slugs(user)),
            None,
        ),
    }


def achievement_badges(user: SocialProfile) -> list[dict]:
    p = get_or_create_profile(user)
    have = _ach_set(p)
    return [
        {"key": k, "title": t, "hint": h, "unlocked": k in have}
        for k, t, h in ACHIEVEMENTS
    ]


def mark_host_achievement(user: SocialProfile) -> None:
    p = get_or_create_profile(user)
    keys = _ach_set(p)
    if "host" not in keys:
        keys.add("host")
        _ach_save(p, keys)

