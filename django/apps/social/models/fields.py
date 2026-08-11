from __future__ import annotations
import json
from django.db.models import Field


class PgJSON(Field):
    def db_type(self, connection):
        return "jsonb"

    def from_db_value(self, value, expression, connection):
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
        return value
