"""Schema validation utilities"""
from __future__ import annotations
import json
from pathlib import Path
from jsonschema import validate, ValidationError


def get_schema() -> dict:
    path = Path(__file__).parent.parent.parent.parent / "config" / "schema.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def validate_config(raw: dict) -> None:
    schema = get_schema()
    try:
        validate(raw, schema)
    except ValidationError as e:
        raise ValueError(f"Config validation error: {e.message}") from e
