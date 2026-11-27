"""Recipe registry: a recipe is a named, pure transform over raw bytes.

``run(seed, inputs) -> outputs`` — same inputs and seed, byte-identical
outputs, no clock, no randomness other than the seed. The registry binds
each recipe name to its steps, required inputs, contracts, default splits
and the source-file hash of its module — everything ``prepare`` needs to
seal a reproducible specimen (docs/DESIGN.md §2). The hash is the code
identity: ``verify`` compares it against the manifest to detect recipe
drift since sealing.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

from ..hashing import sha256_file
from ..manifest import Splits, TableContract

RecipeFn = Callable[[int, Mapping[str, bytes]], Mapping[str, str]]


def hash_module(module: ModuleType) -> str:
    """Hash a recipe module's source file — its code identity (stable: git enforces LF)."""
    file = module.__file__
    if file is None:
        raise ValueError(f"recipe module {module.__name__!r} has no source file to hash")
    return sha256_file(Path(file))


@dataclass(frozen=True)
class RecipeSpec:
    name: str
    module: str
    source_sha256: str
    steps: tuple[str, ...]
    inputs: tuple[str, ...]
    contracts: tuple[TableContract, ...]
    splits: Splits
    run: RecipeFn


from . import demo_vitals, sanctuary_worlds, stock_1101  # noqa: E402 - registry assembled after the spec type

REGISTRY: dict[str, RecipeSpec] = {
    "demo_vitals": RecipeSpec(
        name="demo_vitals",
        module="specimen.recipes.demo_vitals",
        source_sha256=hash_module(demo_vitals),
        steps=demo_vitals.STEPS,
        inputs=demo_vitals.INPUTS,
        contracts=demo_vitals.CONTRACTS,
        splits=demo_vitals.SPLITS,
        run=demo_vitals.run,
    ),
    "sanctuary_worlds": RecipeSpec(
        name="sanctuary_worlds",
        module="specimen.recipes.sanctuary_worlds",
        source_sha256=hash_module(sanctuary_worlds),
        steps=sanctuary_worlds.STEPS,
        inputs=sanctuary_worlds.INPUTS,
        contracts=sanctuary_worlds.CONTRACTS,
        splits=sanctuary_worlds.SPLITS,
        run=sanctuary_worlds.run,
    ),
    "stock_1101": RecipeSpec(
        name="stock_1101",
        module="specimen.recipes.stock_1101",
        source_sha256=hash_module(stock_1101),
        steps=stock_1101.STEPS,
        inputs=stock_1101.INPUTS,
        contracts=stock_1101.CONTRACTS,
        splits=stock_1101.SPLITS,
        run=stock_1101.run,
    ),
}
