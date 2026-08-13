"""Combined WebSocket URL routes for first-party app LIVE."""
from django.urls import re_path

from apps.social.live import consumers as live
from apps.social.poker import consumers as poker

websocket_urlpatterns = [
    # Poker
    re_path(r"^ws/poker/game/(?P<game_id>\d+)/$", poker.PokerGameConsumer.as_asgi()),
    re_path(r"^ws/poker/room/(?P<room_id>\d+)/$", poker.PokerRoomConsumer.as_asgi()),
    # Farm / Dating / Chess / soft user pings
    re_path(r"^ws/farm/$", live.FarmLiveConsumer.as_asgi()),
    re_path(r"^ws/dating/$", live.DatingLiveConsumer.as_asgi()),
    re_path(r"^ws/chess/game/(?P<game_id>\d+)/$", live.ChessLiveConsumer.as_asgi()),
    re_path(r"^ws/live/user/$", live.UserLiveConsumer.as_asgi()),
]
