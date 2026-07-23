"""Analyze bad benchmark turns from saved JSON artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

ROOT = Path(__file__).resolve().parents[1]

import sys

sys.path.insert(0, str(ROOT))

from core.metrics import list_turn_badcase_matrix


OUTPUT_DIR = ROOT / "outputs" / "reports"


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze bad turns using saved JSON files.")
    parser.add_argument("--benchmark-run-id", default="memory_stress_full_v2_20260723")
    args = parser.parse_args()

    rows = list_turn_badcase_matrix(benchmark_run_id=args.benchmark_run_id)
    bad_rows = [row for row in rows if row.get("status") == "BAD"]
    report = build_report(args.benchmark_run_id, bad_rows)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"{args.benchmark_run_id}_badcase_json_analysis.md"
    path.write_text(report, encoding="utf-8")
    print(path.relative_to(ROOT))


def build_report(benchmark_run_id: str, rows: Iterable[Dict[str, Any]]) -> str:
    lines = [
        f"# Badcase JSON Analysis: {benchmark_run_id}",
        "",
        "This report is generated from per-turn artifacts: delta.json, memory.json, prompt.txt, evaluation.json, and method_metadata.json.",
        "",
        "## Findings",
        "",
    ]
    for row in rows:
        analysis = analyze_row(benchmark_run_id, row)
        lines.extend(
            [
                f"### {analysis['method']} / {analysis['case_id']} / Turn {analysis['turn_index']}",
                "",
                f"- Instruction: {analysis['instruction']}",
                f"- Failed: {analysis['failed_items']}",
                f"- Evaluation reason: {analysis['failed_reasons']}",
                f"- Attribution: {analysis['attribution']}",
                f"- JSON evidence: {analysis['evidence']}",
                f"- Fix direction: {analysis['fix']}",
                "",
            ]
        )
    return "\n".join(lines)


def analyze_row(benchmark_run_id: str, row: Dict[str, Any]) -> Dict[str, Any]:
    turn_dir = (
        ROOT
        / "outputs"
        / "benchmarks"
        / benchmark_run_id
        / str(row["method"])
        / str(row["case_id"])
        / f"turn_{int(row['turn_index']):02d}"
    )
    delta = read_json(turn_dir / "delta.json")
    memory = read_json(turn_dir / "memory.json")
    evaluation = read_json(turn_dir / "evaluation.json")
    metadata = read_json(turn_dir / "method_metadata.json")
    prompt = read_text(turn_dir / "prompt.txt")

    method = str(row["method"])
    case_id = str(row["case_id"])
    failed_items = str(row.get("failed_items") or "")
    failed_reasons = str(row.get("failed_reasons") or "")
    prompt_lower = prompt.lower()
    memory_text = json.dumps(memory, ensure_ascii=False).lower()
    delta_text = json.dumps(delta, ensure_ascii=False).lower()
    metadata_text = json.dumps(metadata, ensure_ascii=False)

    attribution = "模型能力层"
    evidence: List[str] = []
    fix = "增加失败项定向重试，并在评估失败后重新生成。"

    if method == "current-only":
        attribution = "输入层 / baseline 设计层"
        evidence.append("method_metadata uses_history=false，prompt 只包含 current user request。")
        evidence.append("prompt 中没有完整历史约束，所以历史主体、背景、姿态或属性缺失是预期风险。")
        fix = "current-only 只能作为弱 baseline；比较主实验时应标注它没有记忆输入。"
    elif method == "pullprompt":
        if "left" in prompt_lower and "dog_left" in failed_items:
            attribution = "模型能力层 / 空间关系执行失败"
            evidence.append("prompt 已包含 move left / keeping it on the left，但 evaluation 判断主体仍居中。")
            fix = "加入空间关系检查后的重试，或升级为局部编辑/布局控制。"
        else:
            evidence.append("prompt 含历史文本，但没有结构化执行计划。")
            fix = "把空间、删除、冲突更新拆成显式 checklist 和重试条件。"
    elif method == "structured-memory":
        if case_id == "material_conflict_vase":
            attribution = "策略与意图层 / 记忆冲突合并错误"
            evidence.append(_presence(memory_text, ["clear glass vase", "white ceramic", "clear glass"]))
            evidence.append("memory 保留旧对象名或旧约束，导致 prompt 同时表达 glass 与 ceramic。")
            fix = "更新 memory merge：replacement 要覆盖对象 name、attributes 和 constraints，旧材质约束应 supersede/delete。"
        elif case_id == "object_addition_wallet":
            attribution = "策略与意图层 / 删除约束保留不强"
            evidence.append(_presence(memory_text, ["credit card", "no credit card", "remove"]))
            evidence.append("evaluation 显示信用卡残留；若 prompt 仍弱化删除约束，生成模型会复现初始物体。")
            fix = "把 remove 转成 active negative constraint，并在 prompt 中提升为 hard constraint；更好是对信用卡区域做 inpainting。"
        elif case_id == "scarf_color_conflict_fox":
            attribution = "策略与意图层 / 冲突属性未彻底覆盖"
            evidence.append(_presence(memory_text, ["red scarf", "blue scarf"]))
            evidence.append("evaluation 看到红围巾残留，说明替换类属性没有局部删除旧属性。")
            fix = "冲突属性采用 latest-wins：blue scarf supersedes red scarf，并显式加入 no red scarf hard negative。"
        elif case_id == "negative_constraint_teacher":
            attribution = "输出格式层 / 模型生成层"
            evidence.append(_presence(prompt_lower, ["do not include readable text", "text artifacts"]))
            evidence.append("JSON/prompt 已有禁止文字，失败来自图像模型常见的文字伪影控制不足。")
            fix = "对 text/no-text 加 VLM 检查后重试，或 prompt 中加入 blank blackboard / no letters / no symbols。"
        else:
            evidence.append("structured memory 已进入 prompt，但图像仍未满足局部约束。")
            fix = "加入局部编辑、mask 和失败项重试。"

    if "items" in evaluation:
        failed_eval = [item for item in evaluation["items"] if not item.get("passed")]
        if failed_eval:
            evidence.append("failed evaluation ids=" + ", ".join(str(item.get("id")) for item in failed_eval))

    if delta_text not in ("{}", "null"):
        evidence.append("delta keys=" + ", ".join(delta.keys()))
    if metadata_text and metadata_text != "{}":
        evidence.append("metadata=" + metadata_text)

    return {
        "method": method,
        "case_id": case_id,
        "turn_index": row["turn_index"],
        "instruction": row.get("instruction", ""),
        "failed_items": failed_items,
        "failed_reasons": failed_reasons,
        "attribution": attribution,
        "evidence": " ".join(item for item in evidence if item),
        "fix": fix,
    }


def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _presence(text: str, terms: List[str]) -> str:
    hits = [term for term in terms if term.lower() in text]
    misses = [term for term in terms if term.lower() not in text]
    parts = []
    if hits:
        parts.append("present=" + ", ".join(hits))
    if misses:
        parts.append("missing=" + ", ".join(misses))
    return "; ".join(parts)


if __name__ == "__main__":
    main()
