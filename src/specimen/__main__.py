"""CLI: specimen prepare / verify / catalog (docs/DESIGN.md §2)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .catalog import catalog, load_raw, prepare, verify
from .recipes import REGISTRY


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="specimen",
        description="Deterministic specimen preparation: raw data in, a sealed, reproducible data bundle out",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    prep = commands.add_parser("prepare", help="run a registered recipe and seal a specimen")
    prep.add_argument("recipe", choices=sorted(REGISTRY))
    prep.add_argument("--seed", type=int, default=0)
    prep.add_argument("--raw", type=Path, required=True, help="directory holding the recipe's raw inputs")
    prep.add_argument("--out", type=Path, required=True, help="specimen directory to seal")

    check = commands.add_parser("verify", help="check a sealed specimen (integrity, contracts, I4 with --raw)")
    check.add_argument("specimen", type=Path)
    check.add_argument("--raw", type=Path, help="directory holding the raw inputs, to also verify bit-reproducibility")

    listing = commands.add_parser("catalog", help="list sealed specimens under a root directory")
    listing.add_argument("root", type=Path)

    run = commands.add_parser("assay", help="run the baseline model comparison on a sealed specimen (needs [ml])")
    run.add_argument("specimen", type=Path)
    run.add_argument("--table", required=True, help="output table to assay")
    run.add_argument("--target", required=True, help="binary (0/1) target column")
    run.add_argument("--features", required=True, help="comma-separated numeric feature columns")
    run.add_argument("--seed", type=int, default=0)

    args = parser.parse_args(argv)
    if args.command == "prepare":
        spec = REGISTRY[args.recipe]
        manifest = prepare(args.recipe, args.seed, load_raw(args.raw, spec.inputs), args.out)
        print(f"sealed {args.out}  ({manifest.name} v{manifest.version}, {len(manifest.outputs)} outputs)")
        return 0
    if args.command == "verify":
        ok, report = verify(args.specimen, args.raw)
        for line in report:
            print(line)
        print("verify: PASS" if ok else "verify: FAIL")
        return 0 if ok else 1
    if args.command == "assay":
        from .assay import run_assay  # the [ml] blade - imported only on demand

        try:
            records = run_assay(args.specimen, args.table, args.target, tuple(args.features.split(",")), seed=args.seed)
        except ValueError as error:
            print(f"assay: refused ({error})")
            return 2
        for record in records:
            metrics = "  ".join(f"{key}={value:.4f}" for key, value in record.metrics)
            print(f"{record.model:14} {metrics}")
        print(f"assay: {len(records)} records appended to the manifest (append-only)")
        return 0
    for entry in catalog(args.root):
        if "error" in entry:
            print(f"{str(entry['name']):24} {entry['error']}")
            continue
        print(f"{entry['name']:24} v{entry['version']}  seed {entry['seed']}  outputs: {', '.join(entry['outputs'])}")  # type: ignore[arg-type]
    return 0


if __name__ == "__main__":
    sys.exit(main())
