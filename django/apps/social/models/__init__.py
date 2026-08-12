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
from .more import Album, Event, EventAttendee, Photo, PhotoComment, PhotoTag
from .pages import Company, CompanyAdmin, CompanyFollower
from .stickers import Sticker, StickerPack
from .extra import FriendList, FriendListMember, MarketplaceListing
from .era2010 import (
    ClassicPoll, ClassicPollOption, ClassicPollVote,
    Place, PlaceCheckin, PlaceReview,
    Question, QuestionAnswer, QuestionVote,
)
from .legacy import (
    CommentReaction, GroupCommentReaction, GroupDoc, PhotoCommentReaction,
    PhotoReaction, PostTag, Reaction, RelationshipRequest,
)

__all__ = [
    "PgJSON", "PROFILE_DEFER", "POST_DEFER", "GROUP_POST_DEFER", "profile_related",
    "SocialProfile", "Friendship", "Block", "Education", "Experience",
    "Post", "PostMedia", "Comment",
    "Community", "CommunityMember", "CommunityPost", "CommunityPostComment",
    "CommunityPostMedia", "CommunityJoinRequest",
    "Conversation", "ConversationMember", "Message", "Notification",
    "Album", "Photo", "PhotoComment", "PhotoTag", "Event", "EventAttendee",
    "Company", "CompanyAdmin", "CompanyFollower",
    "Sticker", "StickerPack",
    "FriendList", "FriendListMember", "MarketplaceListing",
    "Place", "PlaceCheckin", "PlaceReview",
    "Question", "QuestionAnswer", "QuestionVote",
    "ClassicPoll", "ClassicPollOption", "ClassicPollVote",
    "Reaction", "PhotoReaction", "CommentReaction",
    "PhotoCommentReaction", "GroupCommentReaction",
    "PostTag", "GroupDoc", "RelationshipRequest",
]
