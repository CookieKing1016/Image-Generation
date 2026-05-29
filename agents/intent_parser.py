"""LLM-backed current-turn intent parsing."""

from __future__ import annotations

from typing import Any, Dict

from core.schema import extract_json_object, json_dumps, normalize_delta
from tools.siliconflow_client import SiliconFlowClient, first_message_text


SYSTEM_PROMPT = """You are the Intent Parser for MemoryTalk2Image.
Your job is to convert the current user instruction into a JSON delta for a
structured visual memory. The system keeps old visual requirements by default,
so only output changes explicitly requested in the current turn.

Return strict JSON with exactly these top-level keys:
{
  "add": {},
  "update": {},
  "remove": {},
  "current_turn_goal": "",
  "reason": ""
}

Allowed memory fields are:
- main_subjects: list of objects. Each object may contain name, attributes,
  pose, position, must_preserve.
- objects: list of secondary visible objects.
- scene: object with fields such as background, lighting, weather, environment.
- style: object with fields such as visual_style, color_palette, medium.
- constraints: list of strings for requirements that must be preserved.
- negative_constraints: list of strings for disallowed elements.

Rules:
- Use "add" for newly introduced objects, attributes, styles, constraints, or
  negative constraints.
- Use "update" for explicit replacement/change instructions, such as changing
  the background or lighting.
- Use "remove" only when the user explicitly asks to remove something.
- If the user says "keep" or "preserve", add a natural-language constraint and
  set must_preserve when it targets a known subject.
- Do not rewrite the whole memory.
- Do not include commentary outside JSON.
"""


class IntentParser:
    def __init__(self, client: SiliconFlowClient):
        self.client = client

    def parse(self, instruction: str, memory: Dict[str, Any]) -> Dict[str, Any]:
        user_prompt = (
            "Current Visual Intent Memory:\n"
            f"{json_dumps(memory)}\n\n"
            "Current user instruction:\n"
            f"{instruction}\n\n"
            "Return only the delta JSON."
        )
        response = self.client.chat_completion(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
            max_tokens=1600,
        )
        parsed = extract_json_object(first_message_text(response))
        return normalize_delta(parsed)

