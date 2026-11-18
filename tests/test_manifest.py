"""Manifest: deterministic serialization, round trip, structural validation."""

from __future__ import annotations

from specimen.manifest import (
    ColumnSpec,
    Input,
    Manifest,
    Output,
    Splits,
    TableContract,
    parse_manifest,
    render_manifest,
    validate_manifest,
)


def demo_manifest() -> Manifest:
    contract = TableContract(
        name="daily",
        grain="daily",
        key=("date", "symbol"),
        columns=(
            ColumnSpec("close", "float", lo=0.0, hi=1000.0, availability_lag_days=90.0),
            ColumnSpec("date", "date"),
            ColumnSpec("symbol", "string"),
        ),
    )
    return Manifest(
        name="demo-s7",
        version=1,
        seed=7,
        recipe_module="specimen.recipes.demo_vitals",
        recipe_steps=("normalize_dates", "split_grains", "dedupe_keep_last", "sort_by_key"),
        recipe_source_sha256="c" * 64,
        inputs=(Input(path="vitals_raw.csv", sha256="a" * 64),),
        outputs=(Output(name="daily", grain="daily", file="daily.csv", sha256="b" * 64, rows=11),),
        contracts=(contract,),
        splits=Splits(method="time-ordered", train_end="2026-01-10", valid_end="2026-01-20"),
    )


def test_round_trip_is_lossless() -> None:
    text = render_manifest(demo_manifest())
    assert parse_manifest(text) == demo_manifest()


def test_rendering_is_deterministic() -> None:
    assert render_manifest(demo_manifest()) == render_manifest(demo_manifest())


def test_no_timestamp_or_platform_leaks_into_the_manifest() -> None:
    text = render_manifest(demo_manifest())
    assert "created" not in text and "environment" not in text and "\r" not in text


def test_sections_appear_in_fixed_order() -> None:
    text = render_manifest(demo_manifest())
    order = [
        text.index(s)
        for s in ("[specimen]", "[recipe]", "[[recipe.inputs]]", "[splits]", "[[outputs]]", "[contracts.daily]")
    ]
    assert order == sorted(order)


def test_validation_catches_structural_invariants() -> None:
    good = demo_manifest()
    assert validate_manifest(good) == []

    bad_split = Manifest(**{**demo_manifest().__dict__, "splits": Splits("random", "x", "y")})
    assert any("splits" in p for p in validate_manifest(bad_split))

    contractless = Manifest(**{**good.__dict__, "contracts": ()})
    assert any("outputs and contracts" in p for p in validate_manifest(contractless))

    bad_sha = Manifest(**{**good.__dict__, "outputs": (Output("daily", "daily", "daily.csv", "short", 11),)})
    assert any("sha256" in p for p in validate_manifest(bad_sha))

    bad_code = Manifest(**{**good.__dict__, "recipe_source_sha256": "short"})
    assert any("source_sha256" in p for p in validate_manifest(bad_code))
