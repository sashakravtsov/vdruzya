"""Group show tab payload — short builders; group_page.page_ctx re-exports."""
from __future__ import annotations

from django.db.models import Count, F

from apps.social.forms import CommentForm, CommunityPostForm, EventForm, GroupDocForm
from apps.social.group_page import ADMIN_ROLES, access, posts_qs, _tab
from apps.social.models import (
    PROFILE_DEFER, Community, CommunityJoinRequest, CommunityMember, Event, SocialProfile,
)
from apps.social.services import accepted_friends


def _base(group, me, tab, access_row):
    from apps.social.compose_ui import editor_context
    is_member, is_admin, can_view, can_post, join_pending = access_row
    return {
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
        **editor_context(stickers=False),
    }


def _shared(ctx, group, me, *, is_member, is_admin):
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


def _wall(ctx, qs, me):
    from apps.social.likes import attach_group_post_likes
    from apps.social.classic_extra import hydrate_posted
    ctx["form"] = CommunityPostForm(auto_id="id_w_%s", initial={"board": "wall"})
    wall_posts = attach_group_post_likes(list(qs.filter(topic="wall")[:20]), me)
    for p in wall_posts:
        if getattr(p, "kind", None) == "video":
            hydrate_posted(p)
    ctx["wall_posts"] = wall_posts


def _discussion(ctx, qs, me, request):
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


def _photos(ctx, qs, me):
    from apps.social.likes import attach_group_post_likes
    ctx["photo_form"] = CommunityPostForm(auto_id="id_ph_%s", initial={"board": "wall"})
    ctx["photos"] = attach_group_post_likes(
        list(qs.exclude(media_path__isnull=True).exclude(media_path="")[:24]), me,
    )


def _docs(ctx, group, can_post):
    from apps.social import group_docs as gdocs
    ctx["docs"] = gdocs.docs_for(group)
    ctx["doc_form"] = GroupDocForm() if can_post else None


def _members(ctx, group):
    ctx["members"] = list(
        SocialProfile.objects.filter(memberships__community=group)
        .defer(*PROFILE_DEFER).order_by("name")[:48]
    )


def _events(ctx, group):
    ctx["events"] = list(Event.objects.filter(community=group).order_by("starts_at")[:12])


def page_ctx(request, group, me):
    access_row = access(me, group)
    tab = _tab(request)
    ctx = _base(group, me, tab, access_row)
    is_member, is_admin, can_view, can_post, _ = access_row
    if not can_view:
        return ctx
    qs = posts_qs(group)
    _shared(ctx, group, me, is_member=is_member, is_admin=is_admin)
    if tab == "wall":
        _wall(ctx, qs, me)
    elif tab == "discussion":
        _discussion(ctx, qs, me, request)
    elif tab == "photos":
        _photos(ctx, qs, me)
    elif tab == "docs":
        _docs(ctx, group, can_post)
    elif tab == "members":
        _members(ctx, group)
    elif tab == "events":
        _events(ctx, group)
    return ctx
