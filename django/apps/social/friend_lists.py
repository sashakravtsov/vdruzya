"""Classic Friend Lists — classic_extra re-exports."""
from __future__ import annotations

from django.db.models import Count

from apps.social.models import FriendList, FriendListMember, SocialProfile
from apps.social.services import friend_ids, now


def lists_for(me):
    if not me:
        return []
    return list(
        FriendList.objects.filter(social_user=me)
        .annotate(n=Count("memberships"))
        .order_by("name")
    )


def owned_list(me, list_id):
    try:
        lid = int(list_id)
    except (TypeError, ValueError):
        return None
    if not me or not lid:
        return None
    return FriendList.objects.filter(pk=lid, social_user=me).first()


def list_member_ids(flist) -> set:
    if not flist:
        return set()
    return set(
        FriendListMember.objects.filter(friend_list=flist).values_list("social_user_id", flat=True)
    )


def list_create(me, name: str):
    name = (name or "").strip()[:120]
    if not me or not name:
        return None
    t = now()
    return FriendList.objects.create(social_user=me, name=name, created_at=t, updated_at=t)


def list_rename(me, flist, name: str) -> bool:
    name = (name or "").strip()[:120]
    if not me or not flist or flist.social_user_id != me.id or not name:
        return False
    flist.name = name
    flist.updated_at = now()
    flist.save(update_fields=["name", "updated_at"])
    return True


def list_members(flist, limit=200):
    return list(
        SocialProfile.objects.filter(list_memberships__friend_list=flist)
        .order_by("name")[:limit]
    )


def list_add(me, flist, friend_id: int) -> bool:
    if not me or flist.social_user_id != me.id:
        return False
    if friend_id not in friend_ids(me):
        return False
    if FriendListMember.objects.filter(friend_list=flist, social_user_id=friend_id).exists():
        return True
    FriendListMember.objects.create(
        friend_list=flist, social_user_id=friend_id, created_at=now(),
    )
    return True


def list_remove(me, flist, friend_id: int) -> bool:
    if not me or flist.social_user_id != me.id:
        return False
    FriendListMember.objects.filter(friend_list=flist, social_user_id=friend_id).delete()
    return True
