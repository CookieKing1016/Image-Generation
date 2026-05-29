"""Single-turn orchestration for the first-stage demo."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from agents.checklist_generator import ChecklistGenerator
from agents.evaluator import ChecklistEvaluator
from agents.intent_parser import IntentParser
from agents.memory_updater import MemoryUpdater
from agents.prompt_composer import PromptBundle, PromptComposer
from core.run_logger import RunLogger, summarize_api_response
from core.schema import empty_memory, normalize_memory
from tools.config import Settings
from tools.siliconflow_client import SiliconFlowClient, first_image_url


@dataclass
class TurnResult:
    turn_index: int
    instruction: str
    delta: Dict[str, Any]
    memory: Dict[str, Any]
    prompt: PromptBundle
    checklist: List[Dict[str, Any]]
    evaluation: Dict[str, Any]
    image_path: Path
    run_dir: Path


class MemoryTalk2ImageOrchestrator:
    def __init__(self, settings: Settings, run_id: str = ""):
        self.client = SiliconFlowClient(settings)
        self.intent_parser = IntentParser(self.client)
        self.memory_updater = MemoryUpdater()
        self.prompt_composer = PromptComposer()
        self.checklist_generator = ChecklistGenerator()
        self.evaluator = ChecklistEvaluator(self.client)
        self.logger = RunLogger(run_id or None)

    @property
    def run_id(self) -> str:
        return self.logger.run_id

    @property
    def run_dir(self) -> Path:
        return self.logger.run_dir

    def run_turn(
        self,
        instruction: str,
        memory: Dict[str, Any] = None,
        turn_index: int = 1,
    ) -> TurnResult:
        current_memory = normalize_memory(memory or empty_memory())
        turn_dir = self.logger.turn_dir(turn_index)
        api_summary: Dict[str, Any] = {}

        try:
            delta = self.intent_parser.parse(instruction, current_memory)
        except Exception as exc:
            self.logger.save_error(turn_index, "intent_parser", exc)
            raise RuntimeError(f"[intent_parser] {exc}") from exc

        updated_memory = self.memory_updater.update(current_memory, delta, instruction)
        prompt = self.prompt_composer.compose(updated_memory)

        try:
            image_response = self.client.generate_image(prompt.generation_prompt)
            api_summary["image_generation"] = summarize_api_response(image_response)
            image_url = first_image_url(image_response)
            image_path = turn_dir / "image.png"
            self.client.download_file(image_url, image_path)
        except Exception as exc:
            self.logger.save_error(turn_index, "image_generation", exc)
            raise RuntimeError(f"[image_generation] {exc}") from exc

        checklist = self.checklist_generator.generate(updated_memory)

        try:
            evaluation = self.evaluator.evaluate(
                image_path=image_path,
                checklist=checklist,
                memory=updated_memory,
                prompt=prompt.positive,
            )
        except Exception as exc:
            self.logger.save_error(turn_index, "vlm_evaluator", exc)
            raise RuntimeError(f"[vlm_evaluator] {exc}") from exc

        self.logger.save_turn_artifacts(
            turn_index=turn_index,
            instruction=instruction,
            delta=delta,
            memory=updated_memory,
            prompt_positive=prompt.positive,
            prompt_negative=prompt.negative,
            checklist=checklist,
            evaluation=evaluation,
            image_path=image_path,
            api_summary=api_summary,
        )

        return TurnResult(
            turn_index=turn_index,
            instruction=instruction,
            delta=delta,
            memory=updated_memory,
            prompt=prompt,
            checklist=checklist,
            evaluation=evaluation,
            image_path=image_path,
            run_dir=self.logger.run_dir,
        )
