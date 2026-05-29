# Mem2Image v1 Pipeline

本文档描述当前 v1 阶段的 **T2I 多轮重生成业务流程**。这里不展开代码实现细节，重点说明用户、Agent、图像生成与评价之间的业务关系，方便下一阶段继续扩展功能。

## 1. 当前阶段目标

v1 的目标是跑通一个最小闭环：

```text
用户多轮视觉指令
-> 系统维护结构化视觉意图
-> 每轮根据当前意图重新生成图像
-> 系统检查图像是否满足当前累计意图
-> 页面展示图像、记忆、检查结果和日志
```

当前阶段只做 **text-to-image regeneration**，即每一轮都根据累计意图重新生成一张图。它不做真实局部编辑、不做 inpainting、不保证像素级跨轮一致性。

## 2. 业务角色

- 用户：通过自然语言逐轮描述想要的画面变化。
- Intent Parser：理解当前轮用户想新增、修改、删除或保留什么视觉要求。
- Visual Intent Memory：保存系统到当前为止理解到的累计视觉意图。
- Prompt Composer：把累计视觉意图整理成文生图模型可执行的描述。
- Image Generator：根据当前 prompt 生成图像。
- Checklist Generator：根据累计视觉意图生成一组可检查的问题。
- VLM Evaluator：查看生成图像并回答 checklist，判断是否出现意图遗漏。
- Demo UI：展示每轮图像、记忆、prompt、checklist 和评价结果。

## 3. 单轮业务流程

每一轮输入一条用户指令后，系统按以下顺序处理：

1. 读取当前用户指令。
2. 结合上一轮 Visual Intent Memory，解析当前轮新增或修改的视觉意图。
3. 将当前轮变化合并进 Visual Intent Memory。
4. 根据更新后的 memory 生成文生图 prompt。
5. 调用图像生成服务，得到当前轮图像。
6. 从 memory 自动生成 checklist。
7. 让 VLM 查看图像并逐条回答 checklist。
8. 在页面展示本轮结果，并保存本轮运行记录。

这条链路的核心思想是：**图像模型不直接负责记住历史，历史意图由显式 memory 维护。**

## 4. Visual Intent Memory 的业务含义

Visual Intent Memory 是当前项目的核心状态。它表达“到目前为止，用户希望画面里应该有什么”。

当前 memory 覆盖这些信息：

- 主体对象：例如 `dog`。
- 普通对象：例如 `book`、`vase`。
- 对象属性：例如 `wearing a red scarf`。
- 姿态和位置：例如 `sitting`、`center`。
- 场景：例如 `snowy forest`。
- 风格：例如 `watercolor`、`children's book illustration`。
- 保持约束：例如 `keep the red scarf`。
- 负向约束：例如 `no extra animals`。
- 当前轮目标：例如 `add warm lighting`。
- 多轮历史：记录每轮指令和系统理解到的变化。

默认业务规则是：**除非用户明确删除或替换，历史视觉要求会继续保留。**

## 5. 内置 Demo 流程

v1 内置的红围巾狗案例有 4 轮：

1. `Generate a dog sitting in a park.`
2. `Make the dog wear a red scarf.`
3. `Change the background to a snowy forest.`
4. `Add warm lighting, but keep the red scarf and dog pose.`

这个案例用于展示 intention drift 的典型场景：

- 第 2 轮新增红围巾属性。
- 第 3 轮替换背景时，红围巾应该继续保留。
- 第 4 轮新增暖光时，红围巾和坐姿都应该继续保留。

如果图像生成结果丢失红围巾、狗不再坐着、背景不是雪林，VLM checklist 应该能显式指出失败项。

## 6. 当前 v1 不包含的内容

以下内容属于后续阶段，不属于当前业务闭环：

- 真实 image editing 或局部 inpainting。
- 基于上一轮图像的区域保持。
- Prompt repair 和 retry。
- 多案例 benchmark。
- baseline 对比。
- 人工评价。
- 报告中的定量实验表格。

v1 的验收标准是：一个多轮 T2I 案例能完整走完 memory、prompt、image、checklist、VLM evaluation 和日志保存流程。
