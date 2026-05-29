# Mem2Image

First-stage course prototype for a training-free, multi-turn text-to-image agent with explicit Visual Intent Memory.

This stage only supports T2I regeneration. Each turn updates a structured memory, composes a generation prompt, calls SiliconFlow image generation, then asks a VLM to evaluate a memory-derived checklist.

## Setup

```bash
conda create -y -n visual python=3.10
conda activate visual
python -m pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set:

```bash
SILICONFLOW_API_KEY=your_api_key_here
```

Model names can be changed in `.env` if a default model is unavailable on your account.
If SiliconFlow returns `Model disabled`, replace the corresponding model in
`.env` with a model enabled for your account. The current default is:

```bash
LLM_MODEL=Qwen/Qwen3-30B-A3B-Instruct-2507
VLM_MODEL=Qwen/Qwen3-VL-32B-Instruct
IMAGE_MODEL=Kwai-Kolors/Kolors
```

## Run

```bash
conda activate visual
streamlit run app.py
```

The built-in demo case is:

1. `Generate a dog sitting in a park.`
2. `Make the dog wear a red scarf.`
3. `Change the background to a snowy forest.`
4. `Add warm lighting, but keep the red scarf and dog pose.`

For each turn, artifacts are saved under:

```text
outputs/runs/<run_id>/turn_XX/
```

Each turn directory contains `memory.json`, `prompt.txt`, `checklist.json`, `evaluation.json`, `delta.json`, `api_responses.json`, `turn_log.json`, and `image.png`.

## Validate Local Logic

These tests do not call external APIs:

```bash
python3 -m unittest discover -s tests
```

## Current Stage Boundaries

- No image editing or inpainting.
- No repair/retry loop.
- No baselines or benchmark experiments.
- No human evaluation table.
- API errors are surfaced in Streamlit, and completed turn logs are kept.
