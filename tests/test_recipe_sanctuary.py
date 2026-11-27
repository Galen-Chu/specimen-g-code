"""sanctuary_worlds: the first atemporal specimen - integer-ordered splits, golden pin."""

from __future__ import annotations

import csv
import io
from pathlib import Path

from specimen import load_raw, parse_manifest, prepare, read_split, verify
from specimen.recipes import REGISTRY

FIXTURES = Path(__file__).parent / "fixtures" / "sanctuary_population"
GOLDEN = Path(__file__).parent / "golden" / "sanctuary-worlds-s100"
RAW = load_raw(FIXTURES, REGISTRY["sanctuary_worlds"].inputs)


def test_sanctuary_worlds_seals_and_passes_all_four_checks(tmp_path: Path) -> None:
    directory = tmp_path / "sanctuary-worlds-s100"
    prepare("sanctuary_worlds", 0, RAW, directory)
    ok, report = verify(directory, RAW)
    assert ok, report


def test_golden_is_byte_identical(tmp_path: Path) -> None:
    """The committed golden pins: population provenance + 3 world TOMLs, recipe, seal."""
    directory = tmp_path / "s"
    prepare("sanctuary_worlds", 0, RAW, directory)
    for filename in ("manifest.toml", "worlds.csv"):
        assert (directory / filename).read_bytes() == (GOLDEN / filename).read_bytes(), filename


def test_worlds_table_follows_the_declared_rules() -> None:
    text = (GOLDEN / "worlds.csv").read_text(encoding="utf-8")
    rows = list(csv.DictReader(io.StringIO(text)))
    assert len(rows) == 3
    seeds = [row["seed"] for row in rows]
    assert seeds == sorted(seeds) == ["100", "101", "102"]
    for row in rows:  # counts_from_scenario: meadow's composition, parsed from each world
        assert row["food_count"] == "5"
        assert row["water_count"] == "2"
        assert row["shelter_count"] == "1"
        assert row["hazard_count"] == "3"
    assert all(row["preset"] == "meadow@1" for row in rows)


def test_seed_ordered_split_degenerates_gracefully() -> None:
    """ADR-0001: the split reads the seed column; I1/I3 degenerate to seed order."""
    manifest = parse_manifest((GOLDEN / "manifest.toml").read_text(encoding="utf-8"))
    assert manifest.splits.method == "integer-ordered"
    text = (GOLDEN / "worlds.csv").read_text(encoding="utf-8")
    assignment = read_split(text, "seed", manifest.splits)
    assert assignment.train == (0,)  # seed 100
    assert assignment.valid == (1,)  # seed 101
    assert assignment.test == (2,)  # seed 102
    assert assignment.labels == ("train", "valid", "test")
    assert assignment.dates == ("100", "101", "102")


def test_seed_crosscheck_refuses_mislabeled_world() -> None:
    """A world file whose scenario seed disagrees with population.toml is a refusal."""
    tampered = dict(RAW)
    tampered["meadow_s101.toml"] = tampered["meadow_s101.toml"].replace(b"seed = 101", b"seed = 999")
    import pytest

    from specimen.recipes.sanctuary_worlds import run

    with pytest.raises(ValueError, match="seed_crosscheck"):
        run(0, tampered)


def test_registry_declares_what_the_manifest_records() -> None:
    spec = REGISTRY["sanctuary_worlds"]
    assert spec.module == "specimen.recipes.sanctuary_worlds"
    assert len(spec.inputs) == 4  # population.toml + 3 world scenarios
    assert spec.steps == (
        "parse_population",
        "parse_worlds",
        "seed_crosscheck",
        "count_crosscheck",
        "sort_by_seed",
    )
    assert len(spec.source_sha256) == 64
