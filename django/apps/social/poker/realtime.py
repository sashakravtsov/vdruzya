"""Poker realtime helpers: JSON snapshots + Channels group broadcast."""
from __future__ import annotations

import logging
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from apps.social.models import SocialProfile

from . import engine
from . import service as poker
from .models import PokerAction, PokerGame, PokerRoom

log = logging.getLogger(__name__)


def game_group(game_id: int) -> str:
    return f"poker.game.{int(game_id)}"


def room_group(room_id: int) -> str:
    return f"poker.room.{int(room_id)}"


def _card_json(c: dict | None) -> dict | None:
    if not c:
        return None
    return {
        "rank": c.get("rank"),
        "suit": c.get("suit"),
        "suit_name": c.get("suit_name"),
        "red": bool(c.get("red")),
        "label": c.get("label"),
        "raw": c.get("raw"),
    }


def serialize_table(game: PokerGame, viewer: SocialProfile) -> dict:
    """Personalized table snapshot for WS / JSON API."""
    view = poker.table_view(game, viewer)
    actions = list(
        PokerAction.objects.filter(game=game)
        .select_related("actor")
        .order_by("-ply")[:12]
    )
    actions.reverse()
    board_slots = []
    for slot in view.get("board_slots") or []:
        board_slots.append(_card_json(slot) if slot else None)

    multi_seats = []
    for s in view.get("multi_seats") or []:
        multi_seats.append({
            "idx": s["idx"],
            "user_id": s["user_id"],
            "name": s["name"],
            "stack": s["stack"],
            "stack_fmt": s["stack_fmt"],
            "bet": s["bet"],
            "bet_fmt": s["bet_fmt"],
            "folded": s["folded"],
            "all_in": s["all_in"],
            "dealer": s["dealer"],
            "to_act": s["to_act"],
            "me": s["me"],
            "angle": s["angle"],
            "hidden": s["hidden"],
            "cards": [_card_json(c) for c in (s.get("cards") or [])],
        })

    return {
        "ok": True,
        "type": "table",
        "game_id": game.id,
        "status": game.status,
        "mode": view.get("mode") or getattr(game, "mode", "hu"),
        "street": view.get("street"),
        "street_label": view.get("street_label"),
        "last_action": game.last_action or "",
        "hand_label": game.hand_label or "",
        "result": game.result,
        "winner_id": game.winner_id,
        "room_id": game.room_id,
        "is_rated": bool(game.is_rated),
        "championship": bool(game.championship_id),
        "pot": view.get("pot"),
        "pot_fmt": view.get("pot_fmt"),
        "can_act": bool(view.get("can_act")),
        "waiting": bool(view.get("waiting")),
        "legal": list(view.get("legal") or []),
        "to_call": view.get("to_call"),
        "to_call_fmt": view.get("to_call_fmt"),
        "min_raise_to": view.get("min_raise_to"),
        "min_raise_fmt": view.get("min_raise_fmt"),
        "half_pot_to": view.get("half_pot_to"),
        "pot_raise_to": view.get("pot_raise_to"),
        "max_raise_to": view.get("max_raise_to"),
        "hand_strength": view.get("hand_strength") or "",
        "sb_fmt": view.get("sb_fmt"),
        "bb_fmt": view.get("bb_fmt"),
        "players_n": view.get("players_n") or 2,
        "streets": view.get("streets") or [],
        "board_slots": board_slots,
        "my_cards": [_card_json(c) for c in (view.get("my_cards") or [])],
        "my_stack_fmt": view.get("my_stack_fmt"),
        "my_bet": view.get("my_bet"),
        "my_bet_fmt": view.get("my_bet_fmt"),
        "opp_name": view.get("opp_name") or "",
        "opp_stack_fmt": view.get("opp_stack_fmt"),
        "opp_bet": view.get("opp_bet"),
        "opp_bet_fmt": view.get("opp_bet_fmt"),
        "opp_cards": [_card_json(c) for c in (view.get("opp_cards") or [])],
        "i_am_dealer": bool(view.get("i_am_dealer")),
        "opp_is_dealer": bool(view.get("opp_is_dealer")),
        "multi_seats": multi_seats,
        "actions": [
            {
                "street": a.street,
                "actor": a.actor.name if a.actor_id else "?",
                "action": a.action,
                "amount": int(a.amount or 0),
                "amount_fmt": engine.format_chips(a.amount),
            }
            for a in actions
        ],
    }


def serialize_room(room: PokerRoom, viewer: SocialProfile) -> dict:
    meta = poker.room_view(room, viewer)
    return {
        "ok": True,
        "type": "room",
        "room_id": room.id,
        "title": room.title,
        "status": room.status,
        "is_private": bool(room.is_private),
        "max_seats": meta["max_seats"],
        "filled_n": meta["filled_n"],
        "can_start": bool(meta["can_start"]),
        "is_owner": bool(meta["is_owner"]),
        "seat": meta["seat"],
        "hands_played": int(room.hands_played or 0),
        "active_game_id": meta["active_game"].id if meta.get("active_game") else None,
        "seats": meta["seats"],
        "stake": meta["stake"][1] if meta.get("stake") else "",
    }


def broadcast_game(game_id: int, event: str = "state") -> None:
    layer = get_channel_layer()
    if not layer:
        return
    try:
        async_to_sync(layer.group_send)(
            game_group(game_id),
            {"type": "poker.push", "event": event, "game_id": int(game_id)},
        )
    except Exception:
        log.exception("poker broadcast_game failed id=%s", game_id)


def broadcast_room(room_id: int, event: str = "state") -> None:
    layer = get_channel_layer()
    if not layer:
        return
    try:
        async_to_sync(layer.group_send)(
            room_group(room_id),
            {"type": "poker.push", "event": event, "room_id": int(room_id)},
        )
    except Exception:
        log.exception("poker broadcast_room failed id=%s", room_id)


def notify_game(game: PokerGame, event: str = "state") -> None:
    broadcast_game(game.id, event)
    if game.room_id:
        broadcast_room(game.room_id, "game")
