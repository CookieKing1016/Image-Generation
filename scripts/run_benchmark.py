"""Run benchmark cases across prompt-building methods."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agents.evaluator import ChecklistEvaluator
from core import database
from core.schema import json_dumps
from methods import create_method
from tools.config import Settings
from tools.siliconflow_client import SiliconFlowClient, first_image_url


BENCHMARK_PATH = ROOT_DIR / "data" / "benchmark.json"
BENCHMARK_OUTPUT_ROOT = ROOT_DIR / "outputs" / "benchmarks"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Mem2Image benchmark methods.")
    parser.add_argument("--benchmark", type=Path, default=BENCHMARK_PATH)
    parser.add_argument(
        "--methods",
        nargs="+",
        default=None,
        help="Methods to run: current-only, full-history, structured-memory.",
    )
    parser.add_argument("--case-limit", type=int, default=0)
    parser.add_argument(
        "--case-ids",
        nargs="+",
        default=None,
        help="Optional case_id list to run. Applied before --case-limit.",
    )
    parser.add_argument("--turn-limit", type=int, default=0)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--db", type=Path, default=database.DEFAULT_DB_PATH)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build prompts and artifacts without calling image/VLM APIs.",
    )
    args = parser.parse_args()

    method_names = args.methods
    if method_names is None:
        method_names = ["current-only", "full-history"] if args.dry_run else [
            "current-only",
            "full-history",
            "structured-memory",
        ]

    settings = Settings.from_env()
    summary = run_benchmark(
        benchmark_path=args.benchmark,
        method_names=method_names,
        settings=settings,
        benchmark_run_id=args.run_id or make_benchmark_run_id(),
        db_path=args.db,
        case_limit=args.case_limit,
        case_ids=args.case_ids,
        turn_limit=args.turn_limit,
        max_retries=args.max_retries,
        dry_run=args.dry_run,
    )
    print(json_dumps(summary))


def run_benchmark(
    benchmark_path: Path,
    method_names: List[str],
    settings: Settings,
    benchmark_run_id: str,
    db_path: Path = database.DEFAULT_DB_PATH,
    case_limit: int = 0,
    case_ids: List[str] | None = None,
    turn_limit: int = 0,
    max_retries: int = 2,
    dry_run: bool = False,
) -> Dict[str, Any]:
    benchmark = load_benchmark(benchmark_path)
    if dry_run and "structured-memory" in method_names:
        raise ValueError("Dry run cannot execute structured-memory because intent parsing requires an LLM API call.")
    cases = benchmark["cases"]
    if case_ids:
        requested = set(case_ids)
        cases = [case for case in cases if case["case_id"] in requested]
        missing = sorted(requested - {case["case_id"] for case in cases})
        if missing:
            raise ValueError(f"Unknown benchmark case_id(s): {', '.join(missing)}")
    cases = cases[: case_limit or None]
    client = None if dry_run else SiliconFlowClient(settings)
    evaluator = None if dry_run else ChecklistEvaluator(client)
    output_root = BENCHMARK_OUTPUT_ROOT / benchmark_run_id
    output_root.mkdir(parents=True, exist_ok=True)

    results = []
    for method_name in method_names:
        method = create_method(method_name, client=client)
        for case in cases:
            run_id = f"{benchmark_run_id}__{method_name}__{case['case_id']}"
            run_dir = output_root / method_name / case["case_id"]
            database.upsert_run(
                run_id=run_id,
                run_dir=run_dir,
                db_path=db_path,
                case_id=case["case_id"],
                method=method_name,
                metadata={
                    "benchmark": benchmark.get("name", ""),
                    "benchmark_version": benchmark.get("version"),
                    "benchmark_run_id": benchmark_run_id,
                    "drift_types": case.get("drift_types", []),
                    "dry_run": dry_run,
                },
            )
            case_result = run_case(
                case=case,
                method=method,
                method_name=method_name,
                run_id=run_id,
                run_dir=run_dir,
                benchmark=benchmark,
                benchmark_run_id=benchmark_run_id,
                db_path=db_path,
                client=client,
                evaluator=evaluator,
                turn_limit=turn_limit,
                max_retries=max_retries,
                dry_run=dry_run,
            )
            results.append(case_result)

    return {
        "benchmark_run_id": benchmark_run_id,
        "benchmark": benchmark.get("name", ""),
        "dry_run": dry_run,
        "methods": method_names,
        "case_count": len(cases),
        "run_count": len(results),
        "output_root": str(output_root),
        "db_path": str(db_path),
        "results": results,
    }


def run_case(
    case: Dict[str, Any],
    method,
    method_name: str,
    run_id: str,
    run_dir: Path,
    benchmark: Dict[str, Any],
    benchmark_run_id: str,
    db_path: Path,
    client: SiliconFlowClient | None,
    evaluator: ChecklistEvaluator | None,
    turn_limit: int = 0,
    max_retries: int = 2,
    dry_run: bool = False,
) -> Dict[str, Any]:
    history: List[str] = []
    state = method.initial_state()
    turns = case["turns"][: turn_limit or None]
    completed = 0

    for turn_index, turn in enumerate(turns, 1):
        instruction = turn["instruction"]
        checklist = turn["checklist"]
        turn_dir = run_dir / f"turn_{turn_index:02d}"
        turn_dir.mkdir(parents=True, exist_ok=True)
        print(
            f"[benchmark] {method_name} / {case['case_id']} / turn {turn_index}/{len(turns)}",
            flush=True,
        )

        try:
            method_result = method.build_turn(instruction, history, state)
            state = method_result.state
            prompt_positive = method_result.positive_prompt
            prompt_negative = method_result.negative_prompt
            image_path = turn_dir / "image.png"
            api_summary: Dict[str, Any] = {}

            if dry_run:
                _write_placeholder_image(image_path)
                evaluation = dry_run_evaluation(checklist)
            else:
                assert client is not None
                assert evaluator is not None
                image_response, evaluation = _run_generation_and_evaluation_with_retries(
                    client=client,
                    evaluator=evaluator,
                    generation_prompt=method_result.generation_prompt,
                    image_path=image_path,
                    checklist=checklist,
                    memory=method_result.state,
                    prompt_positive=prompt_positive,
                    max_retries=max_retries,
                )
                api_summary["image_generation"] = database_summary(image_response)

            save_turn_files(
                turn_dir=turn_dir,
                run_id=run_id,
                case_id=case["case_id"],
                method_name=method_name,
                turn_index=turn_index,
                instruction=instruction,
                method_result=method_result,
                checklist=checklist,
                evaluation=evaluation,
                image_path=image_path,
                api_summary=api_summary,
            )
            database.save_turn(
                run_id=run_id,
                run_dir=run_dir,
                turn_index=turn_index,
                instruction=instruction,
                delta=method_result.delta,
                memory=method_result.state,
                prompt_positive=prompt_positive,
                prompt_negative=prompt_negative,
                checklist=checklist,
                evaluation=evaluation,
                image_path=image_path,
                api_summary=api_summary,
                db_path=db_path,
                method=method_name,
                case_id=case["case_id"],
                metadata={
                    "benchmark": benchmark.get("name", ""),
                    "benchmark_version": benchmark.get("version"),
                    "benchmark_run_id": benchmark_run_id,
                    "drift_types": case.get("drift_types", []),
                    "dry_run": dry_run,
                },
            )
            history.append(instruction)
            completed += 1
        except Exception as exc:
            save_error_file(turn_dir, turn_index, "benchmark_turn", exc)
            database.save_error(run_id, turn_index, "benchmark_turn", exc, db_path=db_path)
            print(
                f"[benchmark] FAILED {method_name} / {case['case_id']} / turn {turn_index}: {type(exc).__name__}: {exc}",
                flush=True,
            )
            break

    return {
        "run_id": run_id,
        "case_id": case["case_id"],
        "method": method_name,
        "completed_turns": completed,
        "total_turns": len(turns),
        "run_dir": str(run_dir),
    }


def load_benchmark(path: Path) -> Dict[str, Any]:
    benchmark = json.loads(path.read_text(encoding="utf-8"))
    validate_benchmark(benchmark)
    return benchmark


def validate_benchmark(benchmark: Dict[str, Any]) -> None:
    cases = benchmark.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Benchmark must contain a non-empty cases list.")
    for case in cases:
        if not case.get("case_id"):
            raise ValueError("Each benchmark case needs case_id.")
        turns = case.get("turns")
        if not isinstance(turns, list) or not turns:
            raise ValueError(f"Case {case.get('case_id')} needs non-empty turns.")
        for turn in turns:
            if not turn.get("instruction"):
                raise ValueError(f"Case {case['case_id']} has an empty instruction.")
            checklist = turn.get("checklist")
            if not isinstance(checklist, list) or not checklist:
                raise ValueError(f"Case {case['case_id']} turn needs checklist items.")
            for item in checklist:
                for key in ("id", "question", "target", "type", "source", "drift_type"):
                    if key not in item:
                        raise ValueError(f"Checklist item in {case['case_id']} is missing {key}.")


def dry_run_evaluation(checklist: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    items = []
    for item in checklist:
        items.append(
            {
                "id": item["id"],
                "question": item["question"],
                "target": item["target"],
                "answer": "unknown",
                "passed": False,
                "confidence": 0.0,
                "reason": "Dry run did not call the VLM evaluator.",
                "type": item["type"],
            }
        )
    return {
        "items": items,
        "checklist_score": 0.0,
        "failed_items": [item["question"] for item in items],
        "summary": "Dry run placeholder evaluation.",
    }


def _run_generation_and_evaluation_with_retries(
    client: SiliconFlowClient,
    evaluator: ChecklistEvaluator,
    generation_prompt: str,
    image_path: Path,
    checklist: List[Dict[str, Any]],
    memory: Dict[str, Any],
    prompt_positive: str,
    max_retries: int,
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            image_response, selected_model, failed_model_attempts = client.generate_image_with_fallback(generation_prompt)
            image_response = {
                **image_response,
                "_mem2image_selected_model": selected_model,
                "_mem2image_failed_model_attempts": failed_model_attempts,
            }
            image_url = first_image_url(image_response)
            client.download_file(image_url, image_path)
            evaluation = evaluator.evaluate(
                image_path=image_path,
                checklist=checklist,
                memory=memory,
                prompt=prompt_positive,
            )
            return image_response, evaluation
        except Exception as exc:
            last_error = exc
            if attempt >= max_retries:
                break
            time.sleep(2 * (attempt + 1))
    assert last_error is not None
    raise last_error


def save_turn_files(
    turn_dir: Path,
    run_id: str,
    case_id: str,
    method_name: str,
    turn_index: int,
    instruction: str,
    method_result,
    checklist: List[Dict[str, Any]],
    evaluation: Dict[str, Any],
    image_path: Path,
    api_summary: Dict[str, Any],
) -> None:
    _save_json(turn_dir / "delta.json", method_result.delta)
    _save_json(turn_dir / "memory.json", method_result.state)
    _save_text(
        turn_dir / "prompt.txt",
        f"POSITIVE PROMPT\n{method_result.positive_prompt}\n\n"
        f"NEGATIVE PROMPT\n{method_result.negative_prompt}\n",
    )
    _save_json(turn_dir / "checklist.json", checklist)
    _save_json(turn_dir / "evaluation.json", evaluation)
    _save_json(turn_dir / "api_responses.json", api_summary)
    _save_json(turn_dir / "method_metadata.json", method_result.metadata)
    _save_json(
        turn_dir / "turn_log.json",
        {
            "run_id": run_id,
            "case_id": case_id,
            "method": method_name,
            "turn": turn_index,
            "instruction": instruction,
            "image_path": str(image_path),
        },
    )


def save_error_file(turn_dir: Path, turn_index: int, stage: str, error: Exception) -> None:
    _save_json(
        turn_dir / "error.json",
        {
            "turn": turn_index,
            "stage": stage,
            "error_type": type(error).__name__,
            "message": str(error),
        },
    )


def database_summary(response: Dict[str, Any]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    for key in ("id", "object", "created", "model", "seed", "timings", "usage"):
        if key in response:
            summary[key] = response[key]
    if "images" in response:
        summary["images"] = response["images"]
    if "choices" in response:
        summary["choices_count"] = len(response.get("choices", []))
    for key in ("_mem2image_selected_model", "_mem2image_failed_model_attempts"):
        if key in response:
            summary[key.removeprefix("_mem2image_")] = response[key]
    return summary


def make_benchmark_run_id() -> str:
    return "benchmark_" + datetime.now().strftime("%Y%m%d_%H%M%S")


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json_dumps(data), encoding="utf-8")


def _save_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_placeholder_image(path: Path) -> None:
    placeholder = ROOT_DIR / "outputs" / "runs" / ".gitkeep"
    path.parent.mkdir(parents=True, exist_ok=True)
    if placeholder.exists():
        shutil.copyfile(placeholder, path)
    else:
        path.write_bytes(b"")


if __name__ == "__main__":
    main()
