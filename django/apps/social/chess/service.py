"""Chess app services: ratings, games, weekly championships."""
from __future__ import annotations

from datetime import date, timedelta

from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q

from apps.social.models import SocialProfile
from apps.social.services import now as _now

from . import engine
from .models import (
    ChessChampEntry, ChessChampionship, ChessGame, ChessLessonProgress, ChessMove,
    ChessPuzzleProgress, ChessRating,
)


def week_key(d: date | None = None) -> str:
    d = d or date.today()
    iso = d.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def week_bounds(d: date | None = None) -> tuple[date, date]:
    d = d or date.today()
    start = d - timedelta(days=d.weekday())  # Monday
    end = start + timedelta(days=6)
    return start, end


def ensure_week_championship(d: date | None = None) -> ChessChampionship:
    """Create current week championship if missing (lazy weekly launcher)."""
    d = d or date.today()
    key = week_key(d)
    cache_key = f"chess:champ:{key}"
    cached_id = cache.get(cache_key)
    if cached_id:
        obj = ChessChampionship.objects.filter(pk=cached_id).first()
        if obj:
            return obj
    start, end = week_bounds(d)
    obj = ChessChampionship.objects.filter(week_key=key).first()
    if not obj:
        title = f"Чемпионат недели {start.strftime('%d.%m')}–{end.strftime('%d.%m.%Y')}"
        obj = ChessChampionship.objects.create(
            week_key=key,
            title=title,
            starts_on=start,
            ends_on=end,
            status="open",
            created_at=_now(),
        )
    cache.set(cache_key, obj.id, 3600)
    return obj


def get_or_create_rating(user: SocialProfile) -> ChessRating:
    row = ChessRating.objects.filter(pk=user.id).first()
    if row:
        return row
    return ChessRating.objects.create(
        social_user=user, rating=1200, games=0, wins=0, losses=0, draws=0,
        puzzle_solved=0, puzzle_streak=0, best_puzzle_streak=0, updated_at=_now(),
    )


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


def leaderboard(limit: int = 20):
    return list(
        ChessRating.objects.select_related("social_user")
        .filter(games__gt=0)
        .order_by("-rating", "-wins")[:limit]
    )


TIME_CONTROL_CHOICES = (
    (0, "Без лимита"),
    (30 * 60, "30 минут на партию"),
    (60 * 60, "1 час на партию"),
    (24 * 3600, "24 часа на партию"),
    (3 * 24 * 3600, "3 дня на партию"),
)


def clocks_enabled(game: ChessGame) -> bool:
    return int(getattr(game, "time_control_sec", 0) or 0) > 0


def remaining_ms(game: ChessGame, side: str, at=None) -> int:
    """Remaining clock for side (applies live tick for the side to move)."""
    at = at or _now()
    base = int(game.white_clock_ms if side == "w" else game.black_clock_ms) or 0
    if not clocks_enabled(game) or game.result != "*":
        return max(0, base)
    if game.turn != side or not game.clock_running_since:
        return max(0, base)
    elapsed = int((at - game.clock_running_since).total_seconds() * 1000)
    return max(0, base - max(0, elapsed))


def clock_snapshot(game: ChessGame, at=None) -> dict:
    at = at or _now()
    pending = game.status == "pending"
    if not clocks_enabled(game):
        return {
            "enabled": False, "white_ms": 0, "black_ms": 0, "turn": game.turn,
            "active": False, "pending": pending,
        }
    return {
        "enabled": True,
        "white_ms": remaining_ms(game, "w", at),
        "black_ms": remaining_ms(game, "b", at),
        "turn": game.turn,
        "active": game.result == "*" and not pending,
        "pending": pending,
        "label": _time_control_label(game.time_control_sec),
        "increment_sec": int(game.increment_sec or 0),
    }


def _time_control_label(sec: int) -> str:
    for value, label in TIME_CONTROL_CHOICES:
        if value == sec:
            return label
    if sec <= 0:
        return "Без лимита"
    if sec % 86400 == 0:
        days = sec // 86400
        return f"{days} дн. на партию"
    if sec % 3600 == 0:
        return f"{sec // 3600} ч. на партию"
    if sec % 60 == 0:
        return f"{sec // 60} мин. на партию"
    return f"{sec} с на партию"


@transaction.atomic
def flag_loss(game: ChessGame, loser_side: str) -> ChessGame:
    if game.result != "*":
        return game
    game.status = "timeout"
    if loser_side == "w":
        game.result = "0-1"
        game.winner_id = game.black_id
        game.white_clock_ms = 0
    else:
        game.result = "1-0"
        game.winner_id = game.white_id
        game.black_clock_ms = 0
    game.clock_running_since = None
    game.updated_at = _now()
    game.save()
    _finish_ratings(game)
    return game


@transaction.atomic
def ensure_clock(game: ChessGame) -> tuple[ChessGame, bool]:
    """If the side to move has flagged, finish the game. Returns (game, flagged)."""
    if game.result != "*" or game.status == "pending" or not clocks_enabled(game):
        return game, False
    rem = remaining_ms(game, game.turn)
    if rem > 0:
        return game, False
    return flag_loss(game, game.turn), True


@transaction.atomic
def claim_timeout(game: ChessGame, user: SocialProfile) -> ChessGame:
    if not side_of(game, user):
        raise ValueError("Это не ваша партия")
    if game.result != "*":
        raise ValueError("Партия уже закончена")
    if not clocks_enabled(game):
        raise ValueError("В этой партии нет часов")
    if remaining_ms(game, game.turn) > 0:
        raise ValueError("Время ещё не истекло")
    return flag_loss(game, game.turn)


def start_game(
    white: SocialProfile,
    black: SocialProfile,
    *,
    in_champ: bool = True,
    time_control_sec: int = 0,
    increment_sec: int = 0,
    invited_by: SocialProfile | None = None,
    require_accept: bool = True,
) -> ChessGame:
    if white.id == black.id:
        raise ValueError("Нельзя играть с самим собой")
    allowed = {v for v, _ in TIME_CONTROL_CHOICES}
    time_control_sec = int(time_control_sec or 0)
    if time_control_sec not in allowed:
        raise ValueError("Выберите контроль времени из списка")
    increment_sec = max(0, min(int(increment_sec or 0), 3600))
    champ = ensure_week_championship() if in_champ else None
    get_or_create_rating(white)
    get_or_create_rating(black)
    if champ:
        for u in (white, black):
            ChessChampEntry.objects.get_or_create(
                championship=champ, social_user=u,
                defaults={"points": 0, "wins": 0, "losses": 0, "draws": 0},
            )
    now = _now()
    bank = time_control_sec * 1000
    pending = bool(require_accept)
    return ChessGame.objects.create(
        white=white,
        black=black,
        fen=engine.START_FEN,
        status="pending" if pending else "active",
        result="*",
        turn="w",
        championship=champ,
        invited_by=invited_by,
        moves_count=0,
        time_control_sec=time_control_sec,
        increment_sec=increment_sec,
        white_clock_ms=bank,
        black_clock_ms=bank,
        clock_running_since=(None if pending or time_control_sec <= 0 else now),
        created_at=now,
        updated_at=now,
    )


@transaction.atomic
def accept_challenge(game: ChessGame, user: SocialProfile) -> ChessGame:
    if game.status != "pending" or game.result != "*":
        raise ValueError("Это приглашение уже неактуально")
    if user.id not in (game.white_id, game.black_id):
        raise ValueError("Это не ваша партия")
    if game.invited_by_id and user.id == game.invited_by_id:
        raise ValueError("Дождитесь ответа соперника")
    game.status = "active"
    game.updated_at = _now()
    if clocks_enabled(game):
        game.clock_running_since = game.updated_at
    game.save()
    return game


@transaction.atomic
def decline_challenge(game: ChessGame, user: SocialProfile) -> ChessGame:
    if game.status != "pending" or game.result != "*":
        raise ValueError("Это приглашение уже неактуально")
    if user.id not in (game.white_id, game.black_id):
        raise ValueError("Это не ваша партия")
    if game.invited_by_id and user.id == game.invited_by_id:
        raise ValueError("Отменить приглашение можно кнопкой «отозвать»")
    game.status = "declined"
    game.result = "0-0"
    game.clock_running_since = None
    game.updated_at = _now()
    game.save()
    return game


@transaction.atomic
def cancel_challenge(game: ChessGame, user: SocialProfile) -> ChessGame:
    if game.status != "pending" or game.result != "*":
        raise ValueError("Это приглашение уже неактуально")
    if not game.invited_by_id or user.id != game.invited_by_id:
        raise ValueError("Отменить может только автор приглашения")
    game.status = "cancelled"
    game.result = "0-0"
    game.clock_running_since = None
    game.updated_at = _now()
    game.save()
    return game


def rematch_game(game: ChessGame, user: SocialProfile) -> ChessGame:
    """Start a new challenge vs the same opponent (colors swapped)."""
    if game.result == "*":
        raise ValueError("Сначала завершите текущую партию")
    if user.id not in (game.white_id, game.black_id):
        raise ValueError("Это не ваша партия")
    # swap colors for variety
    return start_game(
        game.black, game.white,
        in_champ=bool(game.championship_id),
        time_control_sec=int(game.time_control_sec or 0),
        increment_sec=int(game.increment_sec or 0),
        invited_by=user,
        require_accept=True,
    )


def game_for(user: SocialProfile, game_id: int) -> ChessGame | None:
    g = (
        ChessGame.objects.select_related("white", "black", "championship", "invited_by")
        .filter(pk=game_id)
        .first()
    )
    if not g:
        return None
    if user.id not in (g.white_id, g.black_id):
        return None
    return g


def side_of(game: ChessGame, user: SocialProfile) -> str | None:
    if user.id == game.white_id:
        return "w"
    if user.id == game.black_id:
        return "b"
    return None


@transaction.atomic
def play_move(game: ChessGame, user: SocialProfile, frm: str, to: str) -> ChessGame:
    if game.result != "*":
        raise ValueError("Партия уже закончена")
    if game.status == "pending":
        raise ValueError("Дождитесь принятия приглашения")
    side = side_of(game, user)
    if not side:
        raise ValueError("Это не ваша партия")
    if game.turn != side:
        raise ValueError("Сейчас ход соперника")
    now = _now()
    if clocks_enabled(game):
        rem = remaining_ms(game, side, now)
        if rem <= 0:
            return flag_loss(game, side)
        mover_bank = rem + int(game.increment_sec or 0) * 1000
    else:
        mover_bank = None
    new_fen, san = engine.make_move(game.fen, frm, to)
    status = engine.game_status(new_fen)
    game.fen = new_fen
    game.turn = "b" if side == "w" else "w"
    game.moves_count += 1
    game.draw_offer_by_id = None
    game.updated_at = now
    if mover_bank is not None:
        if side == "w":
            game.white_clock_ms = mover_bank
        else:
            game.black_clock_ms = mover_bank
    ChessMove.objects.create(
        game=game, ply=game.moves_count, from_sq=frm.lower()[:2], to_sq=to.lower()[:2],
        san=san, fen_after=new_fen, created_at=now,
    )
    if status == "checkmate":
        game.status = "mate"
        game.result = "1-0" if side == "w" else "0-1"
        game.winner_id = user.id
        game.clock_running_since = None
        _finish_ratings(game)
    elif status == "stalemate":
        game.status = "draw"
        game.result = "1/2-1/2"
        game.clock_running_since = None
        _finish_ratings(game)
    elif status == "check":
        game.status = "check"
        if clocks_enabled(game):
            game.clock_running_since = now
    else:
        game.status = "active"
        if clocks_enabled(game):
            game.clock_running_since = now
    game.save()
    return game


@transaction.atomic
def resign(game: ChessGame, user: SocialProfile) -> ChessGame:
    if game.result != "*":
        raise ValueError("Партия уже закончена")
    if game.status == "pending":
        raise ValueError("Сначала примите или отклоните приглашение")
    side = side_of(game, user)
    if not side:
        raise ValueError("Это не ваша партия")
    game.status = "resign"
    if side == "w":
        game.result = "0-1"
        game.winner_id = game.black_id
    else:
        game.result = "1-0"
        game.winner_id = game.white_id
    game.clock_running_since = None
    game.updated_at = _now()
    game.save()
    _finish_ratings(game)
    return game


def _finish_ratings(game: ChessGame):
    white = get_or_create_rating(game.white)
    black = get_or_create_rating(game.black)
    draw = game.result == "1/2-1/2"
    if draw:
        nw, nb = elo_update(white.rating, black.rating, draw=True)
        white.draws += 1
        black.draws += 1
    elif game.result == "1-0":
        nw, nb = elo_update(white.rating, black.rating, draw=False)
        white.wins += 1
        black.losses += 1
    else:
        nb, nw = elo_update(black.rating, white.rating, draw=False)
        black.wins += 1
        white.losses += 1
    white.rating, black.rating = nw, nb
    white.games += 1
    black.games += 1
    white.updated_at = black.updated_at = _now()
    white.save()
    black.save()
    if game.championship_id:
        _champ_points(game)


def _champ_points(game: ChessGame):
    champ = game.championship
    if not champ or champ.status != "open":
        return
    we, _ = ChessChampEntry.objects.get_or_create(
        championship=champ, social_user=game.white,
        defaults={"points": 0, "wins": 0, "losses": 0, "draws": 0},
    )
    be, _ = ChessChampEntry.objects.get_or_create(
        championship=champ, social_user=game.black,
        defaults={"points": 0, "wins": 0, "losses": 0, "draws": 0},
    )
    if game.result == "1/2-1/2":
        we.points += 1
        be.points += 1
        we.draws += 1
        be.draws += 1
    elif game.result == "1-0":
        we.points += 3
        we.wins += 1
        be.losses += 1
    elif game.result == "0-1":
        be.points += 3
        be.wins += 1
        we.losses += 1
    we.save()
    be.save()


def championship_standings(champ: ChessChampionship, limit: int = 30):
    return list(
        ChessChampEntry.objects.select_related("social_user")
        .filter(championship=champ)
        .order_by("-points", "-wins", "losses")[:limit]
    )


def recent_championships(limit: int = 6):
    ensure_week_championship()
    return list(ChessChampionship.objects.order_by("-starts_on")[:limit])


@transaction.atomic
def offer_draw(game: ChessGame, user: SocialProfile) -> ChessGame:
    if game.result != "*":
        raise ValueError("Партия уже закончена")
    if not side_of(game, user):
        raise ValueError("Это не ваша партия")
    if game.draw_offer_by_id == user.id:
        raise ValueError("Вы уже предложили ничью")
    if game.draw_offer_by_id and game.draw_offer_by_id != user.id:
        # treat as accept if opponent already offered
        return accept_draw(game, user)
    game.draw_offer_by_id = user.id
    game.updated_at = _now()
    game.save(update_fields=["draw_offer_by_id", "updated_at"])
    return game


@transaction.atomic
def accept_draw(game: ChessGame, user: SocialProfile) -> ChessGame:
    if game.result != "*":
        raise ValueError("Партия уже закончена")
    if not side_of(game, user):
        raise ValueError("Это не ваша партия")
    if not game.draw_offer_by_id or game.draw_offer_by_id == user.id:
        raise ValueError("Нет предложения ничьей от соперника")
    game.status = "draw"
    game.result = "1/2-1/2"
    game.draw_offer_by_id = None
    game.clock_running_since = None
    game.updated_at = _now()
    game.save()
    _finish_ratings(game)
    return game


@transaction.atomic
def decline_draw(game: ChessGame, user: SocialProfile) -> ChessGame:
    if game.result != "*":
        raise ValueError("Партия уже закончена")
    if not side_of(game, user):
        raise ValueError("Это не ваша партия")
    if not game.draw_offer_by_id or game.draw_offer_by_id == user.id:
        raise ValueError("Нет предложения ничьей")
    game.draw_offer_by_id = None
    game.updated_at = _now()
    game.save(update_fields=["draw_offer_by_id", "updated_at"])
    return game


def finished_games_page(user: SocialProfile, page_num: int = 1, per_page: int = 15):
    qs = (
        ChessGame.objects.filter(Q(white=user) | Q(black=user))
        .exclude(result__in=["*", "0-0"])
        .select_related("white", "black")
        .order_by("-id")
    )
    return Paginator(qs, per_page).get_page(page_num)


def ratings_page(page_num: int = 1, per_page: int = 25):
    qs = (
        ChessRating.objects.select_related("social_user")
        .filter(games__gt=0)
        .order_by("-rating", "-wins")
    )
    return Paginator(qs, per_page).get_page(page_num)


def mark_lesson_done(user: SocialProfile, slug: str) -> ChessLessonProgress:
    row, _ = ChessLessonProgress.objects.get_or_create(
        social_user=user, lesson_slug=slug[:40],
        defaults={"completed_at": _now()},
    )
    if not row.completed_at:
        row.completed_at = _now()
        row.save(update_fields=["completed_at"])
    return row


def lesson_done_slugs(user: SocialProfile) -> set[str]:
    return set(
        ChessLessonProgress.objects.filter(social_user=user)
        .values_list("lesson_slug", flat=True)
    )


def learn_stats(user: SocialProfile) -> dict:
    from .lessons import CATALOG
    done = lesson_done_slugs(user)
    total = len(CATALOG.ordered_slugs)
    return {
        "done": len(done),
        "total": total,
        "pct": int(round(100 * len(done) / total)) if total else 0,
        "slugs": done,
    }


def user_stats(user: SocialProfile) -> dict:
    r = get_or_create_rating(user)
    recent = list(
        ChessGame.objects.filter(Q(white=user) | Q(black=user))
        .exclude(result__in=["*", "0-0"])
        .select_related("white", "black")
        .order_by("-id")[:10]
    )
    active = list(
        ChessGame.objects.filter(Q(white=user) | Q(black=user), result="*")
        .exclude(status="pending")
        .select_related("white", "black")
        .order_by("-updated_at")[:10]
    )
    by_result = (
        ChessGame.objects.filter(Q(white=user) | Q(black=user))
        .exclude(result__in=["*", "0-0"])
        .values("result")
        .annotate(n=Count("id"))
    )
    return {"rating": r, "recent": recent, "active": active, "by_result": list(by_result)}


def play_hub(user: SocialProfile) -> dict:
    """Inbox-style lists for the Play tab."""
    open_games = list(
        ChessGame.objects.filter(Q(white=user) | Q(black=user), result="*")
        .select_related("white", "black", "invited_by")
        .order_by("-updated_at")[:40]
    )
    your_move, waiting, incoming, outgoing = [], [], [], []
    for g in open_games:
        if g.status == "pending":
            if g.invited_by_id == user.id:
                outgoing.append(g)
            else:
                incoming.append(g)
            continue
        side = side_of(g, user)
        if side and side == g.turn:
            your_move.append(g)
        else:
            waiting.append(g)
    return {
        "your_move": your_move,
        "waiting": waiting,
        "incoming": incoming,
        "outgoing": outgoing,
        "your_move_n": len(your_move),
        "incoming_n": len(incoming),
        "waiting_n": len(waiting),
        "outgoing_n": len(outgoing),
    }


def engagement_strip(user: SocialProfile, champ: ChessChampionship | None = None) -> dict:
    hub = play_hub(user)
    r = get_or_create_rating(user)
    week_rank = None
    week_points = None
    if champ:
        entry = (
            ChessChampEntry.objects.filter(championship=champ, social_user=user).first()
        )
        if entry:
            week_points = entry.points
            better = ChessChampEntry.objects.filter(
                championship=champ, points__gt=entry.points,
            ).count()
            week_rank = better + 1
    return {
        **hub,
        "rating": r.rating,
        "puzzle_streak": int(getattr(r, "puzzle_streak", 0) or 0),
        "puzzle_solved": int(getattr(r, "puzzle_solved", 0) or 0),
        "week_rank": week_rank,
        "week_points": week_points,
    }


@transaction.atomic
def record_puzzle_attempt(user: SocialProfile, puzzle_id: str, solved: bool) -> dict:
    from datetime import date, timedelta

    row, _ = ChessPuzzleProgress.objects.get_or_create(
        social_user=user, puzzle_id=puzzle_id[:40],
        defaults={"attempts": 0, "solved_at": None},
    )
    row.attempts = int(row.attempts or 0) + 1
    first_solve = False
    if solved and not row.solved_at:
        row.solved_at = _now()
        first_solve = True
    row.save()

    rating = get_or_create_rating(user)
    today = date.today()
    if first_solve:
        rating.puzzle_solved = int(rating.puzzle_solved or 0) + 1
        last = rating.last_puzzle_on
        if last == today:
            pass  # already counted streak today
        elif last == today - timedelta(days=1):
            rating.puzzle_streak = int(rating.puzzle_streak or 0) + 1
        else:
            rating.puzzle_streak = 1
        rating.last_puzzle_on = today
        rating.best_puzzle_streak = max(
            int(rating.best_puzzle_streak or 0), int(rating.puzzle_streak or 0),
        )
        rating.updated_at = _now()
        rating.save()
    solved_ids = set(
        ChessPuzzleProgress.objects.filter(social_user=user, solved_at__isnull=False)
        .values_list("puzzle_id", flat=True)
    )
    return {
        "first_solve": first_solve,
        "attempts": row.attempts,
        "streak": int(rating.puzzle_streak or 0),
        "solved_ids": solved_ids,
        "solved_total": int(rating.puzzle_solved or 0),
    }


def puzzle_stats(user: SocialProfile) -> dict:
    from . import puzzles as chess_puzzles

    rating = get_or_create_rating(user)
    solved_ids = set(
        ChessPuzzleProgress.objects.filter(social_user=user, solved_at__isnull=False)
        .values_list("puzzle_id", flat=True)
    )
    total = len(chess_puzzles.PUZZLES)
    return {
        "solved_ids": solved_ids,
        "solved": len(solved_ids),
        "total": total,
        "streak": int(getattr(rating, "puzzle_streak", 0) or 0),
        "best_streak": int(getattr(rating, "best_puzzle_streak", 0) or 0),
        "pct": int(round(100 * len(solved_ids) / total)) if total else 0,
    }
