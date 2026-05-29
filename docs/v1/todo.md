# Mem2Image v1 Remaining TODO

本文档记录 v1 之后的剩余工作，供下一阶段开发排期使用。当前优先级按课程项目目标排序：先增强可展示闭环，再补实验可信度，最后扩展更复杂功能。

## P0：跑通稳定性和可演示性

- 增加一个 `scripts/run_case.py`，支持命令行跑完整 4-turn case，避免只能依赖 Streamlit 点击。
- 增加 dry-run/mock 模式：不调用 API，也能展示 parser、memory、prompt、checklist 的流转。
- 增加 Manual Memory Editor：允许用户在 Streamlit 中手动编辑当前 Visual Intent Memory JSON，用于修正 LLM 漏抽取或误抽取的意图。
- 手动编辑后需要做 JSON 解析、`normalize_memory()` 校验和错误提示；校验通过后覆盖 `st.session_state.memory`，后续 prompt、checklist、evaluation 都基于修正后的 memory。
- 保存手动修正记录：至少记录修正前 memory、修正后 memory、修正时间和备注，方便报告中说明 human-in-the-loop correction。
- 为每轮输出增加 `models.json` 或在 `turn_log.json` 里记录当轮实际 LLM/VLM/Image 模型。
- 页面增加“下载本次 run zip”或“打开 run 目录”提示，方便收集报告素材。
- 页面支持展示历史轮次缩略图，而不是只展示最新一轮。
- 补充常见错误说明：`Model disabled`、余额不足、图片 URL 下载失败、VLM 输出非 JSON。

## P1：Prompt Repair / Retry

- 增加 Refiner Agent：根据 `failed_items` 生成 repair prompt。
- 支持每轮最多 retry 一次，并保存 retry 前后两张图。
- 页面展示 before/after 和 repair reason。
- 设计 retry 选择策略：如果 retry checklist score 更高，则采用 retry 图；否则保留原图并标记失败。
- 保存 `repair_prompt.txt`、`repair_evaluation.json`、`retry_image.png`。

## P1：Benchmark 和实验

- 扩展 `data/benchmark.json`，至少覆盖 10 个多轮案例，每个 4 轮。
- 覆盖 drift 类型：
  - object drift
  - attribute drift
  - scene drift
  - style drift
  - constraint drift
  - negative constraint violation
- 实现 baseline：
  - current-only
  - full-history
  - natural-language summary
  - ours memory
  - ours memory + repair
- 实现批量运行脚本，自动保存每个 method/case/turn 的输出。
- 汇总指标：
  - checklist score
  - failed item count
  - history constraint retention rate
  - current turn success rate
  - drift count
- 挑选 3-5 个高质量 qualitative case，用于报告和 PPT。

## P1：Memory 能力增强

- 增加更严格的 JSON schema 校验，减少 LLM 输出畸形导致的隐性错误。
- 增加冲突检测：例如用户先说 `red scarf`，后说 `blue scarf`，系统应记录替换原因。
- 增加对象属性级 remove：例如只移除 `red scarf`，而不是移除整个 dog。
- 为 memory 中每条对象、属性、约束记录来源 turn，方便解释和可视化。
- 增加 memory diff 展示：每轮新增、修改、删除了哪些内容。
- 区分硬约束和软偏好，例如 `must preserve` vs `prefer warm colors`。

## P2：图像生成与编辑扩展

- 增加 ComfyUI 后端，降低在线 API 额度和网络风险。
- 增加图像缓存：相同 prompt 可复用已生成图片，便于调试。
- 支持 image-to-image 或 inpainting，开始向真实 multi-turn editing 靠近。
- 引入 ControlNet/IP-Adapter 等保持主体姿态或构图的一致性。
- 支持用户上传初始图片，并将第一轮从 T2I 切换为编辑流程。

## P2：VLM Evaluation 增强

- 为 checklist item 增加权重，主体和 must-preserve 约束权重更高。
- 对 VLM 评价做多问法或二次确认，降低 yes/no 抖动。
- 输出 drift type，例如 `attribute_drift`、`scene_drift`、`style_drift`。
- 增加人工复核入口，让用户手动修正 VLM 判断。
- 将 failed item 映射回 memory 字段，方便 Refiner 精准修 prompt。

## P2：UI 和展示

- 增加 method selector，用同一案例对比 baseline 和 ours。
- 增加 memory timeline，展示每轮记住了什么。
- 增加 checklist 通过/失败的可视化标记。
- 增加 prompt 展开/折叠，避免页面信息过载。
- 准备离线 demo 包：固定图片、memory、evaluation，防止汇报现场 API 不稳定。
- 录制一段完整 4-turn demo 视频，作为汇报兜底材料。

## P2：报告和 PPT 素材

- 整理系统架构图：User -> Parser -> Memory -> Prompt -> Image -> Checklist -> VLM。
- 整理方法图：Visual Intent Memory 如何减少 intention drift。
- 整理 before/after 案例：baseline 忘记红围巾，ours 保留或检测失败。
- 整理定量表格模板。
- 整理 limitation：不是像素级一致、依赖 API/VLM、repair 不保证成功。
- 补齐引用：Talk2Image、GenPilot、VLM evaluation、T2I/editing 相关工作。

## P3：工程质量

- 将当前标准库 JSON 处理升级为 Pydantic 或 JSON Schema。
- 增加类型检查或 lint 配置。
- 增加 integration test，但默认跳过，需要 API key 时手动开启。
- 抽象 `ImageGenerator`、`LLMClient`、`VLMClient` 接口，为多 provider 做准备。
- 增加配置文件而不是只依赖 `.env` 和 sidebar。
- 清理旧的 `.venv`，统一使用 conda `visual` 环境。

## 下一阶段建议顺序

建议下一阶段按这个顺序推进：

1. 先做 `scripts/run_case.py` 和离线 demo 数据，确保可复现。
2. 再做 Refiner + retry，因为它最能强化课程展示的闭环感。
3. 然后做 10-case benchmark 和 baseline，对报告最有价值。
4. 最后再考虑 image editing、ComfyUI 和更复杂 UI。

不要一开始就上真实编辑或大规模实验。当前项目最有辨识度的是 **显式 Visual Intent Memory + Checklist-based Drift Detection**，下一阶段应优先把这两个点做强。
