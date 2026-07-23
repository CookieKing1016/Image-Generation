"""Import existing file-based run artifacts into SQLite.

Usage:
    python3 scripts/import_runs.py
    python3 scripts/import_runs.py --db outputs/mem2image.sqlite3
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core import database
from core.run_logger import ROOT, RUNS_ROOT


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Mem2Image run logs into SQLite.")
    parser.add_argument("--runs-root", type=Path, default=RUNS_ROOT)
    parser.add_argument("--db", type=Path, default=database.DEFAULT_DB_PATH)
    args = parser.parse_args()

    imported_turns = import_runs(args.runs_root, args.db)
    print(f"Imported {imported_turns} turn(s) into {args.db}")


def import_runs(runs_root: Path = RUNS_ROOT, db_path: Path = database.DEFAULT_DB_PATH) -> int:
    database.init_db(db_path)
    imported_turns = 0

    for run_dir in sorted(path for path in runs_root.iterdir() if path.is_dir()):
        database.upsert_run(run_id=run_dir.name, run_dir=run_dir, db_path=db_path)
        for turn_dir in sorted(path for path in run_dir.iterdir() if path.is_dir() and path.name.startswith("turn_")):
            if _import_error(run_dir.name, turn_dir, db_path):
                continue
            turn_log_path = turn_dir / "turn_log.json"
            if not turn_log_path.exists():
                continue

            turn_log = _read_json(turn_log_path, {})
            prompt_positive, prompt_negative = _read_prompt(turn_dir / "prompt.txt")
            evaluation = _read_json(turn_dir / "evaluation.json", {})
            checklist = _read_json(turn_dir / "checklist.json", [])
            turn_index = int(turn_log.get("turn") or _turn_index_from_dir(turn_dir))
            image_path = ROOT / str(turn_log.get("image_path", turn_dir / "image.png"))

            database.save_turn(
                run_id=run_dir.name,
                run_dir=run_dir,
                turn_index=turn_index,
                instruction=str(turn_log.get("instruction", "")),
                delta=_read_json(turn_dir / "delta.json", {}),
                memory=_read_json(turn_dir / "memory.json", {}),
                prompt_positive=prompt_positive,
                prompt_negative=prompt_negative,
                checklist=checklist if isinstance(checklist, list) else [],
                evaluation=evaluation if isinstance(evaluation, dict) else {},
                image_path=image_path,
                api_summary=_read_json(turn_dir / "api_responses.json", {}),
                db_path=db_path,
            )
            imported_turns += 1

    return imported_turns


def _import_error(run_id: str, turn_dir: Path, db_path: Path) -> bool:
    error_path = turn_dir / "error.json"
    if not error_path.exists():
        return False

    error_data = _read_json(error_path, {})
    turn_index = int(error_data.get("turn") or _turn_index_from_dir(turn_dir))
    stage = str(error_data.get("stage", "unknown"))
    message = str(error_data.get("message", ""))
    error_type = str(error_data.get("error_type", "RuntimeError"))
    database.init_db(db_path)
    with database.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO errors(run_id, turn_index, stage, error_type, message)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(run_id, turn_index, stage) DO UPDATE SET
                error_type = excluded.error_type,
                message = excluded.message
            """,
            (run_id, turn_index, stage, error_type, message),
        )
    return True


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _read_prompt(path: Path) -> Tuple[str, str]:
    if not path.exists():
        return "", ""
    text = path.read_text(encoding="utf-8")
    match = re.search(
        r"POSITIVE PROMPT\n(?P<positive>.*?)\n\nNEGATIVE PROMPT\n(?P<negative>.*)\Z",
        text,
        re.DOTALL,
    )
    if not match:
        return text.strip(), ""
    return match.group("positive").strip(), match.group("negative").strip()


def _turn_index_from_dir(turn_dir: Path) -> int:
    return int(turn_dir.name.replace("turn_", ""))


if __name__ == "__main__":
    main()
