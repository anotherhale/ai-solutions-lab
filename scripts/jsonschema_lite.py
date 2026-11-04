"""Subset JSON Schema Draft 2020-12 validator for Wasatch contracts.

Supports the keywords used by data/schemas/v1: type, properties, required,
additionalProperties, enum, const, pattern, format, minLength, minimum,
maximum, exclusiveMinimum, minItems, uniqueItems, $ref, and $defs.

This is not a complete meta-schema engine. Add jsonschema later if contracts
outgrow this subset.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any


class SchemaError(ValueError):
    """A JSON Schema validation failure."""


def _pointer(path: str, suffix: str) -> str:
    if suffix.startswith("["):
        return f"{path}{suffix}"
    return f"{path}/{suffix}"


def _json_pointer(document: Any, pointer: str) -> Any:
    if pointer in {"", "/"}:
        return document
    if not pointer.startswith("/"):
        raise SchemaError(f"invalid JSON Pointer: {pointer}")
    current = document
    for raw_part in pointer[1:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            raise SchemaError(f"JSON Pointer {pointer} not found")
    return current


class SchemaRegistry:
    """Loads schemas from disk and resolves $ref values."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self._by_path: dict[Path, dict[str, Any]] = {}

    def load(self, path: Path) -> dict[str, Any]:
        resolved = path.resolve()
        if resolved not in self._by_path:
            self._by_path[resolved] = json.loads(resolved.read_text(encoding="utf-8"))
        return self._by_path[resolved]

    def resolve(self, ref: str, current_path: Path) -> tuple[Path, dict[str, Any]]:
        uri, _, fragment = ref.partition("#")
        if uri:
            target = (current_path.parent / uri).resolve()
        else:
            target = current_path.resolve()
        schema = self.load(target)
        if fragment:
            resolved = _json_pointer(schema, fragment)
            if not isinstance(resolved, dict):
                raise SchemaError(f"$ref {ref} did not resolve to an object")
            return target, resolved
        return target, schema


def _is_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
    return _is_integer(value) or isinstance(value, float)


def _check_format(value: str, fmt: str, path: str) -> None:
    if fmt == "date":
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise SchemaError(f"{path}: invalid date {value}") from exc
    elif fmt == "date-time":
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise SchemaError(f"{path}: invalid date-time {value}") from exc
    elif fmt == "email":
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise SchemaError(f"{path}: invalid email {value}")


def validate_instance(
    instance: Any,
    schema: dict[str, Any],
    *,
    registry: SchemaRegistry,
    schema_path: Path,
    path: str = "$",
) -> None:
    if "$ref" in schema:
        ref_path, ref_schema = registry.resolve(schema["$ref"], schema_path)
        extra = {key: value for key, value in schema.items() if key != "$ref"}
        merged = {**ref_schema, **extra} if extra else ref_schema
        validate_instance(
            instance,
            merged,
            registry=registry,
            schema_path=ref_path,
            path=path,
        )
        return

    expected_type = schema.get("type")
    if expected_type == "object":
        if not isinstance(instance, dict):
            raise SchemaError(f"{path}: expected object")
        required = schema.get("required", [])
        for key in required:
            if key not in instance:
                raise SchemaError(f"{path}: missing required property {key}")
        properties = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)
        if additional is False:
            extras = set(instance) - set(properties)
            if extras:
                raise SchemaError(f"{path}: unexpected properties {sorted(extras)}")
        for key, value in instance.items():
            if key in properties:
                validate_instance(
                    value,
                    properties[key],
                    registry=registry,
                    schema_path=schema_path,
                    path=_pointer(path, key),
                )
            elif isinstance(additional, dict):
                validate_instance(
                    value,
                    additional,
                    registry=registry,
                    schema_path=schema_path,
                    path=_pointer(path, key),
                )
    elif expected_type == "array":
        if not isinstance(instance, list):
            raise SchemaError(f"{path}: expected array")
        min_items = schema.get("minItems")
        if min_items is not None and len(instance) < min_items:
            raise SchemaError(f"{path}: expected at least {min_items} items")
        if schema.get("uniqueItems") and len(instance) != len(set(map(str, instance))):
            raise SchemaError(f"{path}: items must be unique")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(instance):
                validate_instance(
                    item,
                    item_schema,
                    registry=registry,
                    schema_path=schema_path,
                    path=_pointer(path, f"[{index}]"),
                )
    elif expected_type == "string":
        if not isinstance(instance, str):
            raise SchemaError(f"{path}: expected string")
        min_length = schema.get("minLength")
        if min_length is not None and len(instance) < min_length:
            raise SchemaError(f"{path}: shorter than minLength {min_length}")
        pattern = schema.get("pattern")
        if pattern and re.search(pattern, instance) is None:
            raise SchemaError(f"{path}: {instance!r} does not match {pattern}")
        fmt = schema.get("format")
        if fmt:
            _check_format(instance, fmt, path)
    elif expected_type == "integer":
        if not _is_integer(instance):
            raise SchemaError(f"{path}: expected integer")
    elif expected_type == "number":
        if not _is_number(instance):
            raise SchemaError(f"{path}: expected number")
    elif expected_type == "boolean":
        if not isinstance(instance, bool):
            raise SchemaError(f"{path}: expected boolean")
    elif expected_type == "null":
        if instance is not None:
            raise SchemaError(f"{path}: expected null")
    elif expected_type is not None:
        raise SchemaError(f"{path}: unsupported type {expected_type}")

    if "enum" in schema and instance not in schema["enum"]:
        raise SchemaError(f"{path}: {instance!r} not in enum")
    if "const" in schema and instance != schema["const"]:
        raise SchemaError(f"{path}: expected const {schema['const']!r}")
    if _is_number(instance):
        if "minimum" in schema and instance < schema["minimum"]:
            raise SchemaError(f"{path}: below minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            raise SchemaError(f"{path}: above maximum {schema['maximum']}")
        if "exclusiveMinimum" in schema and instance <= schema["exclusiveMinimum"]:
            raise SchemaError(f"{path}: not greater than {schema['exclusiveMinimum']}")
