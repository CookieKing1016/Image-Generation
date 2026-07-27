# Mem2Image

Training-free, multi-turn image generation and editing agent with explicit Visual Intent Memory.

The first turn uses text-to-image generation. Later turns resolve memory
conflicts, plan edit tasks, build one mask per task, and route to reference
editing or native inpainting. Benchmark mode evaluates a memory-derived
checklist and can retry failed edits.

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
MEM2IMAGE_ADMIN_PASSWORD=change-this-before-deploy
```

Model names can be changed in `.env` if a default model is unavailable on your account.
If SiliconFlow returns `Model disabled`, replace the corresponding model in
`.env` with a model enabled for your account. The current default is:

```bash
LLM_MODEL=Qwen/Qwen3-30B-A3B-Instruct-2507
VLM_MODEL=Qwen/Qwen3-VL-32B-Instruct
IMAGE_MODEL=Kwai-Kolors/Kolors
IMAGE_EDIT_MODEL=Qwen/Qwen-Image-Edit
```

Set `IMAGE_INPAINT_MODEL` only to a model on your provider that natively accepts
both `image` and `mask`. When it is empty, masked turns use reference editing
followed by local compositing.

For AI/ML API FLUX.1 Fill:

```bash
AIMLAPI_API_KEY=your_aimlapi_key
AIMLAPI_BASE_URL=https://api.aimlapi.com/v1
IMAGE_INPAINT_PROVIDER=aimlapi
IMAGE_INPAINT_MODEL=blackforestlabs/flux-fill
```

SiliconFlow continues to serve chat, vision, generation, and reference editing.
Only native masked inpainting is sent to AI/ML API. The generated SAM2 mask is
converted to a strict black-white PNG before it is submitted to FLUX.1 Fill.

Optional local SAM2 refinement:

```bash
SEGMENTATION_BACKEND=sam2
SAM2_CHECKPOINT=/absolute/path/to/sam2_checkpoint.pt
SAM2_MODEL_CONFIG=configs/sam2.1/your_model.yaml
SAM2_DEVICE=mps
```

The project now has a local `.venv-sam2` environment with SAM2.1 Hiera-Tiny
enabled on Apple Silicon through MPS. The checkpoint is intentionally ignored
by Git. If that environment is unavailable, the mask planner records and uses
the VLM bounding-box fallback.

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

Each turn directory also contains `task_plan.json`, `agent_events.json`,
task-level masks, the union `mask.png`, and refinement candidates when those
stages are used.

## Editing Architecture

Visual entities keep a stable `entity_id`, active attributes, `attribute_slots`,
slot history, provenance, preserve constraints, and deleted tombstones. A newer
value in the same slot supersedes the old value, removes stale positive
constraints, and creates a negative residual constraint for evaluation.

Each task in the edit DAG owns a separate mask:

- attribute/remove/move: VLM target box, optionally refined to a SAM2 silhouette;
- add object: position-prior mask;
- background/style: inverse of protected subject masks.

The task masks are persisted separately and unioned into the final edit mask.
Native inpainting receives `source image + union mask + instruction + negative
prompt`. If no native model is configured, the system uses reference image
editing and local compositing. If no editor is available, it records an explicit
full-generation fallback.

Superseded attributes create critical `old_attribute_residual` checks. In
interactive mode only these high-risk replacement turns are evaluated
synchronously and retried with the same union mask; ordinary generation remains
unblocked. Set `RESIDUAL_AUTO_RETRY=false` to keep all interactive evaluation in
the background.

The app also writes searchable run metadata to:

```text
outputs/mem2image.sqlite3
```

Images and raw per-turn artifacts stay in `outputs/runs/`; SQLite stores paths,
scores, prompts, JSON payloads, and checklist item results for filtering,
dashboarding, and bad-case analysis.

To import existing file-based runs into SQLite:

```bash
python3 scripts/import_runs.py
```

## SQLite Backend

The lightweight backend uses these tables:

- `runs`: one row per multi-turn run, with `run_id`, method, case id, and run directory.
- `turns`: one row per turn, with instruction, image path, prompts, score, failed count, and JSON snapshots.
- `checklist_items`: one row per checklist item, joined with VLM answers and pass/fail status.
- `errors`: parser, image generation, or evaluator failures.

This keeps the prototype simple: the filesystem remains the artifact store, and
SQLite becomes the query layer for historical analysis.

The evaluation dashboard is admin-only in the Streamlit app. Set the admin
password in `.env`:

```bash
MEM2IMAGE_ADMIN_PASSWORD=your_admin_password
```

If the variable is missing during local development, the fallback password is
`admin`. Do not deploy with the fallback.

## First-Round Benchmark

The first benchmark set is defined in:

```text
data/benchmark.json
```

It contains 10 cases with 4 turns each. Every turn includes an evaluation
checklist with `source` labels (`current` or `history`) and drift categories.

Run a no-API smoke test:

```bash
python3 scripts/run_benchmark.py --dry-run --methods current-only full-history --case-limit 1
```

Run the first real comparison after setting `SILICONFLOW_API_KEY`:

```bash
python3 scripts/run_benchmark.py \
  --methods current-only full-history structured-memory
```

Summarize method-level metrics:

```bash
python3 scripts/summarize_benchmark.py
```

First-round methods:

- `current-only`: uses only the current user instruction.
- `full-history`: concatenates all instructions so far.
- `structured-memory`: uses the project Visual Intent Memory pipeline.

First-round metrics:

- `avg_checklist_score`: mean of per-turn checklist scores. Each turn score is passed checklist items divided by all checklist items.
- `history_retention_rate`: v2-style per-turn preservation score. For each turn, score historical/cumulative items (`source=history`, or legacy items whose type is not `current_turn`) as passed history items divided by all history items; if a turn has no history item, it counts as `1.0`. The method score is the mean across turns.
- `current_turn_success_rate`: v2-style per-turn binary success. For each turn, all current items (`source=current` or `type=current_turn`) must pass; otherwise the turn counts as `0.0`. If a turn has no current item, it counts as `1.0`. The method score is the fraction of successful turns.
- `critical_success_rate`: pass rate over checklist items marked `critical=true`.
- `drift_count`: number of failed checklist items.

This follows the v2 evaluation idea: first judge each visual checklist item with
the VLM, then separate cumulative-intent retention from current-turn success
before aggregating by method.

## Validate Local Logic

These tests do not call external APIs:

```bash
python3 -m unittest discover -s tests
```

## Current Stage Boundaries

- SAM2.1 Hiera-Tiny is installed and enabled locally through MPS; another
  machine still needs to install its runtime and checkpoint separately.
- Native inpainting is implemented through a provider-neutral request boundary
  and remains inactive until `IMAGE_INPAINT_MODEL` names a compatible model.
- VLM residual detection and automatic edit retry run for all benchmark turns
  and for high-risk superseded-attribute edits in interactive mode.
- No human evaluation table is included yet.
