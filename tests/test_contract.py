"""Contracts: type, range, key-uniqueness and missing-column violations."""

from __future__ import annotations

from specimen.contract import validate_table
from specimen.manifest import ColumnSpec, TableContract

CONTRACT = TableContract(
    name="daily",
    grain="daily",
    key=("date", "symbol"),
    columns=(
        ColumnSpec("close", "float", lo=0.0, hi=1000.0),
        ColumnSpec("date", "date"),
        ColumnSpec("symbol", "string"),
    ),
)

CLEAN = "date,symbol,close\n2026-01-02,ACME,101.5\n2026-01-03,GLOB,55.0\n"


def test_clean_table_passes() -> None:
    assert validate_table(CONTRACT, CLEAN) == []


def test_duplicate_key_is_reported() -> None:
    text = "date,symbol,close\n2026-01-02,ACME,101.5\n2026-01-02,ACME,102.0\n"
    assert any("duplicate key" in p for p in validate_table(CONTRACT, text))


def test_range_violations_are_reported() -> None:
    text = "date,symbol,close\n2026-01-02,ACME,2000.0\n2026-01-03,GLOB,-1.0\n"
    problems = validate_table(CONTRACT, text)
    assert any("above range" in p for p in problems)
    assert any("below range" in p for p in problems)


def test_type_violations_are_reported() -> None:
    text = "date,symbol,close\n2026-1-2,ACME,101.5\n2026-01-03,GLOB,not-a-number\n"
    problems = validate_table(CONTRACT, text)
    assert any("not a valid date" in p for p in problems)
    assert any("not a valid float" in p for p in problems)


def test_missing_column_short_circuits() -> None:
    text = "date,symbol\n2026-01-02,ACME\n"
    assert any("missing columns" in p for p in validate_table(CONTRACT, text))


def test_empty_cells_are_reported() -> None:
    text = "date,symbol,close\n2026-01-02,ACME,\n"
    assert any("empty cell" in p for p in validate_table(CONTRACT, text))
