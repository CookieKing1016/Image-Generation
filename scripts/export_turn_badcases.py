"""Export per-turn benchmark evaluation rows from SQLite."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any, Dict, Iterable, List

ROOT = Path(__file__).resolve().parents[1]

import sys

sys.path.insert(0, str(ROOT))

from core import database
from core.metrics import list_benchmark_run_ids, list_turn_badcase_matrix


DEFAULT_REPORT_DIR = ROOT / "outputs" / "reports"


def main() -> None:
    parser = argparse.ArgumentParser(description="Export per-turn badcase matrix.")
    parser.add_argument("--benchmark-run-id", default="", help="Benchmark run id. Defaults to the latest id in SQLite.")
    parser.add_argument("--db", type=Path, default=database.DEFAULT_DB_PATH)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_REPORT_DIR)
    args = parser.parse_args()

    benchmark_run_id = args.benchmark_run_id or _latest_benchmark_run_id(args.db)
    rows = list_turn_badcase_matrix(db_path=args.db, benchmark_run_id=benchmark_run_id)
    if not rows:
        raise SystemExit(f"No turn rows found for benchmark_run_id={benchmark_run_id!r}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stem = benchmark_run_id or "all_runs"
    csv_path = args.out_dir / f"{stem}_turn_badcases.csv"
    md_path = args.out_dir / f"{stem}_turn_badcases.md"

    _write_csv(csv_path, rows)
    _write_markdown(md_path, benchmark_run_id, rows)
    print(f"wrote {csv_path.relative_to(ROOT)}")
    print(f"wrote {md_path.relative_to(ROOT)}")


def _latest_benchmark_run_id(db_path: Path) -> str:
    run_ids = list_benchmark_run_ids(db_path=db_path)
    if not run_ids:
        raise SystemExit("No benchmark_run_id found in SQLite.")
    return run_ids[0]


def _write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    fieldnames = [
        "method",
        "case_id",
        "turn_index",
        "status",
        "checklist_score",
        "failed_item_count",
        "critical_failed_count",
        "history_retention",
        "current_success",
        "failed_items",
        "failed_reasons",
        "instruction",
        "image_path",
    ]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows({key: row.get(key, "") for key in fieldnames} for row in rows)


def _write_markdown(path: Path, benchmark_run_id: str, rows: List[Dict[str, Any]]) -> None:
    bad_rows = [row for row in rows if row.get("status") == "BAD"]
    lines = [
        f"# Per-turn Evaluation Matrix: {benchmark_run_id or 'all runs'}",
        "",
        f"- Total turns: {len(rows)}",
        f"- Bad turns: {len(bad_rows)}",
        "",
        "## Badcase Index",
        "",
    ]
    if bad_rows:
        lines.extend(_markdown_table(bad_rows, include_reasons=True))
    else:
        lines.append("No failed checklist items.")
    lines.extend(
        [
            "",
            "## All Turns",
            "",
        ]
    )
    lines.extend(_markdown_table(rows, include_reasons=False))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _markdown_table(rows: Iterable[Dict[str, Any]], include_reasons: bool) -> List[str]:
    columns = [
        "method",
        "case_id",
        "turn_index",
        "status",
        "checklist_score",
        "history_retention",
        "current_success",
        "failed_items",
    ]
    if include_reasons:
        columns.append("failed_reasons")
    columns.append("instruction")

    result = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for row in rows:
        result.append("| " + " | ".join(_cell(row.get(column, "")) for column in columns) + " |")
    return result


def _cell(value: Any) -> str:
    text = str(value).replace("\n", " ").replace("|", "/")
    return text if text else "-"


if __name__ == "__main__":
    main()
