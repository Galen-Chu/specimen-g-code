"""unbodysoma_signals: the endogenous specimen - integer-ordered time, golden pin."""

from __future__ import annotations

import csv
import io
from pathlib import Path

from specimen import load_raw, parse_manifest, prepare, verify
from specimen.recipes import REGISTRY

FIXTURES = Path(__file__).parent / "fixtures" / "unbodysoma_run"
GOLDEN = Path(__file__).parent / "golden" / "unbodysoma-fear-s0"
RAW = load_raw(FIXTURES, REGISTRY["unbodysoma_signals"].inputs)


def test_unbodysoma_signals_seals_and_passes_all_four_checks(tmp_path: Path) -> None:
    directory = tmp_path / "unbodysoma-fear-s0"
    prepare("unbodysoma_signals", 0, RAW, directory)
    ok, report = verify(directory, RAW)
    assert ok, report


def test_golden_is_byte_identical(tmp_path: Path) -> None:
    """The committed golden pins: the fear run's signals.csv + meta.json, recipe, seal."""
    directory = tmp_path / "s"
    prepare("unbodysoma_signals", 0, RAW, directory)
    for filename in ("manifest.toml", "signals.csv"):
        assert (directory / filename).read_bytes() == (GOLDEN / filename).read_bytes(), filename


def test_signals_table_follows_the_declared_rules() -> None:
    text = (GOLDEN / "signals.csv").read_text(encoding="utf-8")
    rows = list(csv.DictReader(io.StringIO(text)))
    assert rows, "the specimen must carry the run's rows"
    times = [int(row["time"]) for row in rows]
    assert times == sorted(times)
    assert len(times) == len(set(times))  # unique timestamps after normalisation
    assert times[0] >= 1  # the blank t=0 row was dropped, not zero-filled
    # run_identity: every row carries the scenario and generator version
    assert {row["scenario"] for row in rows} == {"fear_response"}
    assert {row["generator_version"] for row in rows} == {"0.3.0"}


def test_integer_ordered_split_reads_time() -> None:
    """ADR-0001 (as amended): the split reads the int 'time' key."""
    manifest = parse_manifest((GOLDEN / "manifest.toml").read_text(encoding="utf-8"))
    assert manifest.splits.method == "integer-ordered"
    text = (GOLDEN / "signals.csv").read_text(encoding="utf-8")
    from specimen import read_split

    assignment = read_split(text, "time", manifest.splits)
    labels = [assignment.labels[i] for i in sorted(range(len(assignment.labels)))]
    assert labels.count("train") > 0 and labels.count("valid") > 0 and labels.count("test") > 0


def test_registry_declares_what_the_manifest_records() -> None:
    spec = REGISTRY["unbodysoma_signals"]
    assert spec.module == "specimen.recipes.unbodysoma_signals"
    assert spec.inputs == ("signals.csv", "meta.json")
    assert "time_seconds" in spec.steps and "drop_incomplete" in spec.steps
    assert len(spec.source_sha256) == 64
