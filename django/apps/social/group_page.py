"""Group page data builders — tabbed FB 2006 layout."""
from django.db.models import Count, F, Prefetch

from apps.social.forms import CommentForm, CommunityPostForm, EventForm
from apps.social.models import (
    GROUP_POST_DEFER, PROFILE_DEFER, Community, CommunityJoinRequest, CommunityMember,
    CommunityPost, CommunityPostComment, Event, SocialProfile, profile_related,
)
from apps.social.services import accepted_friends

ADMIN_ROLES = ("admin", "moderator", "creator", "officer")
TABS = ("wall", "discussion", "photos", "docs", "members", "events")


def access(me, group):
    is_member = bool(me and CommunityMember.objects.filter(community=group, social_user=me).exists())
    is_admin = bool(
        me and CommunityMember.objects.filter(community=group, social_user=me, role__in=ADMIN_ROLES).exists()
    )
    can_view = group.privacy != "closed" or is_member
    # FB 2006 groups: members (or admins-only) — no open wall for non-members
    can_post = bool(
        me and is_member and (group.posting_policy != "admins" or is_admin)
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
        .defer(*GROUP_POST_DEFER, *profile_related("social_user__"))
        .prefetch_related(
            Prefetch(
                "comments",
                queryset=CommunityPostComment.objects.select_related("social_user")
                .defer(*profile_related("social_user__")).order_by("id"),
            ),
            "media",
        )
        .annotate(n_comments=Count("comments", distinct=True))
    )


def _tab(request):
    tab = (request.GET.get("tab") or "").lower()
    if request.GET.get("topic"):
        return "discussion"
    return tab if tab in TABS else "wall"


def page_ctx(request, group, me):
    is_member, is_admin, can_view, can_post, join_pending = access(me, group)
    tab = _tab(request)
    ctx = {
        "group": group, "me": me, "tab": tab,
        "is_member": is_member, "is_admin": is_admin,
        "can_view": can_view, "can_post": can_post, "join_pending": join_pending,
        "n_members": CommunityMember.objects.filter(community=group).count(),
        "members": [], "officers": [], "related": [], "posts": [], "wall_posts": [],
        "photos": [], "pending": [], "events": [], "invite_friends": [],
        "n_topics": 0, "open_topic": None,
        "form": None, "board_form": None, "photo_form": None, "doc_form": None,
        "docs": [],
        "comment_form": CommentForm(auto_id=False) if is_member else None,
        "event_form": EventForm() if is_admin else None,
    }
    if not can_view:
        return ctx

    qs = posts_qs(group)
    ctx["officers"] = list(
        SocialProfile.objects.filter(memberships__community=group, memberships__role__in=ADMIN_ROLES)
        .defer(*PROFILE_DEFER).distinct()[:12]
    )
    ctx["related"] = list(
        Community.objects.filter(category=group.category).exclude(pk=group.pk)
        .annotate(n_members=Count("memberships", distinct=True)).order_by("-n_members", "name")[:6]
    )
    if is_admin:
        ctx["pending"] = list(
            CommunityJoinRequest.objects.filter(community=group, status="pending")
            .select_related("social_user")[:30]
        )
    if is_member and me:
        member_ids = CommunityMember.objects.filter(community=group).values("social_user_id")
        ctx["invite_friends"] = list(
            accepted_friends(me).exclude(id__in=member_ids).defer(*PROFILE_DEFER)[:12]
        )

    if tab == "wall":
        ctx["form"] = CommunityPostForm(auto_id="id_w_%s", initial={"board": "wall"})
        from apps.social.likes import attach_group_post_likes
        ctx["wall_posts"] = attach_group_post_likes(list(qs.filter(topic="wall")[:20]), me)
    elif tab == "discussion":
        from apps.social.likes import attach_group_post_likes
        discuss = qs.exclude(topic="wall").order_by(F("updated_at").desc(nulls_last=True), "-id")
        ctx["n_topics"] = discuss.count()
        ctx["posts"] = attach_group_post_likes(
            list(discuss[:40] if request.GET.get("all") else discuss[:5]), me,
        )
        ctx["board_form"] = CommunityPostForm(auto_id="id_b_%s", initial={"board": "discussion"})
        tid = request.GET.get("topic")
        if tid and str(tid).isdigit():
            open_topic = (
                next((p for p in ctx["posts"] if p.id == int(tid)), None)
                or discuss.filter(pk=tid).first()
            )
            if open_topic and not hasattr(open_topic, "n_likes"):
                attach_group_post_likes([open_topic], me)
            ctx["open_topic"] = open_topic
    elif tab == "photos":
        from apps.social.likes import attach_group_post_likes
        ctx["photo_form"] = CommunityPostForm(auto_id="id_ph_%s", initial={"board": "wall"})
        ctx["photos"] = attach_group_post_likes(
            list(qs.exclude(media_path__isnull=True).exclude(media_path="")[:24]), me,
        )
    elif tab == "docs":
        from apps.social import group_docs as gdocs
        from apps.social.forms import GroupDocForm
        ctx["docs"] = gdocs.docs_for(group)
        ctx["doc_form"] = GroupDocForm() if can_post else None
    elif tab == "members":
        ctx["members"] = list(
            SocialProfile.objects.filter(memberships__community=group)
            .defer(*PROFILE_DEFER).order_by("name")[:48]
        )
    elif tab == "events":
        ctx["events"] = list(Event.objects.filter(community=group).order_by("starts_at")[:12])
    return ctx
