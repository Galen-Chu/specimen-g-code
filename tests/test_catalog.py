"""Catalog acceptance: seal, verify, tamper detection, I4 bit-reproducibility."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from specimen import catalog, load_raw, prepare, verify
from specimen.catalog import _count_rows
from specimen.manifest import parse_manifest, write_manifest
from specimen.recipes import REGISTRY

FIXTURES = Path(__file__).parent / "fixtures"
RAW = load_raw(FIXTURES, REGISTRY["demo_vitals"].inputs)


def seal(tmp_path: Path, name: str = "demo") -> Path:
    directory = tmp_path / name
    prepare("demo_vitals", 7, RAW, directory)
    return directory


def test_prepare_seals_a_complete_specimen(tmp_path: Path) -> None:
    directory = seal(tmp_path)
    assert (directory / "manifest.toml").exists()
    assert (directory / "daily.csv").exists()
    assert (directory / "quarterly.csv").exists()


def test_verify_passes_all_four_checks(tmp_path: Path) -> None:
    ok, report = verify(seal(tmp_path), RAW)
    assert ok, report
    assert "manifest: ok" in report
    assert "integrity: ok" in report
    assert "contract: ok" in report
    assert "reproduce: ok (byte-identical)" in report


def test_prepare_is_bit_reproducible(tmp_path: Path) -> None:
    """I4: same raw + seed -> byte-identical specimen, manifest included."""
    a, b = seal(tmp_path, "a"), seal(tmp_path, "b")
    for filename in ("manifest.toml", "daily.csv", "quarterly.csv"):
        assert (a / filename).read_bytes() == (b / filename).read_bytes()


def test_tampered_output_fails_integrity(tmp_path: Path) -> None:
    directory = seal(tmp_path)
    (directory / "daily.csv").write_text(
        (directory / "daily.csv").read_text(encoding="utf-8").replace("101.5", "999.9"), encoding="utf-8"
    )
    ok, report = verify(directory, RAW)
    assert not ok
    assert any("daily.csv hash mismatch" in line for line in report)


def test_changed_raw_is_diagnosed_by_input_hash(tmp_path: Path) -> None:
    """Different raw bytes are caught by the sealed input hash, before any rerun."""
    directory = seal(tmp_path)
    different_raw = {"vitals_raw.csv": RAW["vitals_raw.csv"].replace(b"101.5", b"110.5")}
    ok, report = verify(directory, different_raw)
    assert not ok
    assert any("input vitals_raw.csv does not match the sealed sha256" in line for line in report)


def test_recipe_code_drift_is_flagged(tmp_path: Path) -> None:
    """A manifest sealed by different recipe code is refused, with the reason named."""
    directory = seal(tmp_path)
    manifest = parse_manifest((directory / "manifest.toml").read_text(encoding="utf-8"))
    drifted = replace(manifest, recipe_source_sha256="d" * 64)
    write_manifest(drifted, directory / "manifest.toml")
    ok, report = verify(directory, RAW)
    assert not ok
    assert any("recipe code changed since sealing" in line for line in report)


def test_recorded_steps_mismatch_is_flagged(tmp_path: Path) -> None:
    directory = seal(tmp_path)
    manifest = parse_manifest((directory / "manifest.toml").read_text(encoding="utf-8"))
    edited = replace(manifest, recipe_steps=("normalize_dates",))
    write_manifest(edited, directory / "manifest.toml")
    ok, report = verify(directory, RAW)
    assert not ok
    assert any("recipe steps differ" in line for line in report)


def test_missing_output_is_reported(tmp_path: Path) -> None:
    directory = seal(tmp_path)
    (directory / "daily.csv").unlink()
    ok, report = verify(directory, RAW)
    assert not ok
    assert any("daily.csv missing" in line for line in report)


def test_unreadable_manifest_is_reported(tmp_path: Path) -> None:
    directory = tmp_path / "broken"
    directory.mkdir()
    (directory / "manifest.toml").write_text("not = [valid", encoding="utf-8")
    ok, report = verify(directory)
    assert not ok
    assert any("manifest: unreadable" in line for line in report)


def test_catalog_reports_bad_specimens_without_crashing(tmp_path: Path) -> None:
    seal(tmp_path, "good")
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "manifest.toml").write_text("]}not toml", encoding="utf-8")
    entries = catalog(tmp_path)
    bad_entry = next(e for e in entries if e["dir"] == "bad")
    assert "unreadable manifest" in str(bad_entry["error"])
    good_entry = next(e for e in entries if e["dir"] == "good")
    assert good_entry["outputs"] == ["daily", "quarterly"]


def test_count_rows_ignores_quoted_newlines() -> None:
    assert _count_rows('a,b\n1,"x\ny"\n2,z\n') == 2  # newline inside a quoted field is not a row
    assert _count_rows('a,b\n1,"x\ny"\n') == 1
    assert _count_rows("a,b\n") == 0
    assert _count_rows("") == 0


def test_catalog_lists_sealed_specimens(tmp_path: Path) -> None:
    seal(tmp_path, "one")
    prepare("demo_vitals", 8, RAW, tmp_path / "two")
    entries = catalog(tmp_path)
    assert [e["seed"] for e in entries] == [7, 8]
    assert all(e["outputs"] == ["daily", "quarterly"] for e in entries)


def test_golden_specimen_is_byte_identical(tmp_path: Path) -> None:
    """The committed golden specimen pins the whole chain: fixture, recipe, seal."""
    golden = Path(__file__).parent / "golden" / "demo-vitals-s7"
    fresh = seal(tmp_path)
    for filename in ("manifest.toml", "daily.csv", "quarterly.csv"):
        assert (fresh / filename).read_bytes() == (golden / filename).read_bytes(), filename


def test_unknown_recipe_key_is_clear(tmp_path: Path) -> None:
    with pytest.raises(KeyError):
        prepare("nonexistent", 0, RAW, tmp_path / "x")
