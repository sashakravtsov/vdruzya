"""Old-school emoji / text-emoticon sets for classic Inbox editor (no npm)."""

# Curated Unicode faces & reactions — readable on classic chrome, no library.
EMOJIS = (
    "😀", "😃", "😄", "😁", "😆", "😅", "😂", "😊", "😇", "🙂",
    "😉", "😌", "😍", "😘", "😗", "😙", "😚", "😋", "😜", "😝",
    "😛", "😎", "🤓", "🧐", "😐", "😑", "😶", "😏", "😒", "🙄",
    "😬", "😮", "😯", "😲", "😳", "🥺", "😢", "😭", "😤", "😠",
    "😡", "🤬", "😈", "👿", "💀", "💩", "👍", "👎", "👏", "🙏",
    "💪", "👀", "❤️", "💔", "💕", "💖", "⭐", "🔥", "🎉", "🎁",
    "💯", "✅", "❌", "💤", "☕", "🎂",
)

# Classic IM-era text smileys (Yahoo/ICQ/MSN muscle memory).
TEXT_EMOTES = (
    ":)", ";)", ":D", ":P", ":(", ":O", ":|", ":'(", "<3", "</3",
    "^^", "o_O", ">_>", "¯\\_(ツ)_/¯",
)


def editor_ctx(*, stickers=None, target_id="id_message_body", sticker_input_id="id_sticker"):
    return {
        "emojis": EMOJIS,
        "text_emotes": TEXT_EMOTES,
        "stickers": stickers or [],
        "target_id": target_id,
        "sticker_input_id": sticker_input_id,
    }
