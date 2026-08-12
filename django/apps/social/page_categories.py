"""Page (industry) categories — classic FB Pages catalog."""

CATALOG = (
    ("local", "Местный бизнес"),
    ("brand", "Бренд / продукт"),
    ("artist", "Артист / группа"),
    ("public_figure", "Публичная личность"),
    ("entertainment", "Развлечения"),
    ("cause", "Дело / сообщество"),
    ("organization", "Организация"),
    ("website", "Сайт / блог"),
    ("other", "Другое"),
)

CHOICES = CATALOG
LABELS = dict(CATALOG)


def label(slug):
    if not slug:
        return LABELS["other"]
    return LABELS.get(str(slug).strip().lower(), str(slug))
