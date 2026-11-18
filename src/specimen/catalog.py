"""Catalog: prepare (seal), load, verify and reproduce specimens.

A sealed specimen directory is

    <dir>/manifest.toml
    <dir>/<output file>...        (one per declared output)

``prepare`` runs a registered recipe over raw inputs, writes the outputs
(LF), computes their hashes and seals the manifest. ``verify`` checks a
directory four ways: manifest validity, output integrity (hashes), contract
conformance, and — when the raw inputs are supplied — bit-reproducibility
(invariant I4). Before attesting I4 it compares the sealed recipe's code
identity and input hashes, so drift is diagnosed precisely instead of
surfacing as an anonymous "differs". Nothing in this module consults the
clock or the platform.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from pathlib import Path

from .contract import validate_all
from .hashing import sha256_bytes
from .manifest import Input, Manifest, Output, parse_manifest, validate_manifest, write_manifest
from .recipes import REGISTRY


def load_raw(raw_dir: str | Path, filenames: tuple[str, ...]) -> dict[str, bytes]:
    raw = {}
    for name in filenames:
        raw[name] = (Path(raw_dir) / name).read_bytes()
    return raw


def _count_rows(text: str) -> int:
    """Data-row count of a CSV body (quoted embedded newlines do not count as rows)."""
    return max(sum(1 for _ in csv.reader(io.StringIO(text))) - 1, 0)


def prepare(recipe_name: str, seed: int, raw: Mapping[str, bytes], out: str | Path, version: int = 1) -> Manifest:
    """Run a recipe and seal a specimen directory (idempotent, deterministic)."""
    spec = REGISTRY[recipe_name]
    missing = [name for name in spec.inputs if name not in raw]
    if missing:
        raise KeyError(f"raw inputs missing: {missing}")
    outputs = dict(spec.run(seed, {k: raw[k] for k in spec.inputs}))

    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    sealed: list[Output] = []
    for name in sorted(outputs):
        filename = f"{name}.csv"
        (out_dir / filename).write_text(outputs[name], encoding="utf-8", newline="\n")
        sealed.append(
            Output(
                name=name,
                grain=next(c.grain for c in spec.contracts if c.name == name),
                file=filename,
                sha256=sha256_bytes(outputs[name].encode("utf-8")),
                rows=_count_rows(outputs[name]),
            )
        )
    manifest = Manifest(
        name=f"{recipe_name.replace('_', '-')}-s{seed}",
        version=version,
        seed=seed,
        recipe_module=spec.module,
        recipe_steps=spec.steps,
        recipe_source_sha256=spec.source_sha256,
        inputs=tuple(Input(path=name, sha256=sha256_bytes(raw[name])) for name in spec.inputs),
        outputs=tuple(sealed),
        contracts=spec.contracts,
        splits=spec.splits,
    )
    problems = validate_manifest(manifest)
    if problems:
        raise ValueError(f"refusing to seal an invalid manifest: {problems}")
    write_manifest(manifest, out_dir / "manifest.toml")
    return manifest


def load(specimen_dir: str | Path) -> Manifest:
    return parse_manifest((Path(specimen_dir) / "manifest.toml").read_text(encoding="utf-8"))


def verify(specimen_dir: str | Path, raw: Mapping[str, bytes] | str | Path | None = None) -> tuple[bool, list[str]]:
    """Check a specimen; returns (ok, report lines).

    ``raw`` supplies the original inputs for the I4 check — either the bytes
    themselves or a directory holding the manifest's declared input files.
    """
    directory = Path(specimen_dir)
    report: list[str] = []
    ok = True
    try:
        manifest = load(directory)
    except (OSError, KeyError, ValueError) as error:
        return False, [f"manifest: unreadable ({error})"]

    problems = validate_manifest(manifest)
    report += [f"manifest: {p}" for p in problems] or ["manifest: ok"]
    ok = ok and not problems

    integrity_ok = True
    for out in manifest.outputs:
        path = directory / out.file
        if not path.exists():
            report.append(f"integrity: {out.file} missing")
            integrity_ok = False
            continue
        digest = sha256_bytes(path.read_bytes())
        if digest != out.sha256:
            report.append(f"integrity: {out.file} hash mismatch (tampered or regenerated differently)")
            integrity_ok = False
    if integrity_ok:
        report.append("integrity: ok")
    ok = ok and integrity_ok

    tables = {
        out.name: (directory / out.file).read_text(encoding="utf-8")
        for out in manifest.outputs
        if (directory / out.file).exists()
    }
    contract_problems = validate_all(manifest.contracts, tables)
    report += [f"contract: {p}" for p in contract_problems] or ["contract: ok"]
    ok = ok and not contract_problems

    if raw is not None:
        raw_bytes: Mapping[str, bytes] | None
        if isinstance(raw, (str, Path)):
            try:
                raw_bytes = load_raw(raw, tuple(i.path for i in manifest.inputs))
            except OSError as error:
                raw_bytes = None
                report.append(f"reproduce: raw inputs unreadable ({error})")
                ok = False
        else:
            raw_bytes = raw
        if raw_bytes is not None:
            reproduce_problems = _reproduce(manifest, raw_bytes, directory)
            report += [f"reproduce: {p}" for p in reproduce_problems] or ["reproduce: ok (byte-identical)"]
            ok = ok and not reproduce_problems
    return ok, report


def _reproduce(manifest: Manifest, raw: Mapping[str, bytes], directory: Path) -> list[str]:
    """I4: rerun the recorded recipe and compare every output byte for byte.

    Identity first: the registered recipe's steps and source hash must match
    what was sealed, and every raw input must match its recorded hash. Only
    then is a fresh run meaningful — otherwise "differs" would misreport code
    or input drift as output tampering.
    """
    spec = next((s for s in REGISTRY.values() if s.module == manifest.recipe_module), None)
    if spec is None:
        return [f"recipe module {manifest.recipe_module!r} is not registered"]
    missing = [name for name in spec.inputs if name not in raw]
    if missing:
        return [f"raw inputs missing: {missing}"]

    problems: list[str] = []
    if spec.steps != manifest.recipe_steps:
        problems.append(f"recipe steps differ from the sealed record: {manifest.recipe_steps} vs {spec.steps}")
    if spec.source_sha256 != manifest.recipe_source_sha256:
        problems.append("recipe code changed since sealing (source sha256 mismatch); seal a new version")
    for inp in manifest.inputs:
        if sha256_bytes(raw[inp.path]) != inp.sha256:
            problems.append(f"input {inp.path} does not match the sealed sha256")
    if problems:
        return problems

    fresh = spec.run(manifest.seed, {k: raw[k] for k in spec.inputs})
    for out in manifest.outputs:
        path = directory / out.file
        if not path.exists():
            continue  # already reported by the integrity check
        if fresh.get(out.name) != path.read_text(encoding="utf-8"):
            problems.append(f"{out.file} differs from a fresh run")
    return problems


def catalog(root: str | Path) -> list[dict[str, object]]:
    """List sealed specimens under a root directory (name, version, outputs).

    An unreadable manifest yields an entry with an ``error`` key instead of
    crashing the listing — a bad specimen is evidence, not an exception.
    """
    entries: list[dict[str, object]] = []
    for manifest_path in sorted(Path(root).glob("*/manifest.toml")):
        try:
            manifest = parse_manifest(manifest_path.read_text(encoding="utf-8"))
        except (OSError, KeyError, ValueError) as error:
            entries.append(
                {
                    "name": manifest_path.parent.name,
                    "error": f"unreadable manifest ({error})",
                    "dir": manifest_path.parent.name,
                }
            )
            continue
        entries.append(
            {
                "name": manifest.name,
                "version": manifest.version,
                "seed": manifest.seed,
                "outputs": [o.name for o in manifest.outputs],
                "dir": manifest_path.parent.name,
            }
        )
    return entries
