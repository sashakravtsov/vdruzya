"""Canvas controller for Шахматы — forms, pagination, learn curriculum."""
from __future__ import annotations

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse

from apps.social import notify
from apps.social import platform_apps as pa
from apps.social.models import SocialProfile
from apps.social.services import friend_ids

from . import engine as chess_engine
from . import lessons as chess_lessons
from . import puzzles as chess_puzzles
from . import service as chess
from .forms import GameActionForm, MoveForm, PuzzleAnswerForm, StartGameForm
from .models import ChessGame, ChessMove


def render_chess_canvas(request, me, app):
    tab = (request.GET.get("tab") or request.POST.get("tab") or "play").strip()
    if tab not in ("play", "game", "stats", "ratings", "champs", "learn", "puzzles"):
        tab = "play"

    friends = pa.friends_for_app(me)
    champ = chess.ensure_week_championship()
    my_rating = chess.get_or_create_rating(me)

    game = None
    moves = []
    board_rows = []
    legal_hint = []
    legal_map = {}
    clock = {"enabled": False}
    my_side = ""
    can_move = False
    from_sq = (request.GET.get("from") or "").strip().lower()
    lesson = None
    puzzle = None
    puzzle_board = []
    puzzle_legal = {}
    start_form = StartGameForm(friends=friends)
    move_form = MoveForm()
    puzzle_form = PuzzleAnswerForm()

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        try:
            if action == "start":
                form = StartGameForm(request.POST, friends=friends)
                if not form.is_valid():
                    start_form = form
                    raise ValueError("Проверьте выбор соперника и контроль времени")
                fid = form.cleaned_data["friend_id"]
                if fid not in friend_ids(me):
                    raise ValueError("Выберите друга из списка")
                peer = SocialProfile.objects.filter(pk=fid).first()
                if not peer:
                    raise ValueError("Соперник не найден")
                color = form.cleaned_data["color"]
                in_champ = bool(form.cleaned_data.get("in_champ"))
                tc = int(form.cleaned_data["time_control"])
                if color == "black":
                    g = chess.start_game(peer, me, in_champ=in_champ, time_control_sec=tc)
                else:
                    g = chess.start_game(me, peer, in_champ=in_champ, time_control_sec=tc)
                notify.push(
                    peer.id, title="Шахматы",
                    body=f"{me.name} приглашает сыграть партию",
                    type="message",
                    url=reverse("apps.canvas", args=["chess"]) + f"?tab=game&id={g.id}",
                )
                messages.success(request, f"Партия с {peer.name} началась.")
                return redirect(reverse("apps.canvas", args=["chess"]) + f"?tab=game&id={g.id}")

            if action == "move":
                form = MoveForm(request.POST)
                if not form.is_valid():
                    move_form = form
                    raise ValueError(next(iter(form.errors.values()))[0])
                g = chess.game_for(me, form.cleaned_data["game_id"])
                if not g:
                    raise ValueError("Партия не найдена")
                g = chess.play_move(g, me, form.cleaned_data["from_sq"], form.cleaned_data["to_sq"])
                opp_id = g.black_id if me.id == g.white_id else g.white_id
                notify.push(
                    opp_id, title="Шахматы",
                    body=f"{me.name}: {form.cleaned_data['from_sq']}-{form.cleaned_data['to_sq']}",
                    type="message",
                    url=reverse("apps.canvas", args=["chess"]) + f"?tab=game&id={g.id}",
                )
                if g.status == "timeout":
                    messages.info(request, "Время истекло — партия завершена.")
                else:
                    messages.success(
                        request,
                        "Партия завершена." if g.result != "*" else f"Ход {form.cleaned_data['from_sq']}-{form.cleaned_data['to_sq']} сделан.",
                    )
                return redirect(reverse("apps.canvas", args=["chess"]) + f"?tab=game&id={g.id}")

            if action in ("resign", "draw_offer", "draw_accept", "draw_decline", "claim_flag"):
                form = GameActionForm(request.POST)
                if not form.is_valid():
                    raise ValueError("Некорректное действие")
                g = chess.game_for(me, form.cleaned_data["game_id"])
                if not g:
                    raise ValueError("Партия не найдена")
                if action == "resign":
                    g = chess.resign(g, me)
                    messages.info(request, "Вы сдались.")
                elif action == "draw_offer":
                    g = chess.offer_draw(g, me)
                    opp_id = g.black_id if me.id == g.white_id else g.white_id
                    notify.push(
                        opp_id, title="Шахматы",
                        body=f"{me.name} предлагает ничью",
                        type="message",
                        url=reverse("apps.canvas", args=["chess"]) + f"?tab=game&id={g.id}",
                    )
                    messages.info(request, "Предложение ничьей отправлено.")
                elif action == "draw_accept":
                    g = chess.accept_draw(g, me)
                    messages.success(request, "Ничья принята.")
                elif action == "draw_decline":
                    g = chess.decline_draw(g, me)
                    messages.info(request, "Ничья отклонена.")
                else:
                    g = chess.claim_timeout(g, me)
                    if g.winner_id == me.id:
                        messages.success(request, "Соперник просрочил время — победа.")
                    else:
                        messages.info(request, "Время истекло — партия завершена.")
                    opp_id = g.black_id if me.id == g.white_id else g.white_id
                    notify.push(
                        opp_id, title="Шахматы",
                        body="Партия завершена: истекло время на часах",
                        type="message",
                        url=reverse("apps.canvas", args=["chess"]) + f"?tab=game&id={g.id}",
                    )
                return redirect(reverse("apps.canvas", args=["chess"]) + f"?tab=game&id={g.id}")

            if action == "lesson_done":
                slug = (request.POST.get("lesson") or "")[:40]
                if not chess_lessons.lesson_by_slug(slug):
                    raise ValueError("Урок не найден")
                chess.mark_lesson_done(me, slug)
                messages.success(request, "Урок отмечен как пройденный.")
                return redirect(reverse("apps.canvas", args=["chess"]) + f"?tab=learn&lesson={slug}")

            if action == "puzzle":
                form = PuzzleAnswerForm(request.POST)
                if not form.is_valid():
                    puzzle_form = form
                    raise ValueError("Укажите клетки хода правильно")
                pz = chess_puzzles.puzzle_by_id(form.cleaned_data["puzzle_id"])
                if not pz:
                    raise ValueError("Задача не найдена")
                ok = chess_puzzles.check_answer(pz, form.cleaned_data["from_sq"], form.cleaned_data["to_sq"])
                if ok:
                    messages.success(request, f"Верно! {pz['explain']}")
                else:
                    messages.error(request, "Пока не то. Подсказка: " + pz["hint"])
                return redirect(
                    reverse("apps.canvas", args=["chess"]) + f"?tab=puzzles&puzzle={pz['id']}"
                )
        except ValueError as exc:
            messages.error(request, str(exc))
        except Exception:
            messages.error(request, "Не удалось выполнить действие. Проверьте данные.")

    # GET assembly
    if tab == "game":
        try:
            gid = int(request.GET.get("id") or 0)
        except (TypeError, ValueError):
            gid = 0
        game = chess.game_for(me, gid) if gid else None
        if game:
            game, flagged = chess.ensure_clock(game)
            if flagged:
                messages.info(request, "Время на часах истекло — партия завершена.")
            flip = me.id == game.black_id
            board_rows = chess_engine.board_rows(game.fen, flip=flip)
            moves = list(ChessMove.objects.filter(game=game).order_by("ply")[:120])
            to_sq = (request.GET.get("to") or "").strip().lower()
            move_form = MoveForm(initial={
                "game_id": game.id,
                "from_sq": from_sq,
                "to_sq": to_sq,
            })
            my_side = chess.side_of(game, me) or ""
            can_move = bool(game.result == "*" and my_side and my_side == game.turn)
            if can_move:
                try:
                    legal_map = chess_engine.legal_moves_map(game.fen, my_side)
                except Exception:
                    legal_map = {}
            if from_sq and can_move:
                legal_hint = legal_map.get(from_sq, [])
            clock = chess.clock_snapshot(game)
        else:
            messages.error(request, "Партия не найдена или недоступна.")
            tab = "play"

    stats = chess.user_stats(me) if tab == "stats" else None
    history_page = None
    if tab == "stats":
        try:
            p = int(request.GET.get("p") or 1)
        except (TypeError, ValueError):
            p = 1
        history_page = chess.finished_games_page(me, p)

    ratings_page = None
    if tab == "ratings":
        try:
            p = int(request.GET.get("p") or 1)
        except (TypeError, ValueError):
            p = 1
        ratings_page = chess.ratings_page(p)

    standings = chess.championship_standings(champ) if tab == "champs" else None
    past_champs = chess.recent_championships(8) if tab == "champs" else None

    learn_meta = chess.learn_stats(me) if tab in ("learn", "puzzles") else None
    chapters = []
    prev_lesson = next_lesson = None
    if tab == "learn":
        chapters = chess_lessons.CATALOG.chapters_with_lessons()
        lesson = chess_lessons.lesson_by_slug((request.GET.get("lesson") or "").strip())
        if lesson:
            prev_lesson, next_lesson = chess_lessons.CATALOG.neighbors(lesson["slug"])

    if tab == "puzzles":
        pid = (request.GET.get("puzzle") or chess_puzzles.PUZZLES[0]["id"]).strip()
        puzzle = chess_puzzles.puzzle_by_id(pid) or chess_puzzles.PUZZLES[0]
        puzzle_board = chess_engine.board_rows(puzzle["fen"], flip=(puzzle["side"] == "b"))
        puzzle_form = PuzzleAnswerForm(initial={"puzzle_id": puzzle["id"]})
        try:
            puzzle_legal = chess_engine.legal_moves_map(puzzle["fen"], puzzle["side"])
        except Exception:
            puzzle_legal = {}

    active_games = list(
        ChessGame.objects.filter(Q(white=me) | Q(black=me), result="*")
        .select_related("white", "black").order_by("-updated_at")[:12]
    ) if tab == "play" else []

    return render(request, "social/apps/canvas_chess.html", {
        "me": me, "app": app, "friends": friends, "tab": tab,
        "champ": champ, "my_rating": my_rating,
        "game": game, "board_rows": board_rows, "moves": moves,
        "legal_hint": legal_hint, "legal_map": legal_map,
        "from_sq": from_sq, "my_side": my_side, "can_move": can_move,
        "clock": clock,
        "start_form": start_form, "move_form": move_form,
        "stats": stats, "history_page": history_page,
        "ratings_page": ratings_page,
        "standings": standings, "past_champs": past_champs,
        "lesson": lesson, "chapters": chapters,
        "prev_lesson": prev_lesson, "next_lesson": next_lesson,
        "learn_meta": learn_meta,
        "puzzle": puzzle, "puzzles": chess_puzzles.PUZZLES,
        "puzzle_board": puzzle_board, "puzzle_form": puzzle_form,
        "puzzle_legal": puzzle_legal,
        "active_games": active_games,
        "nav": "apps", "installed": True,
    })
