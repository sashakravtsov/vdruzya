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
    """Group show context — builders live in group_ctx."""
    from apps.social.group_ctx import page_ctx as build
    return build(request, group, me)
