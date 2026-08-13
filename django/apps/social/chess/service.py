"""Chess app services: ratings, games, weekly championships."""
from __future__ import annotations

from datetime import date, timedelta

from django.db import transaction
from django.db.models import Q

from apps.social.models import SocialProfile
from apps.social.services import now as _now

from . import engine
from .models import ChessChampEntry, ChessChampionship, ChessGame, ChessMove, ChessRating


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
    start, end = week_bounds(d)
    obj = ChessChampionship.objects.filter(week_key=key).first()
    if obj:
        return obj
    title = f"Чемпионат недели {start.strftime('%d.%m')}–{end.strftime('%d.%m.%Y')}"
    return ChessChampionship.objects.create(
        week_key=key,
        title=title,
        starts_on=start,
        ends_on=end,
        status="open",
        created_at=_now(),
    )


def get_or_create_rating(user: SocialProfile) -> ChessRating:
    row = ChessRating.objects.filter(pk=user.id).first()
    if row:
        return row
    return ChessRating.objects.create(
        social_user=user, rating=1200, games=0, wins=0, losses=0, draws=0, updated_at=_now(),
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


def user_stats(user: SocialProfile) -> dict:
    r = get_or_create_rating(user)
    recent = list(
        ChessGame.objects.filter(Q(white=user) | Q(black=user))
        .exclude(result="*")
        .order_by("-id")[:10]
    )
    active = list(
        ChessGame.objects.filter(Q(white=user) | Q(black=user), result="*")
        .order_by("-updated_at")[:10]
    )
    return {"rating": r, "recent": recent, "active": active}


def start_game(white: SocialProfile, black: SocialProfile, *, in_champ: bool = True) -> ChessGame:
    if white.id == black.id:
        raise ValueError("Нельзя играть с самим собой")
    champ = ensure_week_championship() if in_champ else None
    get_or_create_rating(white)
    get_or_create_rating(black)
    if champ:
        for u in (white, black):
            ChessChampEntry.objects.get_or_create(
                championship=champ, social_user=u,
                defaults={"points": 0, "wins": 0, "losses": 0, "draws": 0},
            )
    return ChessGame.objects.create(
        white=white,
        black=black,
        fen=engine.START_FEN,
        status="active",
        result="*",
        turn="w",
        championship=champ,
        moves_count=0,
        created_at=_now(),
        updated_at=_now(),
    )


def game_for(user: SocialProfile, game_id: int) -> ChessGame | None:
    g = ChessGame.objects.select_related("white", "black", "championship").filter(pk=game_id).first()
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
    side = side_of(game, user)
    if not side:
        raise ValueError("Это не ваша партия")
    if game.turn != side:
        raise ValueError("Сейчас ход соперника")
    new_fen, san = engine.make_move(game.fen, frm, to)
    status = engine.game_status(new_fen)
    game.fen = new_fen
    game.turn = "b" if side == "w" else "w"
    game.moves_count += 1
    game.updated_at = _now()
    ChessMove.objects.create(
        game=game, ply=game.moves_count, from_sq=frm.lower()[:2], to_sq=to.lower()[:2],
        san=san, fen_after=new_fen, created_at=_now(),
    )
    if status == "checkmate":
        game.status = "mate"
        game.result = "1-0" if side == "w" else "0-1"
        game.winner_id = user.id
        _finish_ratings(game)
    elif status == "stalemate":
        game.status = "draw"
        game.result = "1/2-1/2"
        _finish_ratings(game)
    elif status == "check":
        game.status = "check"
    else:
        game.status = "active"
    game.save()
    return game


@transaction.atomic
def resign(game: ChessGame, user: SocialProfile) -> ChessGame:
    if game.result != "*":
        raise ValueError("Партия уже закончена")
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
