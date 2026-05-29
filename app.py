"""Streamlit demo for Mem2Image first-stage pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st

from core.orchestrator import Mem2ImageOrchestrator, TurnResult
from core.run_logger import make_run_id
from core.schema import empty_memory
from tools.config import Settings


ROOT = Path(__file__).resolve().parent
EXAMPLE_PATH = ROOT / "data" / "examples" / "red_scarf_dog.json"


def main() -> None:
    st.set_page_config(page_title="Mem2Image", layout="wide")
    _init_state()

    settings = _settings_sidebar()
    example = _load_example()

    st.title("Mem2Image")
    st.caption("First-stage multi-turn T2I regeneration with Visual Intent Memory.")

    left, right = st.columns([0.42, 0.58])
    with left:
        _render_controls(settings, example)
        _render_history(example)
    with right:
        _render_latest_result()
        _render_state_panels()


def _init_state() -> None:
    if "run_id" not in st.session_state:
        st.session_state.run_id = make_run_id()
    if "memory" not in st.session_state:
        st.session_state.memory = empty_memory()
    if "results" not in st.session_state:
        st.session_state.results = []
    if "last_error" not in st.session_state:
        st.session_state.last_error = ""


def _reset_state() -> None:
    st.session_state.run_id = make_run_id()
    st.session_state.memory = empty_memory()
    st.session_state.results = []
    st.session_state.last_error = ""


def _settings_sidebar() -> Settings:
    env_settings = Settings.from_env()
    with st.sidebar:
        st.header("Backend")
        api_key = st.text_input("SiliconFlow API Key", value=env_settings.api_key, type="password")
        base_url = st.text_input("Base URL", value=env_settings.base_url)
        llm_model = st.text_input("LLM Model", value=env_settings.llm_model)
        vlm_model = st.text_input("VLM Model", value=env_settings.vlm_model)
        image_model = st.text_input("Image Model", value=env_settings.image_model)
        image_size = st.text_input("Image Size", value=env_settings.image_size)
        st.caption("Effective models for this run")
        st.code(
            "\n".join(
                [
                    f"LLM_MODEL={llm_model}",
                    f"VLM_MODEL={vlm_model}",
                    f"IMAGE_MODEL={image_model}",
                ]
            ),
            language="bash",
        )
        if "vl" in llm_model.lower() and "vl" not in vlm_model.lower():
            st.warning("LLM Model looks like a vision model, while VLM Model does not. These two fields may be swapped.")
        st.text(f"Run ID: {st.session_state.run_id}")
        if st.button("Reset run", use_container_width=True):
            _reset_state()

    return Settings(
        api_key=api_key,
        base_url=base_url,
        llm_model=llm_model,
        vlm_model=vlm_model,
        image_model=image_model,
        image_size=image_size,
        num_inference_steps=env_settings.num_inference_steps,
        guidance_scale=env_settings.guidance_scale,
        timeout_seconds=env_settings.timeout_seconds,
    )


def _render_controls(settings: Settings, example: Dict[str, Any]) -> None:
    st.subheader("Turn Input")
    instructions = example.get("turns", [])
    next_index = len(st.session_state.results)
    next_instruction = instructions[next_index] if next_index < len(instructions) else ""

    custom_instruction = st.text_area(
        "Instruction",
        value=next_instruction,
        height=110,
        placeholder="Enter the next visual instruction.",
    )

    col1, col2 = st.columns(2)
    with col1:
        run_clicked = st.button("Run turn", type="primary", use_container_width=True)
    with col2:
        demo_clicked = st.button("Run demo turn", use_container_width=True)

    if run_clicked:
        _run_turn(settings, custom_instruction.strip())
    if demo_clicked:
        _run_turn(settings, next_instruction.strip())

    if st.session_state.last_error:
        st.error(st.session_state.last_error)


def _run_turn(settings: Settings, instruction: str) -> None:
    if not instruction:
        st.warning("Instruction is empty.")
        return
    if not settings.api_key:
        st.session_state.last_error = (
            "SILICONFLOW_API_KEY is missing. Add it to .env or paste it in the sidebar."
        )
        return

    st.session_state.last_error = ""
    turn_index = len(st.session_state.results) + 1
    orchestrator = Mem2ImageOrchestrator(settings=settings, run_id=st.session_state.run_id)

    with st.spinner(f"Running turn {turn_index} with LLM, image generation, and VLM evaluation..."):
        try:
            result = orchestrator.run_turn(
                instruction=instruction,
                memory=st.session_state.memory,
                turn_index=turn_index,
            )
        except Exception as exc:
            st.session_state.last_error = str(exc)
            return

    st.session_state.memory = result.memory
    st.session_state.results.append(_result_to_state(result))


def _render_history(example: Dict[str, Any]) -> None:
    st.subheader("Demo Case")
    st.write(example.get("name", "red_scarf_dog"))
    for idx, instruction in enumerate(example.get("turns", []), 1):
        completed = idx <= len(st.session_state.results)
        label = "done" if completed else "pending"
        st.markdown(f"`Turn {idx}` {label}: {instruction}")


def _render_latest_result() -> None:
    st.subheader("Latest Image")
    if not st.session_state.results:
        st.info("Run the first turn to generate an image.")
        return

    latest = st.session_state.results[-1]
    image_path = latest.get("image_path", "")
    if image_path and Path(image_path).exists():
        st.image(image_path, caption=f"Turn {latest['turn_index']}: {latest['instruction']}")
    else:
        st.warning("The latest result has no saved image.")


def _render_state_panels() -> None:
    tabs = st.tabs(["Memory", "Prompt", "Checklist", "Evaluation", "Logs"])
    latest = st.session_state.results[-1] if st.session_state.results else None

    with tabs[0]:
        st.json(st.session_state.memory)

    with tabs[1]:
        if latest:
            st.text_area("Positive prompt", latest["prompt"]["positive"], height=180)
            st.text_area("Negative prompt", latest["prompt"]["negative"], height=90)
        else:
            st.info("No prompt yet.")

    with tabs[2]:
        if latest:
            st.json(latest["checklist"])
        else:
            st.info("No checklist yet.")

    with tabs[3]:
        if latest:
            st.metric("Checklist score", latest["evaluation"].get("checklist_score", 0.0))
            st.json(latest["evaluation"])
        else:
            st.info("No evaluation yet.")

    with tabs[4]:
        st.write(f"Run directory: `{ROOT / 'outputs' / 'runs' / st.session_state.run_id}`")
        if latest:
            st.json(
                {
                    "turn": latest["turn_index"],
                    "image_path": latest["image_path"],
                    "run_dir": latest["run_dir"],
                }
            )


def _load_example() -> Dict[str, Any]:
    return json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))


def _result_to_state(result: TurnResult) -> Dict[str, Any]:
    return {
        "turn_index": result.turn_index,
        "instruction": result.instruction,
        "delta": result.delta,
        "memory": result.memory,
        "prompt": {
            "positive": result.prompt.positive,
            "negative": result.prompt.negative,
        },
        "checklist": result.checklist,
        "evaluation": result.evaluation,
        "image_path": str(result.image_path),
        "run_dir": str(result.run_dir),
    }


if __name__ == "__main__":
    main()
