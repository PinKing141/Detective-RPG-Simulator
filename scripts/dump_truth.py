from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from noir import config
from noir.cases.truth_generator import generate_case
from noir.truth.exporters import dump_truth
from noir.util.rng import Rng


def main() -> None:
    parser = argparse.ArgumentParser(description="Dump Truth for a seeded case.")
    parser.add_argument("--seed", type=int, default=config.SEED)
    parser.add_argument("--case-id", type=str, default=None)
    parser.add_argument("--out", type=str, default=None)
    args = parser.parse_args()

    rng = Rng(args.seed)
    truth, _ = generate_case(rng, case_id=args.case_id)
    output = dump_truth(truth)

    if args.out:
        with open(args.out, "w", encoding="ascii") as handle:
            handle.write(output)
        print(f"Wrote truth dump to {args.out}")
        return

    print(output)


if __name__ == "__main__":
    main()
