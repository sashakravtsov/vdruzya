"""Wall topic/mood choices — FB 2005 classic labels."""
TOPICS = [
    ("thought", "Мысль"), ("idea", "Идея"), ("news", "Новость"), ("question", "Вопрос"),
    ("help", "Помощь"), ("event", "Событие"), ("work", "Работа"), ("achievement", "Успех"),
]
MOODS = [
    ("", "—"), ("happy", "радостное"), ("calm", "спокойное"), ("focused", "сосредоточенное"),
    ("inspired", "вдохновлённое"), ("curious", "любопытное"), ("grateful", "благодарное"),
    ("serious", "серьёзное"), ("worried", "встревоженное"),
]
TOPIC_KEYS = {k for k, _ in TOPICS}
MOOD_KEYS = {k for k, _ in MOODS if k}
TOPIC_LABELS = dict(TOPICS)
MOOD_LABELS = {k: v for k, v in MOODS if k}


def mood_label(key):
    if not key:
        return ""
    return MOOD_LABELS.get(str(key), str(key))


def topic_label(key):
    if not key:
        return ""
    return TOPIC_LABELS.get(str(key), str(key))
