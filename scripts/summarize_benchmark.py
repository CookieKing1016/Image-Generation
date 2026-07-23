"""Print benchmark metric summaries from SQLite."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core import database
from core.metrics import summarize_drift_types, summarize_methods
from core.schema import json_dumps


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize Mem2Image benchmark metrics.")
    parser.add_argument("--db", type=Path, default=database.DEFAULT_DB_PATH)
    parser.add_argument("--benchmark-run-id", default="")
    args = parser.parse_args()

    print(
        json_dumps(
            {
                "method_summary": summarize_methods(args.db, args.benchmark_run_id),
                "drift_type_summary": summarize_drift_types(args.db, args.benchmark_run_id),
            }
        )
    )


if __name__ == "__main__":
    main()
