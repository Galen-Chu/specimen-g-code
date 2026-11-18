"""Assay protocol: gates at the door, baselines on the sealed splits, append-only records."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

pytest.importorskip("sklearn", reason="the assay blade needs the [ml] extra")

from specimen import Input, Output, parse_manifest, verify, write_manifest
from specimen.assay import run_assay
from specimen.hashing import sha256_bytes
from specimen.manifest import ColumnSpec, Manifest, Splits, TableContract

GOLDEN = Path(__file__).parent / "golden" / "demo-vitals-s7"
TRAIN_END, VALID_END = "2026-01-20", "2026-01-30"

CONTRACT = TableContract(
    name="daily",
    grain="daily",
    key=("date", "symbol"),
    columns=(
        ColumnSpec("close", "float", availability_lag_days=0.0),
        ColumnSpec("date", "date"),
        ColumnSpec("label", "int"),
        ColumnSpec("symbol", "string"),
        ColumnSpec("volume", "int", availability_lag_days=0.0),
    ),
)
FEATURES = ("close", "volume")


def build_specimen(directory: Path, rows: int = 36) -> Path:
    """A synthetic sealed specimen: one table, declared availability, binary target."""
    lines = ["date,symbol,close,volume,label"]
    day = date(2026, 1, 1)
    for i in range(rows):
        close = 100.0 + (i % 7) * 2.5  # cycles so both classes appear in every segment
        label = 1 if close > 104.0 else 0
        lines.append(f"{day + timedelta(days=i)},TEST,{close},{1000 + i * 13},{label}")
    text = "\n".join(lines) + "\n"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "daily.csv").write_text(text, encoding="utf-8", newline="\n")
    manifest = Manifest(
        name="assay-demo",
        version=1,
        seed=0,
        recipe_module="specimen.recipes.demo_vitals",
        recipe_steps=("synthetic",),
        recipe_source_sha256="a" * 64,
        inputs=(Input(path="raw.csv", sha256="b" * 64),),
        outputs=(Output(name="daily", grain="daily", file="daily.csv", sha256=sha256_bytes(text.encode()), rows=rows),),
        contracts=(CONTRACT,),
        splits=Splits(method="time-ordered", train_end=TRAIN_END, valid_end=VALID_END),
    )
    write_manifest(manifest, directory / "manifest.toml")
    return directory


def test_assay_appends_records_and_keeps_the_specimen_verifiable(tmp_path: Path) -> None:
    directory = build_specimen(tmp_path / "s")
    records = run_assay(directory, "daily", "label", FEATURES, seed=7)
    assert [r.model for r in records] == ["constant", "logistic", "decision_tree", "knn"]
    assert all(r.protocol == "time-split-baseline" and r.train_end == TRAIN_END for r in records)
    assert all(0.0 <= value <= 1.0 for r in records for _, value in r.metrics)
    on_disk = parse_manifest((directory / "manifest.toml").read_text(encoding="utf-8"))
    assert on_disk.assays == tuple(records)
    ok, report = verify(directory)
    assert ok, report


def test_assay_records_are_append_only(tmp_path: Path) -> None:
    directory = build_specimen(tmp_path / "s")
    first = run_assay(directory, "daily", "label", FEATURES, seed=7)
    second = run_assay(directory, "daily", "label", FEATURES, seed=7)
    on_disk = parse_manifest((directory / "manifest.toml").read_text(encoding="utf-8"))
    assert on_disk.assays[:4] == tuple(first)
    assert on_disk.assays[4:] == tuple(second)
    assert len(on_disk.assays) == 8


def test_assay_is_deterministic_within_an_environment(tmp_path: Path) -> None:
    a = run_assay(build_specimen(tmp_path / "a"), "daily", "label", FEATURES, seed=7)
    b = run_assay(build_specimen(tmp_path / "b"), "daily", "label", FEATURES, seed=7)
    assert a == b


def test_assay_refuses_undeclared_availability_on_the_golden_specimen() -> None:
    with pytest.raises(ValueError, match="undeclared"):
        run_assay(GOLDEN, "daily", "close", ("date", "symbol", "volume"))


def test_assay_refuses_the_target_among_features(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must not appear among the features"):
        run_assay(build_specimen(tmp_path / "s"), "daily", "label", ("close", "volume", "label"))


def test_assay_refuses_unknown_tables_and_non_numeric_features(tmp_path: Path) -> None:
    directory = build_specimen(tmp_path / "s")
    with pytest.raises(ValueError, match="not declared in the manifest"):
        run_assay(directory, "quarterly", "label", FEATURES)
    with pytest.raises(ValueError, match="numeric"):
        run_assay(directory, "daily", "label", ("close", "symbol"))


def test_assay_refuses_non_binary_targets(tmp_path: Path) -> None:
    directory = build_specimen(tmp_path / "s")
    text = (directory / "daily.csv").read_text(encoding="utf-8").replace(",1\n", ",2\n")
    (directory / "daily.csv").write_text(text, encoding="utf-8", newline="\n")
    manifest = parse_manifest((directory / "manifest.toml").read_text(encoding="utf-8"))
    output = manifest.outputs[0]
    from dataclasses import replace as _replace

    sealed = _replace(manifest, outputs=(_replace(output, sha256=sha256_bytes(text.encode("utf-8"))),))
    write_manifest(sealed, directory / "manifest.toml")
    with pytest.raises(ValueError, match="binary"):
        run_assay(directory, "daily", "label", FEATURES)


def test_assay_refuses_to_train_on_a_tampered_table(tmp_path: Path) -> None:
    directory = build_specimen(tmp_path / "s")
    text = (directory / "daily.csv").read_text(encoding="utf-8").replace("1000,", "9990,")
    (directory / "daily.csv").write_text(text, encoding="utf-8", newline="\n")
    with pytest.raises(ValueError, match="hash mismatch"):
        run_assay(directory, "daily", "label", FEATURES)


def test_assay_refuses_unknown_protocols(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="protocol"):
        run_assay(build_specimen(tmp_path / "s"), "daily", "label", FEATURES, protocol="random-split")


def test_assay_refuses_a_manifest_with_drifted_grains(tmp_path: Path) -> None:
    directory = build_specimen(tmp_path / "s")
    manifest = parse_manifest((directory / "manifest.toml").read_text(encoding="utf-8"))
    from dataclasses import replace as _replace

    drifted = _replace(manifest, contracts=(_replace(manifest.contracts[0], grain="weekly"),))
    write_manifest(drifted, directory / "manifest.toml")
    with pytest.raises(ValueError, match="grain"):
        run_assay(directory, "daily", "label", FEATURES)
