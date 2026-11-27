"""Second domain: a sanctuary world group — the first atemporal specimen.

Raw inputs are one ``population.toml`` (the group provenance that
``sanctuary --seed M --preset P --count N`` writes) plus the N world
scenario TOMLs it lists. The recipe parses each world with ``tomllib`` and
emits one ``worlds`` table (grain ``world``, one row per world): the group
identity, each world's composition counts, and its geometry.

No time axis exists anywhere in this domain — the split is ``integer-ordered``
over the world seed (ADR-0001), I1/I3 degenerate to the seed order, and
every column is knowable with its own artifact (availability 0.0). Assay is
deferred until a learning question exists for worlds (ADR-0001
consequences); preparation, catalog and verify are the full acceptance for
now.

Declared rules (none implicit):

- count_crosscheck: ``population.toml``'s ``count`` must equal the number of
  ``[[worlds]]`` entries and the number of world files actually supplied.
- seed_crosscheck: each world file's ``[scenario].seed`` must equal the
  seed its ``[[worlds]]`` entry declares — a mislabeled world is a refusal.
- counts_from_scenario: entity counts come from parsing each world's own
  TOML sections, never from any description string.
- sort_by_seed: rows sorted by (population_seed, seed).
"""

from __future__ import annotations

import csv
import io
import tomllib
from collections.abc import Mapping

from ..manifest import ColumnSpec, Splits, TableContract

STEPS = ("parse_population", "parse_worlds", "seed_crosscheck", "count_crosscheck", "sort_by_seed")
INPUTS = (
    "population.toml",
    "meadow_s100.toml",
    "meadow_s101.toml",
    "meadow_s102.toml",
)
WORLDS_HEADER = (
    "population_seed",
    "seed",
    "world_name",
    "preset",
    "generator_version",
    "duration_h",
    "width",
    "height",
    "start_x",
    "start_y",
    "food_count",
    "water_count",
    "shelter_count",
    "hazard_count",
)
CONTRACTS = (
    # Atemporal: every column is knowable with the artifact itself (I2
    # availability 0.0); the split is integer-ordered (ADR-0001).
    TableContract(
        name="worlds",
        grain="world",
        key=("population_seed", "seed"),
        columns=(
            ColumnSpec("food_count", "int", lo=0.0, availability_lag_days=0.0),
            ColumnSpec("generator_version", "string", availability_lag_days=0.0),
            ColumnSpec("hazard_count", "int", lo=0.0, availability_lag_days=0.0),
            ColumnSpec("height", "float", lo=0.0, availability_lag_days=0.0),
            ColumnSpec("duration_h", "float", lo=0.0, availability_lag_days=0.0),
            ColumnSpec("population_seed", "int", lo=0.0, availability_lag_days=0.0),
            ColumnSpec("preset", "string", availability_lag_days=0.0),
            ColumnSpec("seed", "int", lo=0.0, availability_lag_days=0.0),
            ColumnSpec("shelter_count", "int", lo=0.0, availability_lag_days=0.0),
            ColumnSpec("start_x", "float", availability_lag_days=0.0),
            ColumnSpec("start_y", "float", availability_lag_days=0.0),
            ColumnSpec("water_count", "int", lo=0.0, availability_lag_days=0.0),
            ColumnSpec("width", "float", lo=0.0, availability_lag_days=0.0),
            ColumnSpec("world_name", "string", availability_lag_days=0.0),
        ),
    ),
)
SPLITS = Splits(method="integer-ordered", train_end="100", valid_end="101")


def _fmt(value: float) -> str:
    """Deterministic float formatting (the recipe idiom: int when integral)."""
    return str(int(value)) if value.is_integer() else repr(value)


def run(seed: int, inputs: Mapping[str, bytes]) -> dict[str, str]:
    population = tomllib.loads(inputs["population.toml"].decode("utf-8"))
    group = population["population"]
    master = int(group["seed"])
    declared_count = int(group["count"])
    entries = population["worlds"]  # count_crosscheck
    if len(entries) != declared_count:
        raise ValueError(
            f"count_crosscheck: population.toml declares count={declared_count}, got {len(entries)} worlds"
        )

    rows: list[dict[str, str]] = []
    for entry in entries:  # parse_worlds
        filename = entry["file"]
        world = tomllib.loads(inputs[filename].decode("utf-8"))
        scenario, grid = world["scenario"], world["world"]
        if int(scenario["seed"]) != int(entry["seed"]):  # seed_crosscheck
            raise ValueError(
                f"seed_crosscheck: {filename} declares seed {scenario['seed']} "
                f"but population.toml lists {entry['seed']}"
            )
        rows.append(
            {
                "population_seed": str(master),
                "seed": str(entry["seed"]),
                "world_name": str(entry["name"]),
                "preset": str(group["preset"]),
                "generator_version": str(group["version"]),
                "duration_h": _fmt(float(scenario["duration_h"])),
                "width": _fmt(float(grid["width"])),
                "height": _fmt(float(grid["height"])),
                "start_x": _fmt(float(grid["start"][0])),
                "start_y": _fmt(float(grid["start"][1])),
                "food_count": str(len(grid.get("food", []))),
                "water_count": str(len(grid.get("water", []))),
                "shelter_count": str(len(grid.get("shelters", []))),
                "hazard_count": str(len(grid.get("hazards", []))),
            }
        )

    rows.sort(key=lambda r: (r["population_seed"], r["seed"]))  # sort_by_seed
    return {"worlds": _to_csv(WORLDS_HEADER, rows)}


def _to_csv(header: tuple[str, ...], rows: list[dict[str, str]]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=header, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row[k] for k in header})
    return buffer.getvalue()
