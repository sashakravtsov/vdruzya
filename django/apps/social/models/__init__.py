"""ORM surface for classic FB-2006 features. Post-2006 columns stay deferred / unmanaged."""
from .defer import GROUP_POST_DEFER, POST_DEFER, PROFILE_DEFER, profile_related
from .fields import PgJSON
from .people import Block, Education, Experience, Friendship, SocialProfile
from .feed import Comment, Post, PostMedia
from .groups import (
    Community, CommunityJoinRequest, CommunityMember, CommunityPost, CommunityPostComment,
    CommunityPostMedia,
)
from .chat import Conversation, ConversationMember, Message, Notification
from .more import Album, Event, EventAttendee, Photo, PhotoComment

__all__ = [
    "PgJSON", "PROFILE_DEFER", "POST_DEFER", "GROUP_POST_DEFER", "profile_related",
    "SocialProfile", "Friendship", "Block", "Education", "Experience",
    "Post", "PostMedia", "Comment",
    "Community", "CommunityMember", "CommunityPost", "CommunityPostComment",
    "CommunityPostMedia", "CommunityJoinRequest",
    "Conversation", "ConversationMember", "Message", "Notification",
    "Album", "Photo", "PhotoComment", "Event", "EventAttendee",
]
