"""Invariant gates: I1 time safety, I2 target purity, and the split reader."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from specimen import (
    SplitAssignment,
    check_grain_separation,
    check_target_purity,
    check_time_safety,
    parse_manifest,
    read_split,
)
from specimen.manifest import ColumnSpec, Splits, TableContract
from specimen.recipes.demo_vitals import CONTRACTS, SPLITS

GOLDEN = Path(__file__).parent / "golden" / "demo-vitals-s7"

# Boundaries: train_end 2026-01-10, valid_end 2026-01-20 (SPLITS).
TABLE = "date,symbol,close\n2026-01-02,A,1\n2026-01-10,B,1\n2026-01-11,C,1\n2026-01-20,D,1\n2026-01-21,E,1\n"


def test_read_split_assigns_boundaries_inclusively() -> None:
    assignment = read_split(TABLE, "date", SPLITS)
    assert assignment.labels == ("train", "train", "valid", "valid", "test")
    assert assignment.train == (0, 1)
    assert assignment.valid == (2, 3)
    assert assignment.test == (4,)
    assert check_time_safety(assignment, SPLITS) == []


def test_read_split_on_the_golden_specimen() -> None:
    """The sealed splits, applied to the sealed table: every segment populated."""
    manifest = parse_manifest((GOLDEN / "manifest.toml").read_text(encoding="utf-8"))
    text = (GOLDEN / "daily.csv").read_text(encoding="utf-8")
    assignment = read_split(text, "date", manifest.splits)
    assert check_time_safety(assignment, manifest.splits) == []
    assert len(assignment.train) == 5 and len(assignment.valid) == 4 and len(assignment.test) == 2


def test_read_split_refuses_ambiguous_input() -> None:
    with pytest.raises(ValueError, match="not a valid"):
        read_split("date,x\n2026-02-31,a\n", "date", SPLITS)  # impossible calendar date
    with pytest.raises(ValueError, match="not in the table header"):
        read_split("when,x\n2026-01-02,a\n", "date", SPLITS)
    with pytest.raises(ValueError, match="train_end"):
        read_split(TABLE, "date", replace(SPLITS, train_end="2026-01-20"))


def test_seed_ordered_splits_read_the_seed_column() -> None:
    """ADR-0001: integer-ordered splits read the int 'seed' key with the same intervals."""
    splits = Splits(method="integer-ordered", train_end="100", valid_end="101")
    text = "seed,x\n99,a\n100,b\n101,c\n102,d\n"
    assignment = read_split(text, "seed", splits)
    assert assignment.train == (0, 1) and assignment.valid == (2,) and assignment.test == (3,)
    with pytest.raises(ValueError, match="not a valid integer seed"):
        read_split("seed,x\nx1,a\n", "seed", splits)


def test_time_safety_catches_a_rogue_labeling() -> None:
    """A self-cut that moves a post-boundary row into train is refused (I1)."""
    honest = read_split(TABLE, "date", SPLITS)
    rogue = SplitAssignment(
        dates=honest.dates,
        labels=("train", "train", "train", "valid", "holdout"),
        train=(0, 1, 2),
        valid=(3,),
        test=(),
    )
    problems = check_time_safety(rogue, SPLITS)
    assert any("train row at 2026-01-11" in p for p in problems)
    assert any("unknown segment 'holdout'" in p for p in problems)


def test_time_safety_reports_inverted_boundaries() -> None:
    assignment = read_split(TABLE, "date", SPLITS)
    problems = check_time_safety(assignment, replace(SPLITS, train_end="2026-01-25"))
    assert any("train_end < valid_end" in p for p in problems)


def test_grain_separation_passes_golden_and_catches_drift() -> None:
    manifest = parse_manifest((GOLDEN / "manifest.toml").read_text(encoding="utf-8"))
    assert check_grain_separation(manifest) == []
    drifted = replace(manifest, contracts=(replace(manifest.contracts[0], grain="weekly"),))
    assert any("differs from output grain" in p for p in check_grain_separation(drifted))


def test_target_purity_refuses_the_target_as_a_feature() -> None:
    problems = check_target_purity(CONTRACTS[0], "close", ("date", "symbol", "close"))
    assert any("must not appear among the features" in p for p in problems)


def test_target_purity_requires_declared_availability() -> None:
    """Keys are exempt (row identity); every other feature must declare its lag."""
    problems = check_target_purity(CONTRACTS[0], "close", ("date", "symbol", "volume"))
    assert any("volume" in p and "undeclared" in p for p in problems)
    assert not any(p.startswith("feature 'date'") or p.startswith("feature 'symbol'") for p in problems)


def test_target_purity_passes_declared_features() -> None:
    contract = TableContract(
        name="daily",
        grain="daily",
        key=("date", "symbol"),
        columns=(
            ColumnSpec("target_growth", "float"),
            ColumnSpec("close", "float", availability_lag_days=0.0),
            ColumnSpec("date", "date"),
            ColumnSpec("net_growth_asof", "float", availability_lag_days=90.0),
            ColumnSpec("symbol", "string"),
        ),
    )
    assert check_target_purity(contract, "target_growth", ("date", "symbol", "close", "net_growth_asof")) == []


def test_target_purity_refuses_unknown_and_negative_lag() -> None:
    contract = TableContract(
        name="daily",
        grain="daily",
        key=("date",),
        columns=(
            ColumnSpec("close", "float"),
            ColumnSpec("date", "date"),
            ColumnSpec("peek", "float", availability_lag_days=-1.0),
        ),
    )
    problems = check_target_purity(contract, "close", ("date", "peek", "phantom"))
    assert any("peek" in p and ">= 0" in p for p in problems)
    assert any("phantom" in p and "not declared" in p for p in problems)
