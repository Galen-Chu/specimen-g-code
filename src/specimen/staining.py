"""Staining step library: named, declarative feature-derivation steps (Phase 3).

SOP staining rules (docs/SOP.md §3): no anonymous lambdas — every derived
column comes from a **named step with declared parameters**, and the manifest
records the invocation via ``step_call`` so provenance is auditable without
this codebase. Composition stays plain Python for now: the *registration* and
the first cross-domain steps land today, the DSL question stays open
(DESIGN open question 2).

- ``asof_join`` — the only sanctioned cross-grain join (I3's operational
  half). Quarterly values become daily-grain features once ``lag_days`` have
  passed since the quarter ended; target rows earlier than the first
  availability are **dropped, never filled** (the ``fillna(0)`` failure case
  from the case study). ``lag_days >= 90`` is the quarterly→daily floor: the
  disclosure window a report cannot beat.
- ``diff`` / ``ratio`` / ``pct_change`` — column arithmetic as named steps.
  ``ratio`` refuses zero denominators loudly; ``pct_change`` drops rows that
  lack the lookback window. Nothing is guessed, nothing is filled.

Determinism: every step is a pure function of its CSV text inputs; floats
format through the recipe idiom (int when integral, ``repr`` otherwise), so
the same inputs always yield the same bytes.
"""

from __future__ import annotations

import csv
import io
from bisect import bisect_right
from collections.abc import Callable
from datetime import date, timedelta

StepFn = Callable[..., str]

STEPS: dict[str, StepFn] = {}


def _registered(fn: StepFn) -> StepFn:
    STEPS[fn.__name__] = fn
    return fn


def require_registered(name: str) -> None:
    """A recorded step name must be a registered one — an anonymous step is a refusal."""
    if name not in STEPS:
        raise ValueError(f"unknown staining step {name!r} (registered: {sorted(STEPS)})")


def _fmt(value: float) -> str:
    """Deterministic float formatting: int when integral, repr otherwise."""
    return str(int(value)) if value.is_integer() else repr(value)


def step_call(step: str, **params: object) -> str:
    """Canonical manifest record of one step invocation: ``step(k=v, ...)``.

    The first argument is the step's registered name (``step`` — ``name``
    itself is a common step parameter, e.g. the derived column of a ratio).
    Params render sorted by key (determinism); tuples join with commas,
    floats use ``_fmt``, everything else prints as-is. The result goes into
    the manifest's ``steps`` list verbatim.
    """
    require_registered(step)

    def render(value: object) -> str:
        if isinstance(value, float):
            return _fmt(value)
        if isinstance(value, tuple):
            return ",".join(str(item) for item in value)
        return str(value)

    inner = ", ".join(f"{key}={render(value)}" for key, value in sorted(params.items()))
    return f"{step}({inner})"


def _rows(text: str) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    reader = csv.DictReader(io.StringIO(text))
    return tuple(reader.fieldnames or []), list(reader)


def _write(header: tuple[str, ...], rows: list[dict[str, str]]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=header, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({name: row[name] for name in header})
    return buffer.getvalue()


@_registered
def asof_join(
    source_text: str,
    target_text: str,
    columns: tuple[str, ...],
    lag_days: float = 90.0,
    date_key: str = "date",
    symbol_key: str = "symbol",
) -> str:
    """Quarterly values onto the daily grain, availability-respecting (I3).

    For each target row, a source value is usable when
    ``source_date + lag_days <= target_date`` — the newest such source row
    wins (as-of semantics). Target rows before the first availability are
    **dropped, never filled**. ``lag_days >= 90`` is enforced: the quarterly
    disclosure window no report can beat.
    """
    if lag_days < 90.0:
        raise ValueError(f"quarterly→daily as-of joins need lag_days >= 90 (the disclosure window), got {lag_days}")
    if not columns:
        raise ValueError("asof_join: at least one column to carry over is required")

    source_header, source_rows = _rows(source_text)
    missing = [c for c in columns if c not in source_header]
    if missing:
        raise ValueError(f"asof_join: columns {missing} are not in the source header {list(source_header)}")

    # Source rows grouped by symbol, dates ascending — bisect finds the newest
    # usable report in O(log n).
    by_symbol: dict[str, list[tuple[str, dict[str, str]]]] = {}
    for row in source_rows:
        by_symbol.setdefault(row[symbol_key], []).append((row[date_key], row))
    for symbol in by_symbol:
        by_symbol[symbol].sort(key=lambda pair: pair[0])
    available_dates = {
        symbol: [(date.fromisoformat(d) + timedelta(days=lag_days)).isoformat() for d, _ in rows]
        for symbol, rows in by_symbol.items()
    }

    target_header, target_rows = _rows(target_text)
    missing = [c for c in (date_key, symbol_key) if c not in target_header]
    if missing:
        raise ValueError(f"asof_join: target key {missing} missing from header {list(target_header)}")

    kept: list[dict[str, str]] = []
    for row in target_rows:
        symbol = row[symbol_key]
        usable = available_dates.get(symbol, [])
        index = bisect_right(usable, row[date_key])
        if index == 0:
            continue  # declared: nothing was public yet — the row is dropped, not filled
        _, report = by_symbol[symbol][index - 1]
        kept.append({**row, **{column: report[column] for column in columns}})

    return _write(target_header + tuple(columns), kept)


@_registered
def diff(table_text: str, a: str, b: str, name: str) -> str:
    """``name = a - b``, row-wise, on numeric columns."""
    header, rows = _rows(table_text)
    if name in header:
        raise ValueError(f"diff: column {name!r} already exists")
    out: list[dict[str, str]] = []
    for row in rows:
        value = float(row[a]) - float(row[b])
        out.append({**row, name: _fmt(value)})
    return _write(header + (name,), out)


@_registered
def ratio(table_text: str, numerator: str, denominator: str, name: str) -> str:
    """``name = numerator / denominator``; a zero denominator refuses loudly
    (a silent inf is a fabricated value)."""
    header, rows = _rows(table_text)
    if name in header:
        raise ValueError(f"ratio: column {name!r} already exists")
    out: list[dict[str, str]] = []
    for row in rows:
        denominator_value = float(row[denominator])
        if denominator_value == 0.0:
            raise ValueError(f"ratio: zero denominator in {denominator!r} — refuse to fabricate a value")
        value = float(row[numerator]) / denominator_value
        out.append({**row, name: _fmt(value)})
    return _write(header + (name,), out)


@_registered
def pct_change(table_text: str, column: str, periods: int, name: str) -> str:
    """``name = column[t] / column[t - periods] - 1`` in row order.

    Rows without the full lookback window are **dropped** — the honest idiom
    this project shares with the forward-return label. ``periods`` must be >= 1.
    """
    if periods < 1:
        raise ValueError(f"pct_change: periods must be >= 1, got {periods}")
    header, rows = _rows(table_text)
    if name in header:
        raise ValueError(f"pct_change: column {name!r} already exists")
    out: list[dict[str, str]] = []
    for index, row in enumerate(rows):
        if index < periods:
            continue  # no honest lookback yet — dropped, not filled
        previous = float(rows[index - periods][column])
        if previous == 0.0:
            raise ValueError(f"pct_change: zero base value in {column!r} at row {index - periods}")
        value = float(row[column]) / previous - 1.0
        out.append({**row, name: _fmt(value)})
    return _write(header + (name,), out)


__all__ = ["STEPS", "asof_join", "diff", "pct_change", "ratio", "require_registered", "step_call"]
