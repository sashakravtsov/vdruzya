"""Columns to defer on hot paths — JSON blobs + post-2006 leftovers still in the live schema."""

# Info-tab fields (looking_for / interested_in / languages) stay undeferred — profile_page reads them.
PROFILE_DEFER = (
    "pronouns", "life_goals", "family_status", "district", "verified",
)
# mood/emoji/sticker — schema leftovers (gifts undefer sticker on their query path);
# shared_post powers classic Share (2009+)
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
