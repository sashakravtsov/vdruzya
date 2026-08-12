"""Group categories — FB 2005-style catalog (short, no class)."""

CATALOG = (
    ("business", "Бизнес"),
    ("tech", "Технологии"),
    ("student", "Студенческие"),
    ("education", "Образование"),
    ("sport", "Спорт"),
    ("music", "Музыка"),
    ("games", "Игры"),
    ("culture", "Культура"),
    ("hobby", "Хобби"),
    ("travel", "Путешествия"),
    ("city", "Город"),
    ("parents", "Родители"),
    ("science", "Наука"),
    ("health", "Здоровье"),
    ("other", "Другое"),
)

CHOICES = CATALOG
LABELS = dict(CATALOG)


def label(slug):
    if not slug:
        return LABELS["other"]
    return LABELS.get(str(slug).strip().lower(), str(slug))
