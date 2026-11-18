"""stock_1101: the first real specimen - declared rules, sealed splits, golden pin."""

from __future__ import annotations

import csv
import io
import json
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
    """The committed golden specimen pins the whole chain: raw months + quarterly raw, recipe, seal."""
    directory = tmp_path / "s"
    prepare("stock_1101", 0, RAW, directory)
    for filename in ("manifest.toml", "daily.csv", "quarterly.csv"):
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
    assert len(spec.inputs) == 36  # 34 monthly + 2 quarterly statement files
    assert spec.steps[-3:] == ("parse_quarterly_statements", "harmonize_to_twd_thousands", "sort_quarterly_by_key")
    assert len(spec.source_sha256) == 64


def test_quarterly_table_harmonizes_and_drops_uncovered_quarters() -> None:
    """Per-quarter TWD thousands; quarters without the full statement set (2025Q1/Q2) are dropped."""
    text = (GOLDEN / "quarterly.csv").read_text(encoding="utf-8")
    rows = list(csv.DictReader(io.StringIO(text)))
    assert [r["date"] for r in rows] == ["2025-09-30", "2025-12-31", "2026-03-31", "2026-06-30", "2026-09-30"]
    latest = rows[-1]
    assert latest["revenue"] == "41232918"  # 41,232,918,000 TWD / 1000
    assert latest["total_assets"] == "602031626"
    assert rows[0]["net_income"] == "-10200124"  # negative quarters are kept, not filled


def test_quarterly_backfill_cross_validates_against_the_official_snapshot() -> None:
    """The overlap quarter proves the unit harmonization: yf per-quarter sum == official YTD."""
    quarterly = list(csv.DictReader(io.StringIO((GOLDEN / "quarterly.csv").read_text(encoding="utf-8"))))
    official = json.loads((FIXTURES / "quarterly" / "t187ap06_L_ci_115Q3.json").read_bytes())
    income = next(r for r in official if r["公司代號"] == "1101")
    ytd_2026 = sum(int(r["revenue"]) for r in quarterly if r["date"] >= "2026-01-01")
    assert ytd_2026 == int(float(income["營業收入"]))  # both in TWD thousands - exact
    balance = json.loads((FIXTURES / "quarterly" / "t187ap07_L_ci_115Q3.json").read_bytes())
    assets = next(r for r in balance if r["公司代號"] == "1101")
    assert int(quarterly[-1]["total_assets"]) == int(float(assets["資產總計"]))  # exact
