"""Realtime messenger — listen-only; sends go through HTTP (throttled forms)."""
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async


class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            return await self.close()
        self.cid = int(self.scope["url_route"]["kwargs"]["cid"])
        if not await self._member(user):
            return await self.close()
        self.group = f"chat_{self.cid}"
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "group"):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive_json(self, content, **kwargs):
        # Writes go through message_send (CSRF + throttle). WS is fan-out only.
        return

    async def chat_message(self, event):
        await self.send_json(event)

    @database_sync_to_async
    def _member(self, user):
        from apps.social import chat as ch
        from apps.social.services import profile_of
        return ch.is_member(profile_of(user), self.cid)
