"""Hard-delete helpers for unmanaged DO_NOTHING relations."""
from __future__ import annotations


def purge_wall_posts(post_ids) -> None:
    """Remove wall Post rows + DO_NOTHING dependents (comments, media, tags…)."""
    if not post_ids:
        return
    from apps.social.models import Comment, Post, PostMedia
    from apps.social.models.era2012 import CollectionItem
    from apps.social.models.era2014 import SavedItem
    from apps.social.models.legacy import CommentReaction, PostTag, Reaction

    cids = list(Comment.objects.filter(post_id__in=post_ids).values_list("id", flat=True))
    if cids:
        CommentReaction.objects.filter(comment_id__in=cids).delete()
    Comment.objects.filter(post_id__in=post_ids).delete()
    Reaction.objects.filter(post_id__in=post_ids).delete()
    PostTag.objects.filter(post_id__in=post_ids).delete()
    PostMedia.objects.filter(post_id__in=post_ids).delete()
    CollectionItem.objects.filter(post_id__in=post_ids).delete()
    SavedItem.objects.filter(post_id__in=post_ids).delete()
    Post.objects.filter(id__in=post_ids).delete()
