from django.core.cache import cache
from django.db.models import F, OuterRef, Q, Subquery

from apps.social.models import Conversation, ConversationMember, Message, Notification
from apps.social.services import profile_of


def _unread_message_count(me) -> int:
    """Unread threads for nav — same rules as chat.inbox(unread_only=True)."""
    last = Message.objects.filter(conversation_id=OuterRef("pk")).order_by("-id")
    my_read = ConversationMember.objects.filter(
        conversation_id=OuterRef("pk"), social_user=me,
    ).values("last_read_at")[:1]
    return (
        Conversation.objects.filter(members__social_user=me, members__archived_at__isnull=True)
        .annotate(
            last_from_id=Subquery(last.values("social_user_id")[:1]),
            last_at=Subquery(last.values("created_at")[:1]),
            my_read_at=Subquery(my_read),
        )
        .exclude(last_from_id=me.id)
        .filter(last_from_id__isnull=False, last_at__isnull=False)
        .filter(Q(my_read_at__isnull=True) | Q(last_at__gt=F("my_read_at")))
        .distinct()
        .count()
    )


def classic(request):
    me = profile_of(request.user) if getattr(request.user, "is_authenticated", False) else None
    unread_n = unread_m = 0
    if me:
        key = f"nav:{me.id}"
        cached = cache.get(key)
        if cached:
            unread_n, unread_m = cached
        else:
            unread_n = Notification.objects.filter(social_user=me, seen=False).count()
            unread_m = _unread_message_count(me)
            cache.set(key, (unread_n, unread_m), 30)
    return {
        "me": me,
        "unread_notifications": unread_n,
        "unread_messages": unread_m,
        "is_home": bool(request.resolver_match and request.resolver_match.url_name == "home"),
        "nav": (request.resolver_match.url_name if request.resolver_match else "") or "",
    }
