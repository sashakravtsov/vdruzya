"""WebSocket consumers for farm / dating / chess realtime (not Messenger)."""
from __future__ import annotations

from typing import Any

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth.models import AnonymousUser

from apps.social.live import broadcast
from apps.social.services import profile_of


class BaseLiveConsumer(AsyncJsonWebsocketConsumer):
    group_name = ""

    async def connect(self):
        user = self.scope.get("user")
        if user is None or isinstance(user, AnonymousUser) or not getattr(user, "is_authenticated", False):
            await self.close(code=4401)
            return
        self.user = user
        self.group_name = await self.build_group()
        if not self.group_name:
            await self.close(code=4403)
            return
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json({"type": "hello", "user_id": int(user.id), "scope": self.scope_name()})
        snapshot = await self.build_snapshot()
        if snapshot is not None:
            await self.send_json({"type": "state", "payload": snapshot})

    async def disconnect(self, close_code):
        if getattr(self, "group_name", None):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    def scope_name(self) -> str:
        return "live"

    async def build_group(self) -> str:
        raise NotImplementedError

    async def build_snapshot(self):
        return None

    async def receive_json(self, content, **kwargs):
        action = str(content.get("action") or content.get("type") or "").strip()
        if action in ("ping",):
            await self.send_json({"type": "pong"})
            return
        if action in ("refresh", "sync"):
            snapshot = await self.build_snapshot()
            await self.send_json({"type": "state", "payload": snapshot})
            return
        await self.handle_action(action, content if isinstance(content, dict) else {})

    async def handle_action(self, action: str, content: dict[str, Any]):
        await self.send_json({"type": "error", "error": "unknown_action", "action": action})


class FarmLiveConsumer(BaseLiveConsumer):
    def scope_name(self) -> str:
        return "farm"

    async def build_group(self) -> str:
        return broadcast.farm_group(int(self.user.id))

    @database_sync_to_async
    def build_snapshot(self):
        from apps.social.live.serializers import farm_state

        me = profile_of(self.user)
        return farm_state(me) if me else {"ok": False, "error": "auth"}

    async def farm_push(self, event):
        # External updates (neighbor help/steal, other tabs) — refresh snapshot.
        snapshot = await self.build_snapshot()
        await self.send_json({
            "type": "state",
            "event": event.get("event") or "state",
            "payload": snapshot,
            "extra": event.get("payload") or {},
        })

    @database_sync_to_async
    def _act(self, action: str, payload: dict[str, Any]):
        from apps.social.farm import service as farm
        from apps.social.live.serializers import farm_state

        me = profile_of(self.user)
        if not me:
            return {"ok": False, "error": "auth"}
        notify_ids: list[int] = []
        try:
            if action == "plant":
                farm.plant(me, int(payload.get("plot_id") or 0), str(payload.get("crop") or payload.get("crop_key") or ""))
            elif action == "harvest":
                farm.harvest(me, int(payload.get("plot_id") or 0))
            elif action == "water":
                farm.water_plot(me, int(payload.get("plot_id") or 0))
            elif action == "fertilize":
                farm.fertilize_plot(me, int(payload.get("plot_id") or 0))
            elif action == "boost":
                farm.boost_plot(me, int(payload.get("plot_id") or 0))
            elif action == "clear":
                farm.clear_withered(me, int(payload.get("plot_id") or 0))
            elif action == "expand":
                farm.expand_field(me)
            elif action == "shop":
                farm.buy_shop(me, str(payload.get("item") or payload.get("item_key") or ""), int(payload.get("qty") or 1))
            elif action == "buy_animal":
                farm.buy_animal(me, str(payload.get("kind") or ""))
            elif action == "feed":
                farm.feed_animal(me, int(payload.get("animal_id") or 0))
            elif action == "collect":
                farm.collect_animal(me, int(payload.get("animal_id") or 0))
            elif action == "daily":
                farm.claim_daily_bonus(me)
            elif action == "help":
                owner_id = int(payload.get("owner_id") or payload.get("neighbor_id") or 0)
                farm.help_neighbor(me, owner_id, int(payload.get("plot_id") or 0))
                notify_ids.append(owner_id)
            elif action == "steal":
                owner_id = int(payload.get("owner_id") or payload.get("neighbor_id") or 0)
                farm.steal_neighbor(me, owner_id, int(payload.get("plot_id") or 0))
                notify_ids.append(owner_id)
            else:
                return {"ok": False, "error": "unknown_action"}
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        except Exception:
            return {"ok": False, "error": "fail"}
        return {"ok": True, "state": farm_state(me), "notify_ids": notify_ids, "event": action}

    async def handle_action(self, action: str, content: dict[str, Any]):
        result = await self._act(action, content)
        notify_ids = result.pop("notify_ids", []) if isinstance(result, dict) else []
        event = result.pop("event", action) if isinstance(result, dict) else action
        await self.send_json({"type": "action_result", "action": action, "payload": result})
        if result.get("ok") and result.get("state"):
            await self.send_json({"type": "state", "payload": result["state"]})
        # Broadcast to others only (avoid sync group_send re-entrancy on this consumer).
        for uid in notify_ids or []:
            if uid and int(uid) != int(self.user.id):
                broadcast.notify_farm(int(uid), event, {"by": int(self.user.id)})


class DatingLiveConsumer(BaseLiveConsumer):
    def scope_name(self) -> str:
        return "dating"

    async def build_group(self) -> str:
        return broadcast.dating_group(int(self.user.id))

    @database_sync_to_async
    def build_snapshot(self):
        from apps.social.live.serializers import dating_state

        me = profile_of(self.user)
        return dating_state(me) if me else {"ok": False, "error": "auth"}

    async def dating_push(self, event):
        snapshot = await self.build_snapshot()
        await self.send_json({
            "type": "state",
            "event": event.get("event") or "state",
            "payload": snapshot,
            "extra": event.get("payload") or {},
        })

    async def live_push(self, event):
        await self.send_json({"type": event.get("event") or "event", "payload": event.get("payload") or {}})

    @database_sync_to_async
    def _act(self, action: str, payload: dict[str, Any]):
        from apps.social.dating import service as dating
        from apps.social.live.serializers import dating_state

        me = profile_of(self.user)
        if not me:
            return {"ok": False, "error": "auth"}
        peer_id = None
        matched = False
        match_id = None
        peer_name = ""
        try:
            if action == "swipe":
                swipe_action = str(payload.get("swipe_action") or payload.get("kind") or "like")
                if swipe_action == "superlike":
                    swipe_action = "super"
                result = dating.swipe(
                    me,
                    int(payload.get("target_id") or payload.get("to_user_id") or 0),
                    swipe_action,
                )
                peer = result.get("peer")
                match = result.get("match")
                peer_id = peer.id if peer else None
                peer_name = peer.name if peer else ""
                matched = bool(match)
                match_id = match.id if match else None
            elif action == "save_profile":
                dating.save_profile(me, {
                    "headline": str(payload.get("headline") or ""),
                    "about": str(payload.get("about") or ""),
                    "intent": str(payload.get("intent") or "dating"),
                    "age_min": int(payload.get("age_min") or 18),
                    "age_max": int(payload.get("age_max") or 99),
                    "gender_pref": str(payload.get("gender_pref") or "any"),
                    "discoverable": bool(payload.get("discoverable", True)),
                    "prompt1_key": str(payload.get("prompt1_key") or ""),
                    "prompt1_answer": str(payload.get("prompt1_answer") or ""),
                    "prompt2_key": str(payload.get("prompt2_key") or ""),
                    "prompt2_answer": str(payload.get("prompt2_answer") or ""),
                    "prompt3_key": str(payload.get("prompt3_key") or ""),
                    "prompt3_answer": str(payload.get("prompt3_answer") or ""),
                })
            else:
                return {"ok": False, "error": "unknown_action"}
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        except Exception:
            return {"ok": False, "error": "fail"}
        return {
            "ok": True,
            "matched": matched,
            "match_id": match_id,
            "peer_id": peer_id,
            "peer_name": peer_name,
            "state": dating_state(me),
        }

    async def handle_action(self, action: str, content: dict[str, Any]):
        result = await self._act(action, content)
        await self.send_json({"type": "action_result", "action": action, "payload": result})
        if result.get("ok") and result.get("state"):
            await self.send_json({"type": "state", "payload": result["state"]})
        peer_id = result.get("peer_id")
        if result.get("ok") and peer_id:
            if result.get("matched"):
                broadcast.notify_dating(
                    int(peer_id),
                    "match",
                    {"with_user_id": int(self.user.id), "match_id": result.get("match_id")},
                )
                broadcast.notify_user(
                    int(peer_id),
                    "dating_match",
                    {"with_user_id": int(self.user.id), "match_id": result.get("match_id")},
                )
            else:
                swipe_action = str(content.get("swipe_action") or "like")
                if swipe_action in ("like", "super", "superlike"):
                    broadcast.notify_dating(
                        int(peer_id),
                        "inbound",
                        {"from_user_id": int(self.user.id), "action": swipe_action},
                    )


class ChessLiveConsumer(BaseLiveConsumer):
    game_id: int = 0

    def scope_name(self) -> str:
        return "chess"

    async def build_group(self) -> str:
        try:
            self.game_id = int(self.scope["url_route"]["kwargs"]["game_id"])
        except (KeyError, TypeError, ValueError):
            return ""
        allowed = await self._can_join()
        if not allowed:
            return ""
        return broadcast.chess_group(self.game_id)

    @database_sync_to_async
    def _can_join(self) -> bool:
        from apps.social.chess import service as chess

        me = profile_of(self.user)
        if not me:
            return False
        return chess.game_for(me, self.game_id) is not None

    @database_sync_to_async
    def build_snapshot(self):
        from apps.social.chess import service as chess
        from apps.social.live.serializers import chess_state

        me = profile_of(self.user)
        if not me:
            return {"ok": False, "error": "auth"}
        game = chess.game_for(me, self.game_id)
        if not game:
            return {"ok": False, "error": "not_found"}
        return chess_state(game, me)

    async def chess_push(self, event):
        snapshot = await self.build_snapshot()
        await self.send_json({
            "type": "state",
            "event": event.get("event") or "state",
            "payload": snapshot,
            "extra": event.get("payload") or {},
        })

    @database_sync_to_async
    def _act(self, action: str, payload: dict[str, Any]):
        from apps.social.chess import service as chess
        from apps.social.live.serializers import chess_state

        me = profile_of(self.user)
        if not me:
            return {"ok": False, "error": "auth"}
        game = chess.game_for(me, self.game_id)
        if not game:
            return {"ok": False, "error": "not_found"}
        try:
            if action == "move":
                frm = str(payload.get("from_sq") or payload.get("from") or "")
                to = str(payload.get("to_sq") or payload.get("to") or "")
                if not frm and payload.get("uci"):
                    uci = str(payload.get("uci") or "")
                    frm, to = uci[:2], uci[2:4]
                game = chess.play_move(game, me, frm, to)
            elif action == "resign":
                game = chess.resign(game, me)
            elif action == "draw_offer":
                game = chess.offer_draw(game, me)
            elif action == "draw_accept":
                game = chess.accept_draw(game, me)
            elif action == "draw_decline":
                game = chess.decline_draw(game, me)
            elif action == "claim_flag":
                game = chess.claim_timeout(game, me)
            elif action == "accept_challenge":
                game = chess.accept_challenge(game, me)
            elif action == "decline_challenge":
                game = chess.decline_challenge(game, me)
            elif action == "cancel_challenge":
                game = chess.cancel_challenge(game, me)
            else:
                return {"ok": False, "error": "unknown_action"}
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        except Exception:
            return {"ok": False, "error": "fail"}
        opp_id = game.black_id if me.id == game.white_id else game.white_id
        return {"ok": True, "state": chess_state(game, me), "opp_id": opp_id, "game_id": game.id}

    async def handle_action(self, action: str, content: dict[str, Any]):
        result = await self._act(action, content)
        opp_id = result.pop("opp_id", None) if isinstance(result, dict) else None
        game_id = result.pop("game_id", self.game_id) if isinstance(result, dict) else self.game_id
        await self.send_json({"type": "action_result", "action": action, "payload": result})
        if result.get("ok") and result.get("state"):
            await self.send_json({"type": "state", "payload": result["state"]})
            # Notify peer via group (other socket), not self-echo from sync path.
            broadcast.notify_chess(int(game_id), action)
            if opp_id:
                broadcast.notify_user(int(opp_id), "chess_update", {"game_id": int(game_id), "action": action})


class UserLiveConsumer(BaseLiveConsumer):
    """Per-user soft pings for first-party apps — never chat/messenger."""

    def scope_name(self) -> str:
        return "user"

    async def build_group(self) -> str:
        return broadcast.user_group(int(self.user.id))

    async def build_snapshot(self):
        return {"ok": True, "type": "user"}

    async def live_push(self, event):
        await self.send_json({"type": event.get("event") or "event", "payload": event.get("payload") or {}})
