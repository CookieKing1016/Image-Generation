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


SCHEMA_VERSION = 2


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

            CREATE TABLE IF NOT EXISTS tasks (
                run_id TEXT NOT NULL,
                turn_index INTEGER NOT NULL,
                task_id TEXT NOT NULL,
                operation TEXT NOT NULL,
                target TEXT NOT NULL DEFAULT '',
                affected_region TEXT NOT NULL DEFAULT '',
                requires_mask INTEGER NOT NULL DEFAULT 0,
                depends_on_json TEXT NOT NULL DEFAULT '[]',
                payload_json TEXT NOT NULL DEFAULT '{}',
                PRIMARY KEY (run_id, turn_index, task_id),
                FOREIGN KEY (run_id, turn_index) REFERENCES turns(run_id, turn_index) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS agent_events (
                run_id TEXT NOT NULL,
                turn_index INTEGER NOT NULL,
                event_index INTEGER NOT NULL,
                agent TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (run_id, turn_index, event_index),
                FOREIGN KEY (run_id, turn_index) REFERENCES turns(run_id, turn_index) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS image_artifacts (
                run_id TEXT NOT NULL,
                turn_index INTEGER NOT NULL,
                artifact_type TEXT NOT NULL,
                path TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                PRIMARY KEY (run_id, turn_index, artifact_type),
                FOREIGN KEY (run_id, turn_index) REFERENCES turns(run_id, turn_index) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS refinement_attempts (
                run_id TEXT NOT NULL,
                turn_index INTEGER NOT NULL,
                attempt_index INTEGER NOT NULL,
                status TEXT NOT NULL,
                failure_reason TEXT NOT NULL DEFAULT '',
                instruction TEXT NOT NULL DEFAULT '',
                score REAL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                PRIMARY KEY (run_id, turn_index, attempt_index),
                FOREIGN KEY (run_id, turn_index) REFERENCES turns(run_id, turn_index) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS evaluation_dimensions (
                run_id TEXT NOT NULL,
                turn_index INTEGER NOT NULL,
                dimension TEXT NOT NULL,
                score REAL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                PRIMARY KEY (run_id, turn_index, dimension),
                FOREIGN KEY (run_id, turn_index) REFERENCES turns(run_id, turn_index) ON DELETE CASCADE
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
    task_plan: Optional[List[Dict[str, Any]]] = None,
    agent_events: Optional[List[Dict[str, Any]]] = None,
    image_artifacts: Optional[List[Dict[str, Any]]] = None,
    refinement_attempts: Optional[List[Dict[str, Any]]] = None,
    evaluation_dimensions: Optional[Dict[str, Any]] = None,
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
            "DELETE FROM errors WHERE run_id = ? AND turn_index = ?",
            (run_id, turn_index),
        )
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
        _replace_task_data(conn, run_id, turn_index, task_plan or [])
        _replace_agent_events(conn, run_id, turn_index, agent_events or [])
        _replace_image_artifacts(conn, run_id, turn_index, image_artifacts or [])
        _replace_refinement_attempts(conn, run_id, turn_index, refinement_attempts or [])
        _replace_evaluation_dimensions(conn, run_id, turn_index, evaluation_dimensions or {})


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


def update_turn_evaluation(
    run_id: str,
    turn_index: int,
    checklist: List[Dict[str, Any]],
    evaluation: Dict[str, Any],
    db_path: Path = DEFAULT_DB_PATH,
) -> None:
    """Replace a pending asynchronous evaluation without rewriting the turn."""
    init_db(db_path)
    failed_items = evaluation.get("failed_items", [])
    if not isinstance(failed_items, list):
        failed_items = []
    with connect(db_path) as conn:
        conn.execute(
            """
            UPDATE turns
            SET checklist_score = ?, failed_item_count = ?, evaluation_json = ?, checklist_json = ?
            WHERE run_id = ? AND turn_index = ?
            """,
            (
                _optional_float(evaluation.get("checklist_score")),
                len(failed_items),
                json_dumps(evaluation),
                json_dumps(checklist),
                run_id,
                turn_index,
            ),
        )
        conn.execute("DELETE FROM checklist_items WHERE run_id = ? AND turn_index = ?", (run_id, turn_index))
        conn.executemany(
            """
            INSERT INTO checklist_items(
                run_id, turn_index, item_id, question, target, item_type,
                source, critical, drift_type, answer, passed, confidence, reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            _checklist_rows(run_id, turn_index, checklist, evaluation),
        )
        conn.execute(
            """
            INSERT INTO evaluation_dimensions(run_id, turn_index, dimension, score, metadata_json)
            VALUES (?, ?, 'checklist_score', ?, '{}')
            ON CONFLICT(run_id, turn_index, dimension) DO UPDATE SET score = excluded.score, metadata_json = excluded.metadata_json
            """,
            (run_id, turn_index, _optional_float(evaluation.get("checklist_score"))),
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


def list_execution_traces(
    db_path: Path = DEFAULT_DB_PATH,
    benchmark_run_id: str = "",
) -> List[Dict[str, Any]]:
    """Return planned edit operations with enough context for the admin UI."""
    init_db(db_path)
    where = ""
    params: List[Any] = []
    if benchmark_run_id:
        where = "WHERE runs.metadata_json LIKE ?"
        params.append(f'%"benchmark_run_id": "{benchmark_run_id}"%')
    with connect(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT runs.run_id, runs.case_id, runs.method, tasks.turn_index,
                   tasks.task_id, tasks.operation, tasks.target,
                   tasks.affected_region, tasks.requires_mask,
                   tasks.depends_on_json, tasks.payload_json,
                   (SELECT path FROM image_artifacts artifacts
                    WHERE artifacts.run_id = tasks.run_id AND artifacts.turn_index = tasks.turn_index
                      AND artifacts.artifact_type = 'previous_image') AS previous_image_path,
                   (SELECT path FROM image_artifacts artifacts
                    WHERE artifacts.run_id = tasks.run_id AND artifacts.turn_index = tasks.turn_index
                      AND artifacts.artifact_type = 'mask') AS mask_path,
                   (SELECT path FROM image_artifacts artifacts
                    WHERE artifacts.run_id = tasks.run_id AND artifacts.turn_index = tasks.turn_index
                      AND artifacts.artifact_type = 'final_image') AS final_image_path,
                   (SELECT COUNT(*) FROM agent_events events
                    WHERE events.run_id = tasks.run_id AND events.turn_index = tasks.turn_index) AS event_count
            FROM tasks
            JOIN runs ON runs.run_id = tasks.run_id
            {where}
            ORDER BY runs.created_at DESC, tasks.turn_index, tasks.task_id
            """,
            params,
        ).fetchall()
    result = []
    for row in rows:
        item = _row_to_dict(row)
        item["depends_on"] = json.loads(item.pop("depends_on_json"))
        item["payload"] = json.loads(item.pop("payload_json"))
        result.append(item)
    return result


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


def _replace_task_data(conn: sqlite3.Connection, run_id: str, turn_index: int, tasks: Iterable[Dict[str, Any]]) -> None:
    conn.execute("DELETE FROM tasks WHERE run_id = ? AND turn_index = ?", (run_id, turn_index))
    rows = []
    for task in tasks:
        if not isinstance(task, dict) or not task.get("task_id"):
            continue
        rows.append(
            (
                run_id,
                turn_index,
                str(task["task_id"]),
                str(task.get("operation", "")),
                str(task.get("target", "")),
                str(task.get("affected_region", "")),
                1 if bool(task.get("requires_mask", False)) else 0,
                json_dumps(task.get("depends_on", [])),
                json_dumps(task),
            )
        )
    if rows:
        conn.executemany(
            """
            INSERT INTO tasks(
                run_id, turn_index, task_id, operation, target, affected_region,
                requires_mask, depends_on_json, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )


def _replace_agent_events(conn: sqlite3.Connection, run_id: str, turn_index: int, events: Iterable[Dict[str, Any]]) -> None:
    conn.execute("DELETE FROM agent_events WHERE run_id = ? AND turn_index = ?", (run_id, turn_index))
    rows = []
    for index, event in enumerate(events, 1):
        if not isinstance(event, dict):
            continue
        rows.append(
            (
                run_id,
                turn_index,
                index,
                str(event.get("agent", "")),
                str(event.get("event_type", "")),
                json_dumps(event.get("payload", {})),
                str(event.get("created_at", "")) or "CURRENT_TIMESTAMP",
            )
        )
    if rows:
        conn.executemany(
            """
            INSERT INTO agent_events(run_id, turn_index, event_index, agent, event_type, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )


def _replace_image_artifacts(conn: sqlite3.Connection, run_id: str, turn_index: int, artifacts: Iterable[Dict[str, Any]]) -> None:
    conn.execute("DELETE FROM image_artifacts WHERE run_id = ? AND turn_index = ?", (run_id, turn_index))
    rows = []
    for artifact in artifacts:
        if not isinstance(artifact, dict) or not artifact.get("artifact_type"):
            continue
        rows.append(
            (
                run_id,
                turn_index,
                str(artifact["artifact_type"]),
                _relpath(Path(str(artifact.get("path", "")))) if artifact.get("path") else "",
                json_dumps(artifact.get("metadata", {})),
            )
        )
    if rows:
        conn.executemany(
            "INSERT INTO image_artifacts(run_id, turn_index, artifact_type, path, metadata_json) VALUES (?, ?, ?, ?, ?)",
            rows,
        )


def _replace_refinement_attempts(
    conn: sqlite3.Connection,
    run_id: str,
    turn_index: int,
    attempts: Iterable[Dict[str, Any]],
) -> None:
    conn.execute("DELETE FROM refinement_attempts WHERE run_id = ? AND turn_index = ?", (run_id, turn_index))
    rows = []
    for index, attempt in enumerate(attempts):
        if not isinstance(attempt, dict):
            continue
        rows.append(
            (
                run_id,
                turn_index,
                int(attempt.get("attempt_index", index)),
                str(attempt.get("status", "")),
                str(attempt.get("failure_reason", "")),
                str(attempt.get("instruction", "")),
                _optional_float(attempt.get("score")),
                json_dumps(attempt.get("metadata", {})),
            )
        )
    if rows:
        conn.executemany(
            """
            INSERT INTO refinement_attempts(
                run_id, turn_index, attempt_index, status, failure_reason,
                instruction, score, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )


def _replace_evaluation_dimensions(
    conn: sqlite3.Connection,
    run_id: str,
    turn_index: int,
    dimensions: Dict[str, Any],
) -> None:
    conn.execute("DELETE FROM evaluation_dimensions WHERE run_id = ? AND turn_index = ?", (run_id, turn_index))
    rows = []
    for name, raw_value in dimensions.items():
        if isinstance(raw_value, dict):
            score = _optional_float(raw_value.get("score"))
            metadata = {key: value for key, value in raw_value.items() if key != "score"}
        else:
            score = _optional_float(raw_value)
            metadata = {}
        rows.append((run_id, turn_index, str(name), score, json_dumps(metadata)))
    if rows:
        conn.executemany(
            "INSERT INTO evaluation_dimensions(run_id, turn_index, dimension, score, metadata_json) VALUES (?, ?, ?, ?, ?)",
            rows,
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
