"""Runtime invariant gates (docs/DESIGN.md section 4).

I1 (time safety), I2 (target purity) and I3 (grain separation) are executed
at the assay door, not advised in documentation. ``read_split`` is the only
sanctioned way to obtain train/valid/test membership — splits belong to the
specimen (DESIGN section 2), so self-cutting experiments have nothing to
cut on. ``check_time_safety`` re-verifies any labeling against the sealed
boundaries, catching labelings that arrived from anywhere else.
``check_target_purity`` refuses the target among the features and any
non-key feature whose availability lag is undeclared: an anonymous column
is a refusal, not an assumption. ``check_grain_separation`` is the
structural half of I3; the operational half (cross-grain joins are as-of)
becomes per-join checkable when staining's registered as-of step lands
(Phase 3). I4 (bit-reproducibility) lives in ``catalog.verify``.

Derivation detection (a feature computed from the target) lands with the
staining registry in Phase 3; until then, declared availability is the
gate.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from .contract import parse_date
from .manifest import Manifest, Splits, TableContract, grain_problems

SEGMENTS = ("train", "valid", "test")


@dataclass(frozen=True)
class SplitAssignment:
    """Row membership derived from the sealed splits.

    ``labels`` holds one segment name per data row; ``train``/``valid``/
    ``test`` hold the row indices (0-based, header excluded) per segment.
    """

    dates: tuple[str, ...]
    labels: tuple[str, ...]
    train: tuple[int, ...]
    valid: tuple[int, ...]
    test: tuple[int, ...]


def _boundaries(splits: Splits) -> tuple[date, date]:
    if splits.method == "integer-ordered":
        raise ValueError(f"integer-ordered splits (ADR-0001) split on the seed column, not dates: {splits!r}")
    train_end = parse_date(splits.train_end)
    valid_end = parse_date(splits.valid_end)
    if train_end is None or valid_end is None or train_end >= valid_end:
        raise ValueError(f"splits boundaries must be dates with train_end < valid_end, got {splits!r}")
    return train_end, valid_end


def _seed_boundaries(splits: Splits) -> tuple[int, int]:
    if splits.method != "integer-ordered":
        raise ValueError(f"time-ordered splits split on dates, not seeds: {splits!r}")
    try:
        train_end, valid_end = int(splits.train_end), int(splits.valid_end)
    except ValueError:
        raise ValueError(
            f"integer-ordered boundaries must be integer seeds with train_end < valid_end, got {splits!r}"
        ) from None
    if train_end >= valid_end:
        raise ValueError(f"integer-ordered boundaries must be integers with train_end < valid_end, got {splits!r}")
    return train_end, valid_end


def split_column(contract: TableContract, method: str) -> str:
    """The key column a split reads: the date key for time-ordered; for
    integer-ordered (ADR-0001) the int key named ``seed`` — else the first int
    key. Refuses when the contract lacks a usable one."""
    wanted = "int" if method == "integer-ordered" else "date"
    candidates = [column.name for column in contract.columns if column.name in contract.key and column.type == wanted]
    if not candidates:
        raise ValueError(f"contract {contract.name!r}: no key column of type {wanted!r} to split on")
    if method == "integer-ordered" and "seed" in candidates:
        return "seed"
    return candidates[0]


def read_split(table_text: str, date_column: str, splits: Splits) -> SplitAssignment:
    """Assign every data row of a CSV table to a segment by the sealed boundaries.

    ``date_column`` is the column the split reads — the date key for
    ``time-ordered`` splits, the seed key for ``integer-ordered`` (ADR-0001).
    train: value <= train_end; valid: train_end < value <= valid_end;
    test: value > valid_end. Raises on malformed values, a missing column
    or invalid boundaries — the reader refuses ambiguous input rather than
    guessing.
    """
    train_end: Any
    valid_end: Any
    if splits.method == "integer-ordered":
        train_end, valid_end = _seed_boundaries(splits)
    else:
        train_end, valid_end = _boundaries(splits)
    reader = csv.DictReader(io.StringIO(table_text))
    if date_column not in (reader.fieldnames or []):
        raise ValueError(f"split column {date_column!r} is not in the table header")
    values: list[str] = []
    labels: list[str] = []
    for row_number, row in enumerate(reader, start=2):
        value = row[date_column] or ""
        try:
            parsed = _parse_split_value(splits, value)
        except ValueError as error:
            raise ValueError(f"row {row_number}: {error}") from None
        values.append(value)
        labels.append(_classify(parsed, train_end, valid_end))
    return SplitAssignment(
        dates=tuple(values),
        labels=tuple(labels),
        train=tuple(i for i, label in enumerate(labels) if label == "train"),
        valid=tuple(i for i, label in enumerate(labels) if label == "valid"),
        test=tuple(i for i, label in enumerate(labels) if label == "test"),
    )


def _parse_int(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        return None


def _parse_split_value(splits: Splits, value: str) -> Any:
    """Parse one split value per the method: an int seed for integer-ordered
    (ADR-0001), an ISO date for time-ordered. Raises on malformed values."""
    if splits.method == "integer-ordered":
        number = _parse_int(value)
        if number is None:
            raise ValueError(f"{value!r} is not a valid integer seed")
        return number
    parsed = parse_date(value)
    if parsed is None:
        raise ValueError(f"{value!r} is not a valid YYYY-MM-DD date")
    return parsed


def _classify(parsed: Any, train_end: Any, valid_end: Any) -> str:
    """The same intervals for both methods — the parsed value's type carries
    the ordering, so one ladder serves dates and seeds alike."""
    return "train" if parsed <= train_end else "valid" if parsed <= valid_end else "test"


def check_time_safety(assignment: SplitAssignment, splits: Splits) -> list[str]:
    """I1 gate: a labeling must respect the sealed boundaries in declared order.

    For ``time-ordered`` every train row <= train_end (dates); for
    ``integer-ordered`` (ADR-0001) the same intervals over the seed column.
    An assignment produced by ``read_split`` passes trivially; the gate
    exists for labelings that came from anywhere else. Empty list = pass.
    """
    problems: list[str] = []
    train_end: Any
    valid_end: Any
    try:
        if splits.method == "integer-ordered":
            train_end, valid_end = _seed_boundaries(splits)
        else:
            train_end, valid_end = _boundaries(splits)
    except ValueError as error:
        return [f"splits: {error}"]
    for row_number, (label, value) in enumerate(zip(assignment.labels, assignment.dates, strict=True), start=2):
        try:
            parsed = _parse_split_value(splits, value)
        except ValueError:
            problems.append(f"row {row_number}: {value!r} is not a valid split value")
            continue
        if label not in SEGMENTS:
            problems.append(f"row {row_number}: unknown segment {label!r}")
        elif label == "train" and parsed > train_end:
            problems.append(f"row {row_number}: train row at {value} is after train_end {splits.train_end}")
        elif label == "valid" and not train_end < parsed <= valid_end:
            problems.append(
                f"row {row_number}: valid row at {value} is outside ({splits.train_end}, {splits.valid_end}]"
            )
        elif label == "test" and parsed <= valid_end:
            problems.append(f"row {row_number}: test row at {value} is not after valid_end {splits.valid_end}")
    return problems


def check_target_purity(contract: TableContract, target: str, features: Sequence[str]) -> list[str]:
    """I2 gate: the assay door for a feature list.

    Refusals: the target appearing among the features; a target or feature
    unknown to the contract; a non-key feature without a declared
    availability lag. Key columns are exempt — they are the row's own
    identity, knowable with the row itself.
    """
    problems: list[str] = []
    columns = {column.name: column for column in contract.columns}
    if target not in columns:
        problems.append(f"target {target!r} is not declared in contract {contract.name!r}")
    if target in features:
        problems.append(f"target {target!r} must not appear among the features")
    for name in features:
        column = columns.get(name)
        if column is None:
            problems.append(f"feature {name!r} is not declared in contract {contract.name!r}")
            continue
        if name in contract.key:
            continue
        if column.availability_lag_days is None:
            problems.append(
                f"feature {name!r}: availability_lag_days is undeclared (I2 refuses anonymous availability)"
            )
        elif column.availability_lag_days < 0:
            problems.append(f"feature {name!r}: availability_lag_days must be >= 0")
    return problems


def check_grain_separation(manifest: Manifest) -> list[str]:
    """I3 gate (structural): every table lives at exactly one declared, well-formed grain.

    Output and contract must agree on the grain, and the grain name must
    follow the manifest pattern. Refuses mixed-grain or hand-drifted
    manifests at the assay door; grain mixing itself is prevented at
    preparation, where recipes that blur grains cannot seal contracts
    that pass here.
    """
    return grain_problems(manifest)
