from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from noir import config
from noir.cases.archetypes import CaseArchetype
from noir.narrative.gaze import GazeMode
from noir.ui.app import Phase05App


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 0.5 Textual wrapper.")
    parser.add_argument("--seed", type=int, default=config.SEED)
    parser.add_argument("--case-id", type=str, default=None)
    parser.add_argument(
        "--case-archetype",
        type=str,
        choices=[c.value for c in CaseArchetype],
        default=None,
        help="Force a case archetype (e.g., pattern or character).",
    )
    parser.add_argument(
        "--gaze",
        type=str,
        choices=[g.value for g in GazeMode],
        default=GazeMode.FORENSIC.value,
        help="Presentation lens (forensic or behavioral).",
    )
    parser.add_argument(
        "--world-db",
        type=str,
        default=str(ROOT / "data" / "world_state.db"),
        help="SQLite database path for world state.",
    )
    parser.add_argument(
        "--no-world-db",
        action="store_true",
        help="Run without persisting world state.",
    )
    parser.add_argument(
        "--reset-world",
        action="store_true",
        help="Reset stored world state before starting.",
    )
    args = parser.parse_args()

    world_db = None if args.no_world_db else Path(args.world_db)
    case_archetype = CaseArchetype(args.case_archetype) if args.case_archetype else None
    gaze_mode = GazeMode(args.gaze)
    app = Phase05App(
        seed=args.seed,
        case_id=args.case_id,
        world_db=world_db,
        case_archetype=case_archetype,
        gaze_mode=gaze_mode,
        reset_world=args.reset_world,
    )
    app.run()


if __name__ == "__main__":
    main()
