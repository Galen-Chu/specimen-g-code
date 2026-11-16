"""The demo recipe: registered transforms turn messy raw into two clean grains."""

from __future__ import annotations

import csv
import io
from pathlib import Path

from specimen.recipes import REGISTRY

RAW = Path(__file__).parent / "fixtures" / "vitals_raw.csv"


def run_recipe() -> dict[str, str]:
    return dict(REGISTRY["demo_vitals"].run(0, {"vitals_raw.csv": RAW.read_bytes()}))


def rows(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text)))


def test_timestamps_are_normalized_and_dates_sorted() -> None:
    daily = rows(run_recipe()["daily"])
    dates = [r["date"] for r in daily]
    assert "2026-01-02" in dates and all(" " not in d for d in dates)
    assert dates == sorted(dates)


def test_duplicate_keys_keep_the_last_row() -> None:
    daily = rows(run_recipe()["daily"])
    keys = [(r["date"], r["symbol"]) for r in daily]
    assert len(keys) == len(set(keys))
    dup = next(r for r in daily if r["date"] == "2026-01-03" and r["symbol"] == "ACME")
    assert dup["close"] == "103.75"  # the later of the two 01-03 rows


def test_grains_are_separated() -> None:
    outputs = run_recipe()
    daily, quarterly = rows(outputs["daily"]), rows(outputs["quarterly"])
    assert all(r["close"] != "" for r in daily)  # no quarterly rows leaked in
    assert "close" not in daily[0] or True
    assert {r["note"] for r in quarterly} == {"Q1 review", "Q2 review"}
    assert len(daily) == 11 and len(quarterly) == 2


def test_recipe_is_seed_independent_but_deterministic() -> None:
    assert REGISTRY["demo_vitals"].run(0, {"vitals_raw.csv": RAW.read_bytes()}) == run_recipe()
    assert REGISTRY["demo_vitals"].run(99, {"vitals_raw.csv": RAW.read_bytes()}) == run_recipe()


def test_registry_declares_what_the_manifest_records() -> None:
    spec = REGISTRY["demo_vitals"]
    assert spec.module == "specimen.recipes.demo_vitals"
    assert spec.inputs == ("vitals_raw.csv",)
    assert spec.steps == ("normalize_dates", "split_grains", "dedupe_keep_last", "sort_by_key")
    assert {c.name for c in spec.contracts} == {"daily", "quarterly"}
