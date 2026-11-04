"""pgvector values for the procedure-page column.

The width matches revision ``0006`` and the laboratory embedding port. The
fake port is that default. Domain code does not choose a different width.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.types import UserDefinedType

# Revision 0006 creates vector(8). Keep this aligned with the fake port.
PROCEDURE_EMBEDDING_WIDTH = 8


class Vector(UserDefinedType):
    """PostgreSQL ``vector(n)`` as a tuple of floats."""

    cache_ok = True

    def __init__(self, dimensions: int) -> None:
        self.dimensions = dimensions

    def get_col_spec(self, **_kw: object) -> str:
        return f"vector({self.dimensions})"

    def bind_processor(self, _dialect: object):
        def process(value: Sequence[float] | None) -> str | None:
            if value is None:
                return None
            return vector_literal(value)

        return process

    def result_processor(self, _dialect: object, _coltype: object):
        def process(value: object) -> tuple[float, ...] | None:
            if value is None:
                return None
            if isinstance(value, str):
                return parse_vector_literal(value)
            if isinstance(value, tuple | list):
                return tuple(float(item) for item in value)
            raise TypeError("vector column returned an unexpected value")

        return process


def vector_literal(values: Sequence[float]) -> str:
    return "[" + ",".join(repr(float(value)) for value in values) + "]"


def parse_vector_literal(value: str) -> tuple[float, ...]:
    stripped = value.strip().strip("[]")
    if not stripped:
        return ()
    return tuple(float(part) for part in stripped.split(","))
