# Mem2Image v1 Dev Log

本文档记录当前 v1 代码实现的架构、开发约定和关键细节，目标是让下一阶段开发者能快速接手，而不需要重新阅读全部代码。

## 1. 当前实现状态

当前代码已经完成第一阶段最小闭环：

```text
Streamlit UI
-> Orchestrator
-> Intent Parser LLM
-> Memory Updater
-> Prompt Composer
-> SiliconFlow Image Generation
-> Checklist Generator
-> VLM Evaluator
-> Run Logger
```

当前默认模型配置：

```bash
LLM_MODEL=Qwen/Qwen3-30B-A3B-Instruct-2507
VLM_MODEL=Qwen/Qwen3-VL-32B-Instruct
IMAGE_MODEL=Kwai-Kolors/Kolors
```

运行环境默认使用 conda：

```bash
conda activate visual
streamlit run app.py
```

## 2. 目录职责

```text
app.py                      Streamlit 入口
agents/                     Agent 层，负责意图解析、记忆更新、prompt、checklist、评价
core/                       核心 schema、调度器、日志保存
tools/                      外部服务 client 和配置读取
data/examples/              内置 demo case
outputs/runs/               每次运行的本地输出
tests/                      不依赖外部 API 的本地逻辑测试
docs/v1/                    v1 交接文档
```

关键文件：

- `core/orchestrator.py`：单轮 pipeline 的主调度入口。
- `core/schema.py`：memory、delta 的默认结构和 JSON 解析辅助函数。
- `tools/siliconflow_client.py`：SiliconFlow chat、vision、image generation 和图片下载封装。
- `agents/memory_updater.py`：确定性的 memory merge 逻辑，是当前最需要保护的核心模块。

## 3. 核心数据结构

### Visual Intent Memory

当前 memory schema：

```json
{
  "main_subjects": [],
  "objects": [],
  "scene": {},
  "style": {},
  "constraints": [],
  "negative_constraints": [],
  "current_turn_goal": "",
  "turn_history": []
}
```

约定：

- `main_subjects` 存主体对象，例如狗、人、城堡。
- `objects` 存非主体但需要出现的对象。
- `scene` 存背景、光照、天气、环境。
- `style` 存画风、媒介、色彩等。
- `constraints` 存必须保持的要求。
- `negative_constraints` 存不允许出现的元素。
- `turn_history` 存每轮指令和 delta，方便复盘。

### Delta

Intent Parser 每轮只输出 delta：

```json
{
  "add": {},
  "update": {},
  "remove": {},
  "current_turn_goal": "",
  "reason": ""
}
```

约定：

- `add` 表示新增对象、属性、风格、约束。
- `update` 表示明确替换或修改，例如换背景、换光照。
- `remove` 只用于用户明确要求删除的内容。
- LLM 不直接重写完整 memory。

## 4. Memory Merge 规则

Memory merge 当前由代码确定性完成，不完全交给 LLM。

已实现规则：

- 默认保留旧 memory。
- 同名对象按 `name` 合并。
- 对象 `attributes` 去重追加。
- 对象 `pose`、`position` 等非空字段会被新值覆盖。
- `scene`、`style` 字段按 key 更新。
- `constraints`、`negative_constraints` 去重追加。
- `remove` 可以删除对象、scene/style 字段或约束。
- 每轮都会追加一条 `turn_history`。

开发注意：

- 不要让 LLM 直接生成完整 memory 覆盖旧状态，除非后续专门设计版本迁移。
- 新增 memory 字段时，需要同时更新 schema normalize、prompt composer、checklist generator 和测试。
- 冲突策略目前很简单：明确 update 覆盖旧字段；复杂冲突留到后续阶段。

## 5. 外部 API 约定

当前只封装 SiliconFlow。

使用接口：

- `/chat/completions`：LLM intent parser。
- `/chat/completions` + image base64 data URL：VLM evaluator。
- `/images/generations`：T2I image generator。

错误处理约定：

- API key 缺失时给出可读错误。
- HTTP 错误中会显示实际请求的模型名和 endpoint。
- Orchestrator 会把失败阶段标记为 `intent_parser`、`image_generation` 或 `vlm_evaluator`。
- 每轮若失败，会写入 `outputs/runs/<run_id>/turn_XX/error.json`。

## 6. 日志产物

每轮成功后会保存：

```text
outputs/runs/<run_id>/turn_XX/
  delta.json
  memory.json
  prompt.txt
  checklist.json
  evaluation.json
  api_responses.json
  turn_log.json
  image.png
```

这些文件是后续实验、报告和 PPT 的基础素材。下一阶段做 benchmark 时，应优先复用这个落盘格式，不要重新发明一套日志结构。

## 7. UI 状态

Streamlit 当前支持：

- 在 sidebar 填 API key、base URL、LLM/VLM/Image model。
- 显示当前实际生效模型。
- 检测 LLM/VLM 是否疑似填反。
- 点击 `Run demo turn` 按顺序跑内置案例。
- 展示最新图像、memory、prompt、checklist、evaluation、run directory。

当前 UI 是开发和展示用，不是最终产品形态。后续可以优化排版，但不要破坏调试信息的可见性。

## 8. 测试约定

当前测试只覆盖本地逻辑，不调用外部 API：

```bash
conda run -n visual python -m unittest discover -s tests
```

已有测试覆盖：

- 红围巾狗 4 轮 memory merge 后，狗、红围巾、坐姿、雪林、暖光和保持约束都存在。
- Checklist 能从 memory 生成关键检查项。
- Negative prompt 与 positive prompt 分离。

新增功能时，优先补本地单元测试。真实 API 调用测试应单独做成手动或集成脚本，避免 CI/普通测试依赖额度和网络。

## 9. 当前技术债

- Memory schema 没有使用 Pydantic/JSON Schema 做强校验。
- Intent Parser 的 LLM 输出质量依赖 prompt，尚无 retry/fix-bad-json 策略以外的强恢复。
- Prompt Composer 仍偏模板化，图像质量和稳定性有提升空间。
- VLM Evaluator 的 yes/no 判断没有二次校验，可能受模型波动影响。
- Image Generator 只支持单一在线服务抽象，尚未支持 ComfyUI、本地模型或缓存复用。
- Streamlit session state 适合 demo，但不适合多人并发或长期实验。

## 10. 修改守则

- 保持 v1 最小闭环可运行：任意扩展都不应破坏单个 4-turn demo。
- 优先维护结构化 memory，不要退回自然语言 summary 作为核心状态。
- Prompt、checklist、evaluation 都应该能从 memory 追溯。
- 对外部模型的 model name、endpoint、错误阶段要显式记录。
- 运行产物默认写入 `outputs/runs/`，不要提交真实生成图片、API 响应或 `.env`。
