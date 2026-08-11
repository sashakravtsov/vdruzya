from __future__ import annotations
import json
from django.db.models import Field


class PgJSON(Field):
    """Postgres json/jsonb column; dumps list/dict for the json adapter."""

    def db_type(self, connection):
        return "json"

    def from_db_value(self, value, expression, connection):
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return value

    def to_python(self, value):
        if value is None or isinstance(value, (list, dict)):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return value

    def get_prep_value(self, value):
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return value
