from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async


class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            return await self.close()
        self.cid = self.scope["url_route"]["kwargs"]["cid"]
        if not await self._member(user):
            return await self.close()
        self.group = f"chat_{self.cid}"
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "group"):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive_json(self, content, **kwargs):
        body = (content.get("body") or "").strip()
        if not body:
            return
        payload = await self._store(body)
        if payload:
            await self.channel_layer.group_send(self.group, {"type": "chat.message", **payload})

    async def chat_message(self, event):
        await self.send_json(event)

    @database_sync_to_async
    def _member(self, user):
        from apps.social.models import ConversationMember
        from apps.social.services import profile_of
        me = profile_of(user)
        return bool(me and ConversationMember.objects.filter(conversation_id=self.cid, social_user=me).exists())

    @database_sync_to_async
    def _store(self, body):
        from apps.social.models import ConversationMember, Message
        from apps.social.services import now, profile_of
        me = profile_of(self.scope["user"])
        if not me or not ConversationMember.objects.filter(conversation_id=self.cid, social_user=me).exists():
            return None
        m = Message.objects.create(
            conversation_id=self.cid, social_user=me, body=body, message_type="text", created_at=now()
        )
        return {"body": m.body, "name": me.name, "id": m.id}
