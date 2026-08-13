"""Canvas controller for Шахматы — forms, pagination, learn curriculum."""
from __future__ import annotations

from django.contrib import messages
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
from .models import ChessMove


def render_chess_canvas(request, me, app):
    tab = (request.GET.get("tab") or request.POST.get("tab") or "play").strip()
    if tab not in ("play", "game", "stats", "ratings", "champs", "learn", "puzzles"):
        tab = "play"

    friends = pa.friends_for_app(me)
    champ = chess.ensure_week_championship()
    my_rating = chess.get_or_create_rating(me)
    strip = chess.engagement_strip(me, champ)

    game = None
    moves = []
    move_pairs = []
    board_rows = []
    legal_hint = []
    legal_map = {}
    clock = {"enabled": False}
    material = {}
    last_move = None
    check_sq = ""
    my_side = ""
    can_move = False
    is_pending = False
    waiting_refresh = False
    from_sq = (request.GET.get("from") or "").strip().lower()
    lesson = None
    puzzle = None
    puzzle_board = []
    puzzle_legal = {}
    puzzle_meta = None
    start_form = StartGameForm(friends=friends)
    move_form = MoveForm()
    puzzle_form = PuzzleAnswerForm()
    sound_event = (request.GET.get("sfx") or "").strip()

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
                    g = chess.start_game(
                        peer, me, in_champ=in_champ, time_control_sec=tc,
                        invited_by=me, require_accept=True,
                    )
                else:
                    g = chess.start_game(
                        me, peer, in_champ=in_champ, time_control_sec=tc,
                        invited_by=me, require_accept=True,
                    )
                notify.push(
                    peer.id, title="Шахматы",
                    body=f"{me.name} вызывает вас на партию",
                    type="message",
                    url=reverse("apps.canvas", args=["chess"]) + f"?tab=game&id={g.id}",
                )
                messages.success(request, f"Приглашение отправлено {peer.name}. Ждём ответа.")
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
                sfx = "move"
                if g.status == "timeout":
                    messages.info(request, "Время истекло — партия завершена.")
                    sfx = "end"
                elif g.result != "*":
                    messages.success(request, "Партия завершена.")
                    sfx = "end"
                elif g.status == "check":
                    messages.success(request, f"Ход сделан — шах!")
                    sfx = "check"
                else:
                    messages.success(
                        request,
                        f"Ход {form.cleaned_data['from_sq']}-{form.cleaned_data['to_sq']} сделан.",
                    )
                    if "×" in (ChessMove.objects.filter(game=g).order_by("-ply").values_list("san", flat=True).first() or ""):
                        sfx = "capture"
                return redirect(
                    reverse("apps.canvas", args=["chess"]) + f"?tab=game&id={g.id}&sfx={sfx}"
                )

            if action in (
                "resign", "draw_offer", "draw_accept", "draw_decline", "claim_flag",
                "accept_challenge", "decline_challenge", "cancel_challenge", "rematch",
            ):
                form = GameActionForm(request.POST)
                if not form.is_valid():
                    raise ValueError("Некорректное действие")
                g = chess.game_for(me, form.cleaned_data["game_id"])
                if not g:
                    raise ValueError("Партия не найдена")
                if action == "resign":
                    g = chess.resign(g, me)
                    messages.info(request, "Вы сдались.")
                    return redirect(reverse("apps.canvas", args=["chess"]) + f"?tab=game&id={g.id}&sfx=end")
                if action == "draw_offer":
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
                    return redirect(reverse("apps.canvas", args=["chess"]) + f"?tab=game&id={g.id}&sfx=end")
                elif action == "draw_decline":
                    g = chess.decline_draw(g, me)
                    messages.info(request, "Ничья отклонена.")
                elif action == "claim_flag":
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
                    return redirect(reverse("apps.canvas", args=["chess"]) + f"?tab=game&id={g.id}&sfx=end")
                elif action == "accept_challenge":
                    g = chess.accept_challenge(g, me)
                    opp_id = g.invited_by_id or (g.black_id if me.id == g.white_id else g.white_id)
                    notify.push(
                        opp_id, title="Шахматы",
                        body=f"{me.name} принял вызов — партия началась",
                        type="message",
                        url=reverse("apps.canvas", args=["chess"]) + f"?tab=game&id={g.id}",
                    )
                    messages.success(request, "Вызов принят. Удачи!")
                    return redirect(reverse("apps.canvas", args=["chess"]) + f"?tab=game&id={g.id}&sfx=start")
                elif action == "decline_challenge":
                    g = chess.decline_challenge(g, me)
                    if g.invited_by_id:
                        notify.push(
                            g.invited_by_id, title="Шахматы",
                            body=f"{me.name} отклонил приглашение",
                            type="message",
                            url=reverse("apps.canvas", args=["chess"]) + "?tab=play",
                        )
                    messages.info(request, "Приглашение отклонено.")
                    return redirect(reverse("apps.canvas", args=["chess"]) + "?tab=play")
                elif action == "cancel_challenge":
                    g = chess.cancel_challenge(g, me)
                    opp_id = g.black_id if me.id == g.white_id else g.white_id
                    notify.push(
                        opp_id, title="Шахматы",
                        body=f"{me.name} отозвал приглашение",
                        type="message",
                        url=reverse("apps.canvas", args=["chess"]) + "?tab=play",
                    )
                    messages.info(request, "Приглашение отозвано.")
                    return redirect(reverse("apps.canvas", args=["chess"]) + "?tab=play")
                else:  # rematch
                    ng = chess.rematch_game(g, me)
                    opp_id = ng.black_id if me.id == ng.white_id else ng.white_id
                    notify.push(
                        opp_id, title="Шахматы",
                        body=f"{me.name} предлагает реванш",
                        type="message",
                        url=reverse("apps.canvas", args=["chess"]) + f"?tab=game&id={ng.id}",
                    )
                    messages.success(request, "Реванш предложен — ждём ответа.")
                    return redirect(reverse("apps.canvas", args=["chess"]) + f"?tab=game&id={ng.id}")
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
                meta = chess.record_puzzle_attempt(me, pz["id"], ok)
                if ok:
                    extra = ""
                    if meta["first_solve"]:
                        extra = f" Серия: {meta['streak']}."
                    messages.success(request, f"Верно! {pz['explain']}{extra}")
                    sfx = "puzzle"
                else:
                    messages.error(request, "Пока не то. Подсказка: " + pz["hint"])
                    sfx = "wrong"
                return redirect(
                    reverse("apps.canvas", args=["chess"])
                    + f"?tab=puzzles&puzzle={pz['id']}&sfx={sfx}"
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
                sound_event = sound_event or "end"
            flip = me.id == game.black_id
            board_rows = chess_engine.board_rows(game.fen, flip=flip)
            moves = list(ChessMove.objects.filter(game=game).order_by("ply")[:120])
            move_pairs = chess_engine.pair_moves(moves)
            last_move = moves[-1] if moves else None
            material = chess_engine.material_view(game.fen)
            to_sq = (request.GET.get("to") or "").strip().lower()
            move_form = MoveForm(initial={
                "game_id": game.id,
                "from_sq": from_sq,
                "to_sq": to_sq,
            })
            my_side = chess.side_of(game, me) or ""
            is_pending = game.status == "pending"
            can_move = bool(
                game.result == "*" and not is_pending and my_side and my_side == game.turn
            )
            waiting_refresh = bool(game.result == "*" and not is_pending and not can_move)
            if can_move:
                try:
                    legal_map = chess_engine.legal_moves_map(game.fen, my_side)
                except Exception:
                    legal_map = {}
            if from_sq and can_move:
                legal_hint = legal_map.get(from_sq, [])
            if game.status == "check" or (
                game.result == "*" and chess_engine.game_status(game.fen) == "check"
            ):
                check_sq = chess_engine.king_square(game.fen, game.turn) or ""
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
        puzzle_meta = chess.puzzle_stats(me)
        try:
            puzzle_legal = chess_engine.legal_moves_map(puzzle["fen"], puzzle["side"])
        except Exception:
            puzzle_legal = {}

    hub = strip if tab == "play" else None

    return render(request, "social/apps/canvas_chess.html", {
        "me": me, "app": app, "friends": friends, "tab": tab,
        "champ": champ, "my_rating": my_rating, "strip": strip, "hub": hub,
        "game": game, "board_rows": board_rows, "moves": moves, "move_pairs": move_pairs,
        "legal_hint": legal_hint, "legal_map": legal_map,
        "from_sq": from_sq, "my_side": my_side, "can_move": can_move,
        "is_pending": is_pending, "waiting_refresh": waiting_refresh,
        "clock": clock, "material": material, "last_move": last_move,
        "check_sq": check_sq, "sound_event": sound_event,
        "start_form": start_form, "move_form": move_form,
        "stats": stats, "history_page": history_page,
        "ratings_page": ratings_page,
        "standings": standings, "past_champs": past_champs,
        "lesson": lesson, "chapters": chapters,
        "prev_lesson": prev_lesson, "next_lesson": next_lesson,
        "learn_meta": learn_meta,
        "puzzle": puzzle, "puzzles": chess_puzzles.PUZZLES,
        "puzzle_board": puzzle_board, "puzzle_form": puzzle_form,
        "puzzle_legal": puzzle_legal, "puzzle_meta": puzzle_meta,
        "nav": "apps", "installed": True,
    })
