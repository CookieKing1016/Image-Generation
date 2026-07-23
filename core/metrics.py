"""Metric summaries for benchmark runs stored in SQLite."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from core import database


def summarize_methods(
    db_path: Path = database.DEFAULT_DB_PATH,
    benchmark_run_id: str = "",
) -> List[Dict[str, Any]]:
    database.init_db(db_path)
    params: List[Any] = []
    where = ""
    if benchmark_run_id:
        where = "WHERE runs.metadata_json LIKE ?"
        params.append(f'%"benchmark_run_id": "{benchmark_run_id}"%')

    with database.connect(db_path) as conn:
        rows = conn.execute(
            f"""
            WITH selected_runs AS (
                SELECT *
                FROM runs
                {where}
            ),
            turn_summary AS (
                SELECT
                    selected_runs.method,
                    COUNT(DISTINCT selected_runs.case_id) AS case_count,
                    COUNT(*) AS turn_count,
                    AVG(turns.checklist_score) AS avg_checklist_score,
                    SUM(turns.failed_item_count) AS failed_item_count
                FROM selected_runs
                LEFT JOIN turns ON selected_runs.run_id = turns.run_id
                GROUP BY selected_runs.method
            ),
            turn_item_summary AS (
                SELECT
                    selected_runs.method,
                    turns.run_id,
                    turns.turn_index,
                    SUM(CASE WHEN {_history_item_condition()} THEN 1 ELSE 0 END) AS history_total,
                    SUM(CASE WHEN {_history_item_condition()} AND checklist_items.passed = 1 THEN 1 ELSE 0 END)
                        AS history_passed,
                    SUM(CASE WHEN {_current_item_condition()} THEN 1 ELSE 0 END) AS current_total,
                    SUM(CASE WHEN {_current_item_condition()} AND checklist_items.passed = 1 THEN 1 ELSE 0 END)
                        AS current_passed
                FROM selected_runs
                JOIN turns ON selected_runs.run_id = turns.run_id
                LEFT JOIN checklist_items
                    ON turns.run_id = checklist_items.run_id
                    AND turns.turn_index = checklist_items.turn_index
                GROUP BY selected_runs.method, turns.run_id, turns.turn_index
            ),
            row_metric_summary AS (
                SELECT
                    method,
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
                GROUP BY method
            ),
            item_summary AS (
                SELECT
                    selected_runs.method,
                    AVG(CASE WHEN checklist_items.critical = 1 THEN checklist_items.passed END)
                        AS critical_success_rate,
                    SUM(CASE WHEN checklist_items.passed = 0 THEN 1 ELSE 0 END) AS drift_count
                FROM selected_runs
                LEFT JOIN checklist_items ON selected_runs.run_id = checklist_items.run_id
                GROUP BY selected_runs.method
            )
            SELECT
                turn_summary.method,
                turn_summary.case_count,
                turn_summary.turn_count,
                turn_summary.avg_checklist_score,
                COALESCE(turn_summary.failed_item_count, 0) AS failed_item_count,
                row_metric_summary.history_retention_rate,
                row_metric_summary.current_turn_success_rate,
                item_summary.critical_success_rate,
                COALESCE(item_summary.drift_count, 0) AS drift_count
            FROM turn_summary
            LEFT JOIN row_metric_summary ON turn_summary.method = row_metric_summary.method
            LEFT JOIN item_summary ON turn_summary.method = item_summary.method
            ORDER BY turn_summary.method
            """,
            params,
        ).fetchall()
    return [_rounded(row) for row in rows]


def summarize_drift_types(
    db_path: Path = database.DEFAULT_DB_PATH,
    benchmark_run_id: str = "",
) -> List[Dict[str, Any]]:
    database.init_db(db_path)
    params: List[Any] = []
    where = "WHERE checklist_items.drift_type != ''"
    if benchmark_run_id:
        where += " AND runs.metadata_json LIKE ?"
        params.append(f'%"benchmark_run_id": "{benchmark_run_id}"%')

    with database.connect(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT
                runs.method,
                checklist_items.drift_type,
                COUNT(*) AS item_count,
                AVG(checklist_items.passed) AS pass_rate,
                SUM(CASE WHEN checklist_items.passed = 0 THEN 1 ELSE 0 END) AS failed_count
            FROM checklist_items
            JOIN runs ON checklist_items.run_id = runs.run_id
            {where}
            GROUP BY runs.method, checklist_items.drift_type
            ORDER BY runs.method, checklist_items.drift_type
            """,
            params,
        ).fetchall()
    return [_rounded(row) for row in rows]


def list_benchmark_run_ids(db_path: Path = database.DEFAULT_DB_PATH) -> List[str]:
    database.init_db(db_path)
    with database.connect(db_path) as conn:
        rows = conn.execute("SELECT metadata_json FROM runs").fetchall()
    ids = set()
    for row in rows:
        try:
            metadata = json.loads(row["metadata_json"] or "{}")
        except json.JSONDecodeError:
            continue
        benchmark_run_id = metadata.get("benchmark_run_id")
        if benchmark_run_id:
            ids.add(str(benchmark_run_id))
    return sorted(ids, reverse=True)


def list_turn_metrics(
    db_path: Path = database.DEFAULT_DB_PATH,
    benchmark_run_id: str = "",
) -> List[Dict[str, Any]]:
    database.init_db(db_path)
    params: List[Any] = []
    where = ""
    if benchmark_run_id:
        where = "WHERE runs.metadata_json LIKE ?"
        params.append(f'%"benchmark_run_id": "{benchmark_run_id}"%')

    with database.connect(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT
                runs.run_id,
                runs.case_id,
                runs.method,
                turns.turn_index,
                turns.instruction,
                turns.checklist_score,
                turns.failed_item_count,
                turns.image_path,
                turns.created_at
            FROM runs
            JOIN turns ON runs.run_id = turns.run_id
            {where}
            ORDER BY runs.created_at DESC, runs.run_id DESC, turns.turn_index
            """,
            params,
        ).fetchall()
    return [_rounded(row) for row in rows]


def list_failed_items(
    db_path: Path = database.DEFAULT_DB_PATH,
    benchmark_run_id: str = "",
) -> List[Dict[str, Any]]:
    database.init_db(db_path)
    params: List[Any] = []
    where = "WHERE checklist_items.passed = 0"
    if benchmark_run_id:
        where += " AND runs.metadata_json LIKE ?"
        params.append(f'%"benchmark_run_id": "{benchmark_run_id}"%')

    with database.connect(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT
                runs.run_id,
                runs.case_id,
                runs.method,
                checklist_items.turn_index,
                checklist_items.item_id,
                checklist_items.item_type,
                checklist_items.source,
                checklist_items.critical,
                checklist_items.drift_type,
                checklist_items.question,
                checklist_items.target,
                checklist_items.answer,
                checklist_items.confidence,
                checklist_items.reason
            FROM checklist_items
            JOIN runs ON checklist_items.run_id = runs.run_id
            {where}
            ORDER BY runs.created_at DESC, runs.run_id DESC, checklist_items.turn_index, checklist_items.item_id
            """,
            params,
        ).fetchall()
    return [_rounded(row) for row in rows]


def dashboard_totals(
    db_path: Path = database.DEFAULT_DB_PATH,
    benchmark_run_id: str = "",
) -> Dict[str, Any]:
    method_rows = summarize_methods(db_path, benchmark_run_id)
    turns = list_turn_metrics(db_path, benchmark_run_id)
    failed = list_failed_items(db_path, benchmark_run_id)
    cases = {row.get("case_id") for row in turns if row.get("case_id")}
    avg_score = _mean(row.get("avg_checklist_score") for row in method_rows)
    history = _mean(row.get("history_retention_rate") for row in method_rows)
    current = _mean(row.get("current_turn_success_rate") for row in method_rows)
    return {
        "method_count": len(method_rows),
        "case_count": len(cases),
        "turn_count": len(turns),
        "failed_item_count": len(failed),
        "avg_checklist_score": round(avg_score, 4),
        "history_retention_rate": round(history, 4),
        "current_turn_success_rate": round(current, 4),
    }


def _rounded(row) -> Dict[str, Any]:
    result = {key: row[key] for key in row.keys()}
    for key, value in list(result.items()):
        if isinstance(value, float):
            result[key] = round(value, 4)
    return result


def _mean(values) -> float:
    parsed = []
    for value in values:
        if value is None:
            continue
        try:
            parsed.append(float(value))
        except (TypeError, ValueError):
            continue
    return sum(parsed) / len(parsed) if parsed else 0.0


def _history_item_condition() -> str:
    return "(checklist_items.source = 'history' OR (checklist_items.source = '' AND checklist_items.item_type != 'current_turn'))"


def _current_item_condition() -> str:
    return "(checklist_items.source = 'current' OR checklist_items.item_type = 'current_turn')"
