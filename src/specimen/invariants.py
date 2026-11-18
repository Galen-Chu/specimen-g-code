"""Runtime invariant gates (docs/DESIGN.md section 4).

I1 (time safety) and I2 (target purity) are executed at the assay door,
not advised in documentation. ``read_split`` is the only sanctioned way to
obtain train/valid/test membership — splits belong to the specimen
(DESIGN section 2), so self-cutting experiments have nothing to cut on.
``check_time_safety`` re-verifies any labeling against the sealed
boundaries, catching labelings that arrived from anywhere else.
``check_target_purity`` refuses the target among the features and any
non-key feature whose availability lag is undeclared: an anonymous column
is a refusal, not an assumption.

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

from .contract import parse_date
from .manifest import Splits, TableContract

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
    train_end = parse_date(splits.train_end)
    valid_end = parse_date(splits.valid_end)
    if train_end is None or valid_end is None or train_end >= valid_end:
        raise ValueError(f"splits boundaries must be dates with train_end < valid_end, got {splits!r}")
    return train_end, valid_end


def read_split(table_text: str, date_column: str, splits: Splits) -> SplitAssignment:
    """Assign every data row of a CSV table to a segment by the sealed boundaries.

    train: date <= train_end; valid: train_end < date <= valid_end;
    test: date > valid_end. Raises on malformed dates, a missing date
    column or invalid boundaries — the reader refuses ambiguous input
    rather than guessing.
    """
    train_end, valid_end = _boundaries(splits)
    reader = csv.DictReader(io.StringIO(table_text))
    if date_column not in (reader.fieldnames or []):
        raise ValueError(f"date column {date_column!r} is not in the table header")
    dates: list[str] = []
    labels: list[str] = []
    for row_number, row in enumerate(reader, start=2):
        value = row[date_column] or ""
        parsed = parse_date(value)
        if parsed is None:
            raise ValueError(f"row {row_number}: {value!r} is not a valid YYYY-MM-DD date")
        dates.append(value)
        labels.append("train" if parsed <= train_end else "valid" if parsed <= valid_end else "test")
    return SplitAssignment(
        dates=tuple(dates),
        labels=tuple(labels),
        train=tuple(i for i, label in enumerate(labels) if label == "train"),
        valid=tuple(i for i, label in enumerate(labels) if label == "valid"),
        test=tuple(i for i, label in enumerate(labels) if label == "test"),
    )


def check_time_safety(assignment: SplitAssignment, splits: Splits) -> list[str]:
    """I1 gate: a labeling must respect the sealed boundaries in time order.

    Every train row <= train_end, every valid row in (train_end,
    valid_end], every test row after valid_end. An assignment produced by
    ``read_split`` passes trivially; the gate exists for labelings that
    came from anywhere else. Empty list = pass.
    """
    problems: list[str] = []
    try:
        train_end, valid_end = _boundaries(splits)
    except ValueError as error:
        return [f"splits: {error}"]
    for row_number, (label, value) in enumerate(zip(assignment.labels, assignment.dates, strict=True), start=2):
        parsed = parse_date(value)
        if parsed is None:
            problems.append(f"row {row_number}: {value!r} is not a valid date")
        elif label == "train" and parsed > train_end:
            problems.append(f"row {row_number}: train row dated {value} is after train_end {splits.train_end}")
        elif label == "valid" and not train_end < parsed <= valid_end:
            problems.append(
                f"row {row_number}: valid row dated {value} is outside ({splits.train_end}, {splits.valid_end}]"
            )
        elif label == "test" and parsed <= valid_end:
            problems.append(f"row {row_number}: test row dated {value} is not after valid_end {splits.valid_end}")
        elif label not in SEGMENTS:
            problems.append(f"row {row_number}: unknown segment {label!r}")
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
