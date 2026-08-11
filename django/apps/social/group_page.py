"""Group page data builders — short helpers only."""
from django.db.models import Count, Prefetch

from apps.social.forms import CommentBodyForm, CommunityPostForm, GroupEventForm
from apps.social.models import (
    Community, CommunityJoinRequest, CommunityMember, CommunityPost, CommunityPostComment,
    Event, Photo, SocialProfile,
)
from apps.social.services import accepted_friends

_ADMIN = ("admin", "moderator", "creator", "officer")


def access(me, group):
    is_member = bool(me and CommunityMember.objects.filter(community=group, social_user=me).exists())
    is_admin = bool(
        me and CommunityMember.objects.filter(community=group, social_user=me, role__in=_ADMIN).exists()
    )
    can_view = group.privacy != "closed" or is_member
    can_post = bool(
        me and (
            group.posting_policy == "everyone"
            or (is_member and group.posting_policy != "admins")
            or is_admin
        )
    )
    join_pending = bool(
        me and not is_member
        and CommunityJoinRequest.objects.filter(community=group, social_user=me, status="pending").exists()
    )
    return is_member, is_admin, can_view, can_post, join_pending


def posts_qs(group):
    return (
        CommunityPost.objects.filter(community=group)
        .select_related("social_user")
        .defer("social_user__looking_for", "social_user__interested_in", "social_user__languages")
        .prefetch_related(
            Prefetch(
                "comments",
                queryset=CommunityPostComment.objects.select_related("social_user")
                .defer("social_user__looking_for", "social_user__interested_in", "social_user__languages").order_by("id"),
            ),
            "media",
        )
        .annotate(n_comments=Count("comments", distinct=True))
    )


def page_ctx(request, group, me):
    is_member, is_admin, can_view, can_post, join_pending = access(me, group)
    ctx = {
        "group": group, "me": me, "is_member": is_member, "is_admin": is_admin,
        "can_view": can_view, "can_post": can_post, "join_pending": join_pending,
        "n_members": CommunityMember.objects.filter(community=group).count(),
        "members": [], "officers": [], "related": [], "posts": [], "wall_posts": [],
        "photos": [], "pending": [], "events": [], "invite_friends": [], "album_photos": [],
        "n_topics": 0, "open_topic": None,
        "form": CommunityPostForm(auto_id="id_w_%s", initial={"board": "wall"}),
        "board_form": CommunityPostForm(auto_id="id_b_%s", initial={"board": "discussion"}),
        "photo_form": CommunityPostForm(auto_id="id_ph_%s", initial={"board": "wall"}),
        "comment_form": CommentBodyForm(auto_id=False) if is_member else None,
        "event_form": GroupEventForm() if is_admin else None,
    }
    if not can_view:
        return ctx
    qs = posts_qs(group)
    discuss = qs.exclude(topic="wall")
    ctx.update(
        members=list(
            SocialProfile.objects.filter(memberships__community=group)
            .defer("looking_for", "interested_in", "languages").order_by("name")[:6]
        ),
        officers=list(
            SocialProfile.objects.filter(memberships__community=group, memberships__role__in=_ADMIN)
            .defer("looking_for", "interested_in", "languages").distinct()[:12]
        ),
        related=list(
            Community.objects.filter(category=group.category).exclude(pk=group.pk)
            .annotate(n_members=Count("memberships", distinct=True)).order_by("-n_members", "name")[:6]
        ),
        n_topics=discuss.count(),
        posts=list(discuss[:40] if request.GET.get("all") else discuss[:5]),
        wall_posts=list(qs.filter(topic="wall")[:20]),
        photos=list(qs.exclude(media_path__isnull=True).exclude(media_path="")[:8]),
        events=list(Event.objects.filter(community=group).order_by("starts_at")[:12]),
    )
    if is_admin:
        ctx["pending"] = list(
            CommunityJoinRequest.objects.filter(community=group, status="pending")
            .select_related("social_user")[:30]
        )
    if is_member and me:
        member_ids = CommunityMember.objects.filter(community=group).values("social_user_id")
        ctx["invite_friends"] = list(
            accepted_friends(me).exclude(id__in=member_ids).defer("looking_for", "interested_in", "languages")[:12]
        )
        ctx["album_photos"] = list(
            Photo.objects.filter(album__social_user=me).exclude(path="").order_by("-id")[:12]
        )
    tid = request.GET.get("topic")
    if tid and str(tid).isdigit():
        ctx["open_topic"] = next((p for p in ctx["posts"] if p.id == int(tid)), None) or discuss.filter(pk=tid).first()
    return ctx
