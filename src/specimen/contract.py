"""Table contracts: validate a CSV table against its declared shape.

The contract is the schema chapter of a specimen (docs/DESIGN.md §3): a
declared grain, a key, and typed columns with optional ranges and
availability lags. Phase 1 enforces structure, types, ranges and key
uniqueness; the availability lag (invariant I2) becomes an assay-time gate
in Phase 2.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence

from .manifest import TableContract

_DATE_LENGTH = 10


def _parse_typed(value: str, type_name: str) -> float | None:
    """Parse a cell as its declared type; None means the cell does not typecheck."""
    try:
        if type_name == "float":
            return float(value)
        if type_name == "int":
            parsed = float(value)
            return parsed if parsed.is_integer() else None
        if type_name == "date":
            if len(value) != _DATE_LENGTH or value[4] != "-" or value[7] != "-":
                return None
            year, month, day = int(value[:4]), int(value[5:7]), int(value[8:10])
            if not 1 <= month <= 12 or not 1 <= day <= 31:
                return None
            return float(year * 10000 + month * 100 + day)
    except ValueError:
        return None
    return None


def validate_table(contract: TableContract, text: str) -> list[str]:
    """Validate one CSV table (LF text) against its contract; empty list = pass."""
    problems: list[str] = []
    reader = csv.DictReader(io.StringIO(text))
    header = reader.fieldnames or []
    expected = [c.name for c in contract.columns]
    missing = [name for name in expected if name not in header]
    if missing:
        return [f"{contract.name}: missing columns {missing}"]
    seen_keys: set[tuple[str, ...]] = set()
    for row_number, row in enumerate(reader, start=2):
        key = tuple(str(row[k]) for k in contract.key)
        if key in seen_keys:
            problems.append(f"{contract.name}: duplicate key {key} at row {row_number}")
        seen_keys.add(key)
        for column in contract.columns:
            value = row[column.name]
            if value == "":
                problems.append(f"{contract.name}.{column.name}: empty cell at row {row_number}")
                continue
            if column.type == "string":
                continue
            parsed = _parse_typed(value, column.type)
            if parsed is None:
                problems.append(
                    f"{contract.name}.{column.name}: {value!r} is not a valid {column.type} (row {row_number})"
                )
                continue
            if column.lo is not None and parsed < column.lo:
                problems.append(f"{contract.name}.{column.name}: {value!r} below range at row {row_number}")
            if column.hi is not None and parsed > column.hi:
                problems.append(f"{contract.name}.{column.name}: {value!r} above range at row {row_number}")
    if len(seen_keys) == 0:
        problems.append(f"{contract.name}: table has no rows")
    return problems


def validate_all(contracts: Sequence[TableContract], tables: Mapping[str, str]) -> list[str]:
    problems: list[str] = []
    for contract in contracts:
        table = tables.get(contract.name)
        if table is None:
            problems.append(f"{contract.name}: output file missing")
            continue
        problems += validate_table(contract, table)
    return problems
