"""The specimen manifest: identity, recipe, outputs, contracts, splits.

A specimen is an immutable directory whose truth is ``manifest.toml``. The
manifest records everything needed to reproduce the outputs: the recipe
module and steps, input hashes, output hashes, per-table contracts, and the
train/valid/test splits (splits belong to the specimen, so every assay on
it shares them — docs/DESIGN.md §2).

Determinism: serialization is field-ordered and float-free (hashes and
counts), writes are LF-only, and nothing in the default flow consults the
clock or the platform — ``prepare`` twice from the same inputs and seed
produces byte-identical manifests on any machine. The ``created`` and
``environment`` fields are opt-in annotations exactly because they would
break that property.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

GRAIN_PATTERN = r"[a-z][a-z0-9-]*"
TYPE_NAMES = frozenset({"string", "float", "int", "date"})


@dataclass(frozen=True)
class Input:
    path: str  # filename within the raw store
    sha256: str


@dataclass(frozen=True)
class ColumnSpec:
    name: str
    type: str  # string | float | int | date
    lo: float | None = None
    hi: float | None = None
    availability_lag_days: float | None = None  # I2: when the column becomes knowable


@dataclass(frozen=True)
class TableContract:
    name: str
    grain: str
    key: tuple[str, ...]
    columns: tuple[ColumnSpec, ...]

    def column(self, name: str) -> ColumnSpec | None:
        return next((c for c in self.columns if c.name == name), None)


@dataclass(frozen=True)
class Output:
    name: str
    grain: str
    file: str
    sha256: str
    rows: int


@dataclass(frozen=True)
class Splits:
    method: str  # Phase 1: "time-ordered"
    train_end: str  # inclusive boundary of the train segment (dates for now)
    valid_end: str


@dataclass(frozen=True)
class Manifest:
    name: str
    version: int
    seed: int
    recipe_module: str
    recipe_steps: tuple[str, ...]
    inputs: tuple[Input, ...]
    outputs: tuple[Output, ...]
    contracts: tuple[TableContract, ...]
    splits: Splits
    created: str | None = None  # opt-in annotation; never consulted for reproduction
    environment: tuple[tuple[str, str], ...] = ()  # opt-in, e.g. (("python", "3.13"),)

    @property
    def contract_of(self) -> dict[str, TableContract]:
        return {c.name: c for c in self.contracts}


def _q(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def render_manifest(m: Manifest) -> str:
    """Serialize deterministically to TOML text (LF, fixed field order)."""
    lines: list[str] = []
    if m.created is not None:
        lines.append(f"created = {_q(m.created)}")
    if m.environment:
        lines.append("[environment]")
        for k, v in m.environment:
            lines.append(f"{k} = {_q(v)}")
        lines.append("")
    lines += [
        "[specimen]",
        f"name = {_q(m.name)}",
        f"version = {m.version}",
        f"seed = {m.seed}",
        "",
        "[recipe]",
        f"module = {_q(m.recipe_module)}",
        "steps = [" + ", ".join(_q(s) for s in m.recipe_steps) + "]",
        "",
    ]
    for inp in m.inputs:
        lines += ["[[recipe.inputs]]", f"path = {_q(inp.path)}", f"sha256 = {_q(inp.sha256)}", ""]
    lines += [
        "[splits]",
        f"method = {_q(m.splits.method)}",
        f"train_end = {_q(m.splits.train_end)}",
        f"valid_end = {_q(m.splits.valid_end)}",
        "",
    ]
    for out in m.outputs:
        lines += [
            "[[outputs]]",
            f"name = {_q(out.name)}",
            f"grain = {_q(out.grain)}",
            f"file = {_q(out.file)}",
            f"sha256 = {_q(out.sha256)}",
            f"rows = {out.rows}",
            "",
        ]
    for contract in sorted(m.contracts, key=lambda c: c.name):
        lines += [
            f"[contracts.{contract.name}]",
            f"grain = {_q(contract.grain)}",
            "key = [" + ", ".join(_q(k) for k in contract.key) + "]",
        ]
        for column in sorted(contract.columns, key=lambda c: c.name):
            lines.append(f"[contracts.{contract.name}.columns.{column.name}]")
            lines.append(f"type = {_q(column.type)}")
            if column.lo is not None:
                lines.append(f"lo = {column.lo!r}")
            if column.hi is not None:
                lines.append(f"hi = {column.hi!r}")
            if column.availability_lag_days is not None:
                lines.append(f"availability_lag_days = {column.availability_lag_days!r}")
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def validate_manifest(m: Manifest) -> list[str]:
    """Completeness and structural validity (I1/I3 structure); empty list = valid."""
    problems: list[str] = []
    if not m.name or m.version < 1:
        problems.append("specimen: name must be non-empty and version >= 1")
    if not m.recipe_module or not m.recipe_steps:
        problems.append("recipe: module and steps are required")
    if not m.inputs:
        problems.append("recipe: at least one input with sha256 is required")
    if any(len(i.sha256) != 64 for i in m.inputs):
        problems.append("recipe: input sha256 must be 64 hex characters")
    if m.splits.method != "time-ordered":
        problems.append(f"splits: unsupported method {m.splits.method!r} (Phase 1: 'time-ordered')")
    output_names = {o.name for o in m.outputs}
    contract_names = {c.name for c in m.contracts}
    if output_names != contract_names:
        problems.append(f"outputs and contracts must match exactly: {sorted(output_names ^ contract_names)}")
    for out in m.outputs:
        if not out.grain or not out.file or len(out.sha256) != 64:
            problems.append(f"output {out.name!r}: grain, file and 64-char sha256 are required (I3)")
    for contract in m.contracts:
        if not contract.key:
            problems.append(f"contract {contract.name!r}: key is required (grain identity)")
        for column in contract.columns:
            if column.type not in TYPE_NAMES:
                problems.append(f"contract {contract.name}.{column.name}: unknown type {column.type!r}")
    return problems


def parse_manifest(text: str) -> Manifest:
    """Parse manifest TOML (the mirror of ``render_manifest``)."""
    data = tomllib.loads(text)
    specimen = data["specimen"]
    recipe = data["recipe"]
    splits = data["splits"]
    inputs = tuple(Input(path=i["path"], sha256=i["sha256"]) for i in recipe["inputs"])
    outputs = tuple(
        Output(name=o["name"], grain=o["grain"], file=o["file"], sha256=o["sha256"], rows=o["rows"])
        for o in data["outputs"]
    )
    contracts = tuple(
        TableContract(
            name=name,
            grain=c["grain"],
            key=tuple(c["key"]),
            columns=tuple(
                ColumnSpec(
                    name=cname,
                    type=cc["type"],
                    lo=cc.get("lo"),
                    hi=cc.get("hi"),
                    availability_lag_days=cc.get("availability_lag_days"),
                )
                for cname, cc in c["columns"].items()
            ),
        )
        for name, c in data["contracts"].items()
    )
    environment = tuple(sorted(data.get("environment", {}).items()))
    return Manifest(
        name=specimen["name"],
        version=specimen["version"],
        seed=specimen["seed"],
        recipe_module=recipe["module"],
        recipe_steps=tuple(recipe["steps"]),
        inputs=inputs,
        outputs=outputs,
        contracts=contracts,
        splits=Splits(method=splits["method"], train_end=splits["train_end"], valid_end=splits["valid_end"]),
        created=data.get("created"),
        environment=environment,
    )


def write_manifest(m: Manifest, path: str | Path) -> None:
    Path(path).write_text(render_manifest(m), encoding="utf-8", newline="\n")
