from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from noir import config
from noir.ui.app import Phase05App


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 0.5 Textual wrapper.")
    parser.add_argument("--seed", type=int, default=config.SEED)
    parser.add_argument("--case-id", type=str, default=None)
    args = parser.parse_args()

    app = Phase05App(seed=args.seed, case_id=args.case_id)
    app.run()


if __name__ == "__main__":
    main()
