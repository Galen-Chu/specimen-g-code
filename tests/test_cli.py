"""CLI acceptance: prepare / verify / catalog and exit codes."""

from __future__ import annotations

from pathlib import Path

from specimen import __version__
from specimen.__main__ import main

FIXTURES = Path(__file__).parent / "fixtures"


def test_prepare_and_verify_round_trip(tmp_path: Path) -> None:
    out = tmp_path / "specimens" / "demo-vitals-s7"
    assert main(["prepare", "demo_vitals", "--seed", "7", "--raw", str(FIXTURES), "--out", str(out)]) == 0
    assert main(["verify", str(out), "--raw", str(FIXTURES)]) == 0


def test_verify_fails_with_nonzero_exit_on_tamper(tmp_path: Path) -> None:
    out = tmp_path / "s"
    main(["prepare", "demo_vitals", "--seed", "7", "--raw", str(FIXTURES), "--out", str(out)])
    (out / "quarterly.csv").write_text("date,symbol,note\n2026-01-02,X,edited\n", encoding="utf-8")
    assert main(["verify", str(out), "--raw", str(FIXTURES)]) == 1


def test_catalog_lists_entries(tmp_path: Path) -> None:
    main(["prepare", "demo_vitals", "--seed", "7", "--raw", str(FIXTURES), "--out", str(tmp_path / "a")])
    assert main(["catalog", str(tmp_path)]) == 0


def test_version_is_exported() -> None:
    assert __version__ == "0.5.0"


def test_verify_missing_raw_file_fails_cleanly(tmp_path: Path) -> None:
    out = tmp_path / "s"
    main(["prepare", "demo_vitals", "--seed", "7", "--raw", str(FIXTURES), "--out", str(out)])
    assert main(["verify", str(out), "--raw", str(tmp_path / "empty")]) == 1
