"""Command line: python -m tl_simulator generate --seed 42 --nights 20"""

import argparse
import shutil
from pathlib import Path

from tl_simulator.campaign import generate_campaign

DEFAULT_OUT = Path("data/synthetic/generated")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tl_simulator", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate", help="generate a campaign of nightly runs")
    generate.add_argument("--seed", type=int, default=42)
    generate.add_argument("--nights", type=int, default=20)
    generate.add_argument("--out", type=Path, default=DEFAULT_OUT)
    generate.add_argument(
        "--force", action="store_true", help="delete the output folder first if it is not empty"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    out: Path = args.out
    if args.nights < 1:
        print("--nights must be at least 1")
        return 2
    if out.exists() and any(out.iterdir()):
        if not args.force:
            print(f"{out} is not empty. Use --force to replace it.")
            return 1
        shutil.rmtree(out)
    generate_campaign(out, args.seed, args.nights)
    print(f"Generated {args.nights} nights into {out} (seed {args.seed})")
    return 0
