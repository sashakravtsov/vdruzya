"""JSON snapshots for LIVE consumers."""
from __future__ import annotations

from apps.social.models import SocialProfile


def farm_state(user: SocialProfile) -> dict:
    from apps.social.farm import service as farm

    return {
        "ok": True,
        "type": "farm",
        "strip": farm.engagement_strip(user),
        "plots": farm.plots_view(user),
        "animals": farm.animals_view(user),
        "crops": farm.crops_catalog_for(user),
    }


def dating_state(user: SocialProfile) -> dict:
    from apps.social.dating import service as dating

    queue = dating.discovery_queue(user, limit=1)
    card = queue[0] if queue else None
    card_json = None
    if card:
        p = card["profile"]
        av = getattr(p, "avatar_url", None)
        if callable(av):
            av = av()
        card_json = {
            "id": p.id,
            "name": p.name,
            "age": card.get("age"),
            "city": card.get("city") or "",
            "headline": card.get("headline") or "",
            "about": card.get("about") or "",
            "intent": card.get("intent") or "",
            "is_friend": bool(card.get("is_friend")),
            "score": card["comp"]["score"],
            "note": card["comp"]["note"],
            "prompts": card.get("prompts") or [],
            "avatar": av or "",
            "profile_url": f"/profile/{p.id}",
        }
    return {
        "ok": True,
        "type": "dating",
        "strip": dating.engagement_strip(user),
        "card": card_json,
        "queue_n": len(dating.discovery_queue(user, limit=8)),
        "likes": [
            {
                "id": r["profile"].id,
                "name": r["profile"].name,
                "score": r["comp"]["score"],
                "note": r["comp"]["note"],
                "is_super": r["is_super"],
                "city": r.get("city") or "",
                "age": r.get("age"),
            }
            for r in dating.likes_you(user, limit=12)
        ],
        "matches": [
            {
                "id": r["match"].id,
                "peer_id": r["peer"].id,
                "peer_name": r["peer"].name,
                "opener": r.get("opener") or "",
                "score": r["comp"]["score"],
                "is_new": r["is_new"],
            }
            for r in dating.my_matches(user, limit=20)
        ],
    }


def chess_state(game, viewer: SocialProfile) -> dict:
    from apps.social.chess import engine as chess_engine
    from apps.social.chess import service as chess
    from apps.social.chess.models import ChessMove

    game, _ = chess.ensure_clock(game)
    flip = viewer.id == game.black_id
    my_side = chess.side_of(game, viewer) or ""
    is_pending = game.status == "pending"
    can_move = bool(game.result == "*" and not is_pending and my_side and my_side == game.turn)
    legal_map = {}
    if can_move:
        try:
            legal_map = chess_engine.legal_moves_map(game.fen, my_side)
        except Exception:
            legal_map = {}
    moves = list(ChessMove.objects.filter(game=game).order_by("ply")[:80])
    status_label = game.status
    if game.result != "*":
        status_label = "finished"
    elif is_pending:
        status_label = "pending"
    elif can_move:
        status_label = "your_move"
    else:
        status_label = "waiting"
    return {
        "ok": True,
        "type": "chess",
        "game_id": game.id,
        "fen": game.fen,
        "status": game.status,
        "status_label": status_label,
        "result": game.result,
        "turn": game.turn,
        "my_side": my_side,
        "can_move": can_move,
        "is_pending": is_pending,
        "flip": flip,
        "legal_map": legal_map,
        "board_rows": chess_engine.board_rows(game.fen, flip=flip),
        "board_files": chess_engine.board_files(flip=flip),
        "clock": chess.clock_snapshot(game),
        "material": chess_engine.material_view(game.fen),
        "last_move": {
            "from_sq": moves[-1].from_sq,
            "to_sq": moves[-1].to_sq,
            "san": getattr(moves[-1], "san", "") or "",
        }
        if moves
        else None,
        "check_sq": (
            chess_engine.king_square(game.fen, game.turn)
            if game.result == "*" and chess_engine.game_status(game.fen) == "check"
            else ""
        ),
        "white_name": game.white.name if game.white_id else "",
        "black_name": game.black.name if game.black_id else "",
        "draw_offer_by_id": game.draw_offer_by_id,
    }
