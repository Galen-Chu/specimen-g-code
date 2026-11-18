"""stock_1101: the first real specimen - declared rules, sealed splits, golden pin."""

from __future__ import annotations

import csv
import io
from pathlib import Path

from specimen import load_raw, parse_manifest, prepare, read_split, verify
from specimen.recipes import REGISTRY

FIXTURES = Path(__file__).parent / "fixtures" / "stock_1101"
GOLDEN = Path(__file__).parent / "golden" / "stock-1101-s0"
RAW = load_raw(FIXTURES, REGISTRY["stock_1101"].inputs)


def test_stock_1101_seals_and_passes_all_four_checks(tmp_path: Path) -> None:
    directory = tmp_path / "stock-1101-s0"
    prepare("stock_1101", 0, RAW, directory)
    ok, report = verify(directory, RAW)
    assert ok, report


def test_stock_1101_golden_is_byte_identical(tmp_path: Path) -> None:
    """The committed golden specimen pins the whole chain: 34 raw months, recipe, seal."""
    directory = tmp_path / "s"
    prepare("stock_1101", 0, RAW, directory)
    for filename in ("manifest.toml", "daily.csv"):
        assert (directory / filename).read_bytes() == (GOLDEN / filename).read_bytes(), filename


def test_daily_table_follows_the_declared_rules() -> None:
    text = (GOLDEN / "daily.csv").read_text(encoding="utf-8")
    rows = list(csv.DictReader(io.StringIO(text)))
    dates = [row["date"] for row in rows]
    assert dates == sorted(dates)
    assert all(len(d) == 10 and d[4] == "-" and "--" not in d for d in dates)  # ROC dates normalized away
    assert all("," not in row["volume"] and "--" not in row["close"] for row in rows)  # thousands stripped
    assert {row["label"] for row in rows} == {"0", "1"}
    keys = [(row["date"], row["symbol"]) for row in rows]
    assert len(keys) == len(set(keys))


def test_segments_carry_both_classes_where_declared() -> None:
    """Train (through 2025-12-31) and test (the last fully-labelable window) both learn."""
    manifest = parse_manifest((GOLDEN / "manifest.toml").read_text(encoding="utf-8"))
    text = (GOLDEN / "daily.csv").read_text(encoding="utf-8")
    assignment = read_split(text, "date", manifest.splits)
    rows = list(csv.DictReader(io.StringIO(text)))
    for segment in ("train", "test"):
        labels = {rows[i]["label"] for i in getattr(assignment, segment)}
        assert labels == {"0", "1"}, segment


def test_registry_declares_what_the_manifest_records() -> None:
    spec = REGISTRY["stock_1101"]
    assert spec.module == "specimen.recipes.stock_1101"
    assert len(spec.inputs) == 34
    assert spec.steps[-1] == "label_forward_return_90d"
    assert len(spec.source_sha256) == 64
