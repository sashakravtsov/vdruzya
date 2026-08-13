"""Channel-layer broadcast helpers for first-party app LIVE (not Messenger)."""
from __future__ import annotations

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

log = logging.getLogger(__name__)


def group_send(group: str, handler: str, **payload) -> None:
    layer = get_channel_layer()
    if not layer:
        return
    try:
        async_to_sync(layer.group_send)(group, {"type": handler, **payload})
    except Exception:
        log.exception("live group_send failed group=%s type=%s", group, handler)


def user_group(user_id: int) -> str:
    return f"live.user.{int(user_id)}"


def farm_group(user_id: int) -> str:
    return f"live.farm.{int(user_id)}"


def dating_group(user_id: int) -> str:
    return f"live.dating.{int(user_id)}"


def chess_group(game_id: int) -> str:
    return f"live.chess.{int(game_id)}"


def notify_user(user_id: int, event: str, payload: dict | None = None) -> None:
    group_send(user_group(user_id), "live.push", event=event, payload=payload or {})


def notify_farm(user_id: int, event: str = "state", payload: dict | None = None) -> None:
    group_send(farm_group(user_id), "farm.push", event=event, payload=payload or {})


def notify_dating(user_id: int, event: str = "state", payload: dict | None = None) -> None:
    group_send(dating_group(user_id), "dating.push", event=event, payload=payload or {})


def notify_chess(game_id: int, event: str = "state", payload: dict | None = None) -> None:
    group_send(chess_group(game_id), "chess.push", event=event, payload=payload or {})
