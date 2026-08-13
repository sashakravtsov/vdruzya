"""Poker services: chips economy, bankruptcy, Texas Hold'em hands, learning XP."""
from __future__ import annotations

from datetime import date, timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.social.models import SocialProfile
from apps.social.services import now as _now

from . import engine
from .models import (
    PokerAction, PokerGame, PokerLessonProgress, PokerProfile, PokerPuzzleProgress,
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


def get_or_create_profile(user: SocialProfile) -> PokerProfile:
    row, created = PokerProfile.objects.get_or_create(
        social_user=user,
        defaults={
            "chips": STARTING_CHIPS,
            "created_at": _now(),
            "updated_at": _now(),
        },
    )
    if created:
        return row
    return row


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
    return {
        **hub,
        "chips": int(p.chips or 0),
        "wins": int(p.wins or 0),
        "games": int(p.games or 0),
        "skill": skill_level(p.learn_xp),
        "puzzle_streak": int(p.puzzle_streak or 0),
        "bankrupt": is_bankrupt(p),
        "can_reset": can_reset_bankruptcy(p),
        "bankrupt_days_left": (
            max(1, int((left.total_seconds() + 86399) // 86400)) if left else 0
        ),
        "reset_count": int(p.reset_count or 0),
        "starting_chips": STARTING_CHIPS,
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
    return {
        "seat": seat,
        "board": board,
        "board_labels": [engine.card_label(c) for c in board],
        "my_hole": my_hole,
        "my_labels": [engine.card_label(c) for c in my_hole],
        "opp_hole": opp_hole,
        "opp_labels": [engine.card_label(c) for c in opp_hole],
        "my_stack": my_stack,
        "opp_stack": opp_stack,
        "my_bet": my_bet,
        "opp_bet": opp_bet,
        "to_call": to_call,
        "legal": legal,
        "pot": game.pot,
        "street": game.street,
        "can_act": bool(legal),
        "min_raise_to": max(opp_bet + game.big_blind, game.big_blind),
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


def recent_finished(user: SocialProfile, limit: int = 10) -> list[PokerGame]:
    return list(
        PokerGame.objects.filter(Q(p1=user) | Q(p2=user), status="done")
        .select_related("p1", "p2", "winner")
        .order_by("-id")[:limit]
    )
