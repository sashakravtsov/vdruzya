"""Django Channels WebSocket consumers for live poker tables/rooms."""
from __future__ import annotations

import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.social.services import profile_of


class PokerGameConsumer(AsyncJsonWebsocketConsumer):
    game_id: int
    group_name: str

    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return
        try:
            self.game_id = int(self.scope["url_route"]["kwargs"]["game_id"])
        except (KeyError, TypeError, ValueError):
            await self.close(code=4400)
            return
        allowed = await self._can_join(user.id, self.game_id)
        if not allowed:
            await self.close(code=4403)
            return
        self.group_name = f"poker.game.{self.game_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self._send_table(user.id)

    async def disconnect(self, code):
        if getattr(self, "group_name", None):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            return
        msg_type = (content.get("type") or "").strip()
        if msg_type == "ping":
            await self.send_json({"type": "pong"})
            return
        if msg_type == "sync":
            await self._send_table(user.id)
            return
        if msg_type == "act":
            try:
                raise_to = int(content.get("raise_to") or content.get("amount") or 0)
            except (TypeError, ValueError):
                raise_to = 0
            result = await self._act(
                user.id,
                self.game_id,
                content.get("play") or "",
                raise_to,
            )
            if not result.get("ok"):
                err = result.get("error") or "fail"
                await self.send_json({"type": "error", "error": err, "detail": err})
                return
            # group broadcast refreshes everyone; also echo ok
            await self.send_json({"type": "acted", "ok": True, "game_id": self.game_id})
            return

    async def poker_push(self, event):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            return
        await self._send_table(user.id, event=event.get("event") or "state")

    async def _send_table(self, user_id: int, event: str = "state"):
        payload = await self._table_payload(user_id, self.game_id)
        if not payload:
            await self.send_json({"type": "error", "error": "not_found"})
            return
        payload["event"] = event
        await self.send_json(payload)

    @database_sync_to_async
    def _can_join(self, user_id: int, game_id: int) -> bool:
        from apps.accounts.models import User
        from apps.social.poker import service as poker

        user = User.objects.filter(pk=user_id).first()
        me = profile_of(user) if user else None
        if not me:
            return False
        return poker.game_for(me, game_id) is not None

    @database_sync_to_async
    def _table_payload(self, user_id: int, game_id: int) -> dict | None:
        from apps.accounts.models import User
        from apps.social.poker import realtime as rt
        from apps.social.poker import service as poker

        user = User.objects.filter(pk=user_id).first()
        me = profile_of(user) if user else None
        if not me:
            return None
        game = poker.game_for(me, game_id)
        if not game:
            return None
        return rt.serialize_table(game, me)

    @database_sync_to_async
    def _act(self, user_id: int, game_id: int, play: str, raise_to: int) -> dict:
        from apps.accounts.models import User
        from apps.social.poker import realtime as rt
        from apps.social.poker import service as poker

        user = User.objects.filter(pk=user_id).first()
        me = profile_of(user) if user else None
        if not me:
            return {"ok": False, "error": "auth"}
        try:
            game = poker.act(me, game_id, play, raise_to=raise_to)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        except Exception:
            return {"ok": False, "error": "Не удалось выполнить ход"}
        rt.notify_game(game, event="acted")
        return {"ok": True, "status": game.status}


class PokerRoomConsumer(AsyncJsonWebsocketConsumer):
    room_id: int
    group_name: str

    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return
        try:
            self.room_id = int(self.scope["url_route"]["kwargs"]["room_id"])
        except (KeyError, TypeError, ValueError):
            await self.close(code=4400)
            return
        ok = await self._room_exists(self.room_id)
        if not ok:
            await self.close(code=4404)
            return
        self.group_name = f"poker.room.{self.room_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self._send_room(user.id)

    async def disconnect(self, code):
        if getattr(self, "group_name", None):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            return
        msg_type = (content.get("type") or "").strip()
        if msg_type == "ping":
            await self.send_json({"type": "pong"})
            return
        if msg_type == "sync":
            await self._send_room(user.id)
            return
        if msg_type == "start_hand":
            result = await self._start(user.id, self.room_id)
            if not result.get("ok"):
                await self.send_json({"type": "error", "error": result.get("error") or "fail"})
                return
            await self.send_json({
                "type": "hand_started",
                "ok": True,
                "game_id": result["game_id"],
                "redirect": f"/apps/poker/canvas?tab=table&id={result['game_id']}",
            })
            return

    async def poker_push(self, event):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            return
        await self._send_room(user.id, event=event.get("event") or "state")

    async def _send_room(self, user_id: int, event: str = "state"):
        payload = await self._room_payload(user_id, self.room_id)
        if not payload:
            await self.send_json({"type": "error", "error": "not_found"})
            return
        payload["event"] = event
        await self.send_json(payload)

    @database_sync_to_async
    def _room_exists(self, room_id: int) -> bool:
        from apps.social.poker.models import PokerRoom
        return PokerRoom.objects.filter(pk=room_id).exclude(status="closed").exists()

    @database_sync_to_async
    def _room_payload(self, user_id: int, room_id: int) -> dict | None:
        from apps.accounts.models import User
        from apps.social.poker import realtime as rt
        from apps.social.poker import service as poker

        user = User.objects.filter(pk=user_id).first()
        me = profile_of(user) if user else None
        if not me:
            return None
        room = poker.room_for(me, room_id)
        if not room or room.status == "closed":
            return None
        return rt.serialize_room(room, me)

    @database_sync_to_async
    def _start(self, user_id: int, room_id: int) -> dict:
        from apps.accounts.models import User
        from apps.social.poker import realtime as rt
        from apps.social.poker import service as poker

        user = User.objects.filter(pk=user_id).first()
        me = profile_of(user) if user else None
        if not me:
            return {"ok": False, "error": "auth"}
        try:
            game = poker.start_room_hand(me, room_id)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        except Exception:
            return {"ok": False, "error": "Не удалось раздать"}
        rt.notify_game(game, event="deal")
        rt.broadcast_room(room_id, "playing")
        return {"ok": True, "game_id": game.id}
