"""Columns to defer on hot paths — JSON blobs + post-2006 leftovers still in the live schema."""

PROFILE_DEFER = (
    "looking_for", "interested_in", "languages",
    "cover_path", "pronouns", "life_goals", "family_status", "district", "verified",
)
POST_DEFER = ("mood", "emoji", "sticker", "search_vector")
GROUP_POST_DEFER = ("mood", "emoji", "sticker")


def profile_related(*prefixes: str) -> tuple[str, ...]:
    """Expand PROFILE_DEFER under select_related/prefetch aliases (e.g. social_user__)."""
    if not prefixes:
        return PROFILE_DEFER
    out = []
    for p in prefixes:
        out.extend(f"{p}{f}" for f in PROFILE_DEFER)
    return tuple(out)
