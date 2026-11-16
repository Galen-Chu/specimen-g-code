"""Recipe registry: a recipe is a named, pure transform over raw bytes.

``run(seed, inputs) -> outputs`` — same inputs and seed, byte-identical
outputs, no clock, no randomness other than the seed. The registry binds
each recipe name to its steps, required inputs, contracts and default
splits, which is everything ``prepare`` needs to seal a reproducible
specimen (docs/DESIGN.md §2).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from ..manifest import Splits, TableContract

RecipeFn = Callable[[int, Mapping[str, bytes]], Mapping[str, str]]


@dataclass(frozen=True)
class RecipeSpec:
    name: str
    module: str
    steps: tuple[str, ...]
    inputs: tuple[str, ...]
    contracts: tuple[TableContract, ...]
    splits: Splits
    run: RecipeFn


from . import demo_vitals  # noqa: E402 - registry assembled after the spec type

REGISTRY: dict[str, RecipeSpec] = {
    "demo_vitals": RecipeSpec(
        name="demo_vitals",
        module="specimen.recipes.demo_vitals",
        steps=demo_vitals.STEPS,
        inputs=demo_vitals.INPUTS,
        contracts=demo_vitals.CONTRACTS,
        splits=demo_vitals.SPLITS,
        run=demo_vitals.run,
    ),
}
