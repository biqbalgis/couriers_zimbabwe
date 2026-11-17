"""Read Django model metadata for the documentation without changing the database."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from django.apps import apps
from django.db import connection
from django.db.models import NOT_PROVIDED


def describe(model):
    fields = []
    for field in model._meta.local_fields:
        default = field.default
        default = None if default is NOT_PROVIDED else (
            getattr(default, "__name__", str(default)) if callable(default) else str(default))
        target = field.related_model._meta.db_table if field.is_relation else None
        fields.append({
            "name": field.name, "column": field.column,
            "type": field.get_internal_type(), "max_length": field.max_length,
            "digits": getattr(field, "max_digits", None),
            "places": getattr(field, "decimal_places", None),
            "null": field.null, "blank": field.blank, "primary_key": field.primary_key,
            "unique": field.unique, "index": field.db_index, "default": default,
            "choices": [str(value) for value, _ in field.choices] if field.choices else [],
            "target": target,
            "on_delete": getattr(getattr(field, "remote_field", None), "on_delete", None).__name__
            if target else None,
            "auto_created": str(getattr(field, "auto_now_add", False)),
        })
    return {
        "model": model.__name__, "app": model._meta.app_label,
        "table": model._meta.db_table, "auto_created": bool(model._meta.auto_created),
        "fields": fields,
        "indexes": [{"name": index.name, "fields": list(index.fields)} for index in model._meta.indexes],
        "constraints": [
            {"name": c.name, "fields": list(getattr(c, "fields", [])),
             "condition": str(getattr(c, "condition", "") or "")}
            for c in model._meta.constraints],
        "unique_together": [list(items) for items in model._meta.unique_together],
    }


print(json.dumps({"engine": connection.vendor, "models": [
    describe(model) for model in apps.get_models(include_auto_created=True)
]}))
