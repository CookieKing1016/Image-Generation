"""SQLite storage for run and turn artifacts.

The file logger remains the source of large artifacts such as images. This
module stores searchable metadata and JSON payloads so reports and dashboards
can query past runs without walking the output directory every time.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from core.schema import json_dumps


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT / "outputs" / "mem2image.sqlite3"


SCHEMA_VERSION = 1


def connect(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    with connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                case_id TEXT,
                method TEXT NOT NULL DEFAULT 'structured-memory',
                run_dir TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                metadata_json TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS turns (
                run_id TEXT NOT NULL,
                turn_index INTEGER NOT NULL,
                instruction TEXT NOT NULL,
                image_path TEXT,
                prompt_positive TEXT NOT NULL DEFAULT '',
                prompt_negative TEXT NOT NULL DEFAULT '',
                checklist_score REAL,
                failed_item_count INTEGER NOT NULL DEFAULT 0,
                delta_json TEXT NOT NULL DEFAULT '{}',
                memory_json TEXT NOT NULL DEFAULT '{}',
                checklist_json TEXT NOT NULL DEFAULT '[]',
                evaluation_json TEXT NOT NULL DEFAULT '{}',
                api_summary_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (run_id, turn_index),
                FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS checklist_items (
                run_id TEXT NOT NULL,
                turn_index INTEGER NOT NULL,
                item_id TEXT NOT NULL,
                question TEXT NOT NULL,
                target TEXT NOT NULL,
                item_type TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT '',
                critical INTEGER NOT NULL DEFAULT 0,
                drift_type TEXT NOT NULL DEFAULT '',
                answer TEXT NOT NULL DEFAULT '',
                passed INTEGER,
                confidence REAL,
                reason TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (run_id, turn_index, item_id),
                FOREIGN KEY (run_id, turn_index)
                    REFERENCES turns(run_id, turn_index)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS errors (
                run_id TEXT NOT NULL,
                turn_index INTEGER NOT NULL,
                stage TEXT NOT NULL,
                error_type TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (run_id, turn_index, stage)
            );
            """
        )
        conn.execute(
            "INSERT OR REPLACE INTO schema_meta(key, value) VALUES (?, ?)",
            ("schema_version", str(SCHEMA_VERSION)),
        )
        _ensure_column(conn, "checklist_items", "source", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "checklist_items", "critical", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "checklist_items", "drift_type", "TEXT NOT NULL DEFAULT ''")


def upsert_run(
    run_id: str,
    run_dir: Path,
    db_path: Path = DEFAULT_DB_PATH,
    case_id: Optional[str] = None,
    method: str = "structured-memory",
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    init_db(db_path)
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO runs(run_id, case_id, method, run_dir, metadata_json)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                case_id = COALESCE(excluded.case_id, runs.case_id),
                method = excluded.method,
                run_dir = excluded.run_dir,
                metadata_json = excluded.metadata_json
            """,
            (
                run_id,
                case_id,
                method,
                _relpath(run_dir),
                json_dumps(metadata or {}),
            ),
        )


def save_turn(
    run_id: str,
    run_dir: Path,
    turn_index: int,
    instruction: str,
    delta: Dict[str, Any],
    memory: Dict[str, Any],
    prompt_positive: str,
    prompt_negative: str,
    checklist: List[Dict[str, Any]],
    evaluation: Dict[str, Any],
    image_path: Path,
    api_summary: Dict[str, Any],
    db_path: Path = DEFAULT_DB_PATH,
    method: str = "structured-memory",
    case_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    upsert_run(
        run_id=run_id,
        run_dir=run_dir,
        db_path=db_path,
        method=method,
        case_id=case_id,
        metadata=metadata,
    )
    failed_items = evaluation.get("failed_items", [])
    if not isinstance(failed_items, list):
        failed_items = []

    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO turns(
                run_id, turn_index, instruction, image_path,
                prompt_positive, prompt_negative, checklist_score,
                failed_item_count, delta_json, memory_json, checklist_json,
                evaluation_json, api_summary_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id, turn_index) DO UPDATE SET
                instruction = excluded.instruction,
                image_path = excluded.image_path,
                prompt_positive = excluded.prompt_positive,
                prompt_negative = excluded.prompt_negative,
                checklist_score = excluded.checklist_score,
                failed_item_count = excluded.failed_item_count,
                delta_json = excluded.delta_json,
                memory_json = excluded.memory_json,
                checklist_json = excluded.checklist_json,
                evaluation_json = excluded.evaluation_json,
                api_summary_json = excluded.api_summary_json
            """,
            (
                run_id,
                turn_index,
                instruction,
                _relpath(image_path),
                prompt_positive,
                prompt_negative,
                _optional_float(evaluation.get("checklist_score")),
                len(failed_items),
                json_dumps(delta),
                json_dumps(memory),
                json_dumps(checklist),
                json_dumps(evaluation),
                json_dumps(api_summary),
            ),
        )
        conn.execute(
            "DELETE FROM checklist_items WHERE run_id = ? AND turn_index = ?",
            (run_id, turn_index),
        )
        conn.executemany(
            """
            INSERT INTO checklist_items(
                run_id, turn_index, item_id, question, target, item_type,
                source, critical, drift_type, answer, passed, confidence, reason
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            _checklist_rows(run_id, turn_index, checklist, evaluation),
        )


def save_error(
    run_id: str,
    turn_index: int,
    stage: str,
    error: Exception,
    db_path: Path = DEFAULT_DB_PATH,
) -> None:
    init_db(db_path)
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO errors(run_id, turn_index, stage, error_type, message)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(run_id, turn_index, stage) DO UPDATE SET
                error_type = excluded.error_type,
                message = excluded.message
            """,
            (run_id, turn_index, stage, type(error).__name__, str(error)),
        )


def list_runs(db_path: Path = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    init_db(db_path)
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            WITH turn_summary AS (
                SELECT
                    run_id,
                    COUNT(*) AS turn_count,
                    AVG(checklist_score) AS avg_checklist_score,
                    SUM(failed_item_count) AS failed_item_count
                FROM turns
                GROUP BY run_id
            ),
            turn_item_summary AS (
                SELECT
                    turns.run_id,
                    turns.turn_index,
                    SUM(CASE WHEN checklist_items.source = 'history'
                        OR (checklist_items.source = '' AND checklist_items.item_type != 'current_turn')
                        THEN 1 ELSE 0 END) AS history_total,
                    SUM(CASE WHEN (checklist_items.source = 'history'
                        OR (checklist_items.source = '' AND checklist_items.item_type != 'current_turn'))
                        AND checklist_items.passed = 1 THEN 1 ELSE 0 END) AS history_passed,
                    SUM(CASE WHEN checklist_items.source = 'current'
                        OR checklist_items.item_type = 'current_turn'
                        THEN 1 ELSE 0 END) AS current_total,
                    SUM(CASE WHEN (checklist_items.source = 'current'
                        OR checklist_items.item_type = 'current_turn')
                        AND checklist_items.passed = 1 THEN 1 ELSE 0 END) AS current_passed
                FROM turns
                LEFT JOIN checklist_items
                    ON turns.run_id = checklist_items.run_id
                    AND turns.turn_index = checklist_items.turn_index
                GROUP BY turns.run_id, turns.turn_index
            ),
            item_summary AS (
                SELECT
                    run_id,
                    AVG(
                        CASE
                            WHEN history_total = 0 THEN 1.0
                            ELSE CAST(history_passed AS REAL) / history_total
                        END
                    ) AS history_retention_rate,
                    AVG(
                        CASE
                            WHEN current_total = 0 THEN 1.0
                            WHEN current_passed = current_total THEN 1.0
                            ELSE 0.0
                        END
                    ) AS current_turn_success_rate
                FROM turn_item_summary
                GROUP BY run_id
            )
            SELECT
                runs.run_id,
                runs.case_id,
                runs.method,
                runs.run_dir,
                runs.created_at,
                COALESCE(turn_summary.turn_count, 0) AS turn_count,
                turn_summary.avg_checklist_score,
                COALESCE(turn_summary.failed_item_count, 0) AS failed_item_count,
                item_summary.history_retention_rate,
                item_summary.current_turn_success_rate
            FROM runs
            LEFT JOIN turn_summary ON runs.run_id = turn_summary.run_id
            LEFT JOIN item_summary ON runs.run_id = item_summary.run_id
            ORDER BY runs.created_at DESC, runs.run_id DESC
            """
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def list_turns(run_id: str, db_path: Path = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    init_db(db_path)
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM turns
            WHERE run_id = ?
            ORDER BY turn_index
            """,
            (run_id,),
        ).fetchall()
    return [_decode_turn(row) for row in rows]


def _checklist_rows(
    run_id: str,
    turn_index: int,
    checklist: Iterable[Dict[str, Any]],
    evaluation: Dict[str, Any],
) -> Iterable[tuple]:
    eval_by_id = {
        str(item.get("id", "")): item
        for item in evaluation.get("items", [])
        if isinstance(item, dict)
    }
    for item in checklist:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id", ""))
        evaluated = eval_by_id.get(item_id, {})
        passed = evaluated.get("passed")
        yield (
            run_id,
            turn_index,
            item_id,
            str(item.get("question", "")),
            str(item.get("target", "")),
            str(item.get("type", "")),
            str(item.get("source", "")),
            1 if bool(item.get("critical", False)) else 0,
            str(item.get("drift_type", "")),
            str(evaluated.get("answer", "")),
            int(passed) if isinstance(passed, bool) else None,
            _optional_float(evaluated.get("confidence")),
            str(evaluated.get("reason", "")),
        )


def _decode_turn(row: sqlite3.Row) -> Dict[str, Any]:
    result = _row_to_dict(row)
    for key in (
        "delta_json",
        "memory_json",
        "checklist_json",
        "evaluation_json",
        "api_summary_json",
    ):
        result[key] = json.loads(result[key])
    return result


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _optional_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _relpath(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)
