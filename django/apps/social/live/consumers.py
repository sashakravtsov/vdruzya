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

    @database_sync_to_async
    def _profile(self):
        return profile_of(self.user)


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
                broadcast.notify_farm(owner_id, "neighbor_help", {"by": int(me.id)})
            elif action == "steal":
                owner_id = int(payload.get("owner_id") or payload.get("neighbor_id") or 0)
                farm.steal_neighbor(me, owner_id, int(payload.get("plot_id") or 0))
                broadcast.notify_farm(owner_id, "neighbor_steal", {"by": int(me.id)})
            else:
                return {"ok": False, "error": "unknown_action"}
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        except Exception:
            return {"ok": False, "error": "fail"}
        state = farm_state(me)
        broadcast.notify_farm(me.id, "state")
        return {"ok": True, "state": state}

    async def handle_action(self, action: str, content: dict[str, Any]):
        result = await self._act(action, content)
        await self.send_json({"type": "action_result", "action": action, "payload": result})
        if result.get("ok") and result.get("state"):
            await self.send_json({"type": "state", "payload": result["state"]})


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
        try:
            if action == "swipe":
                swipe_action = str(payload.get("swipe_action") or payload.get("kind") or "like")
                if swipe_action == "superlike":
                    swipe_action = "super"
                result = dating.swipe(me, int(payload.get("target_id") or payload.get("to_user_id") or 0), swipe_action)
                peer = result.get("peer")
                matched = result.get("match")
                if peer:
                    broadcast.notify_dating(peer.id, "inbound", {"from_user_id": int(me.id), "action": swipe_action})
                    if matched:
                        broadcast.notify_dating(peer.id, "match", {"with_user_id": int(me.id), "match_id": matched.id})
                        broadcast.notify_user(peer.id, "dating_match", {"with_user_id": int(me.id), "match_id": matched.id})
                out = {
                    "ok": True,
                    "matched": bool(matched),
                    "match_id": matched.id if matched else None,
                    "peer_name": peer.name if peer else "",
                    "state": dating_state(me),
                }
                broadcast.notify_dating(me.id, "state")
                return out
            if action == "save_profile":
                dating.save_profile(me, {
                    "headline": str(payload.get("headline") or ""),
                    "about": str(payload.get("about") or ""),
                    "intent": str(payload.get("intent") or "dating"),
                    "age_min": int(payload.get("age_min") or 18),
                    "age_max": int(payload.get("age_max") or 99),
                    "gender_pref": str(payload.get("gender_pref") or "any"),
                    "prompts_json": str(payload.get("prompts_json") or "[]"),
                })
            else:
                return {"ok": False, "error": "unknown_action"}
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        except Exception:
            return {"ok": False, "error": "fail"}
        state = dating_state(me)
        broadcast.notify_dating(me.id, "state")
        return {"ok": True, "state": state}

    async def handle_action(self, action: str, content: dict[str, Any]):
        result = await self._act(action, content)
        await self.send_json({"type": "action_result", "action": action, "payload": result})
        if result.get("ok") and result.get("state"):
            await self.send_json({"type": "state", "payload": result["state"]})


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
        state = chess_state(game, me)
        broadcast.notify_chess(game.id, "state")
        return {"ok": True, "state": state}

    async def handle_action(self, action: str, content: dict[str, Any]):
        result = await self._act(action, content)
        await self.send_json({"type": "action_result", "action": action, "payload": result})
        if result.get("ok") and result.get("state"):
            await self.send_json({"type": "state", "payload": result["state"]})


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
