# Badcase JSON Analysis: memory_stress_full_v2_20260723

This report is generated from per-turn artifacts: delta.json, memory.json, prompt.txt, evaluation.json, and method_metadata.json.

## Findings

### current-only / background_only_dog / Turn 3

- Instruction: Change only the background to a snowy forest.
- Failed: dog_exists [object_retention/history]; dog_sitting [pose_retention/history]; red_scarf [attribute_drift/history]
- Evaluation reason: No dog is visible in the image; only a snowy forest is present. | No dog is present, so sitting pose cannot be verified. | No dog is visible, so no scarf can be observed.
- Attribution: 输入层 / baseline 设计层
- JSON evidence: method_metadata uses_history=false，prompt 只包含 current user request。 prompt 中没有完整历史约束，所以历史主体、背景、姿态或属性缺失是预期风险。 failed evaluation ids=dog_exists, dog_sitting, red_scarf metadata={"uses_history": false}
- Fix direction: current-only 只能作为弱 baseline；比较主实验时应标注它没有记忆输入。

### current-only / background_only_dog / Turn 4

- Instruction: Add warm lighting without changing the dog, scarf, or sitting pose.
- Failed: red_scarf [attribute_drift/history]; snowy_forest [scene_drift/history]
- Evaluation reason: The scarf is brown, not red, as requested in history. | The background is a plain, warm-toned gradient, not a snowy forest.
- Attribution: 输入层 / baseline 设计层
- JSON evidence: method_metadata uses_history=false，prompt 只包含 current user request。 prompt 中没有完整历史约束，所以历史主体、背景、姿态或属性缺失是预期风险。 failed evaluation ids=red_scarf, snowy_forest metadata={"uses_history": false}
- Fix direction: current-only 只能作为弱 baseline；比较主实验时应标注它没有记忆输入。

### current-only / count_conflict_balloons / Turn 2

- Instruction: Make one balloon red and one balloon yellow.
- Failed: child_exists [object_retention/history]
- Evaluation reason: No child is visible in the image; only two balloons are present.
- Attribution: 输入层 / baseline 设计层
- JSON evidence: method_metadata uses_history=false，prompt 只包含 current user request。 prompt 中没有完整历史约束，所以历史主体、背景、姿态或属性缺失是预期风险。 failed evaluation ids=child_exists metadata={"uses_history": false}
- Fix direction: current-only 只能作为弱 baseline；比较主实验时应标注它没有记忆输入。

### current-only / count_conflict_balloons / Turn 3

- Instruction: Change the count to exactly three balloons by adding one blue balloon.
- Failed: child_exists [object_retention/history]
- Evaluation reason: No child is visible in the image; only three balloons are present.
- Attribution: 输入层 / baseline 设计层
- JSON evidence: method_metadata uses_history=false，prompt 只包含 current user request。 prompt 中没有完整历史约束，所以历史主体、背景、姿态或属性缺失是预期风险。 failed evaluation ids=child_exists metadata={"uses_history": false}
- Fix direction: current-only 只能作为弱 baseline；比较主实验时应标注它没有记忆输入。

### current-only / negative_constraint_teacher / Turn 2

- Instruction: Make the robot hold a red textbook.
- Failed: blackboard [scene_drift/history]
- Evaluation reason: The background shows a laboratory or office setting with microscopes and monitors, but no classroom blackboard is visible.
- Attribution: 输入层 / baseline 设计层
- JSON evidence: method_metadata uses_history=false，prompt 只包含 current user request。 prompt 中没有完整历史约束，所以历史主体、背景、姿态或属性缺失是预期风险。 failed evaluation ids=blackboard metadata={"uses_history": false}
- Fix direction: current-only 只能作为弱 baseline；比较主实验时应标注它没有记忆输入。

### current-only / negative_constraint_teacher / Turn 3

- Instruction: Use children's book illustration style.
- Failed: red_textbook [attribute_drift/history]; robot_teacher [object_retention/history]
- Evaluation reason: The child is holding a blue book with illustrations; no red textbook is visible. | The main subject is a child reading a book, not a teacher robot.
- Attribution: 输入层 / baseline 设计层
- JSON evidence: method_metadata uses_history=false，prompt 只包含 current user request。 prompt 中没有完整历史约束，所以历史主体、背景、姿态或属性缺失是预期风险。 failed evaluation ids=robot_teacher, red_textbook metadata={"uses_history": false}
- Fix direction: current-only 只能作为弱 baseline；比较主实验时应标注它没有记忆输入。

### current-only / negative_constraint_teacher / Turn 4

- Instruction: Keep the red textbook and classroom, but do not include readable text on the blackboard.
- Failed: robot_teacher [object_retention/history]
- Evaluation reason: No robot is visible in the image; only a classroom with desks and a red textbook.
- Attribution: 输入层 / baseline 设计层
- JSON evidence: method_metadata uses_history=false，prompt 只包含 current user request。 prompt 中没有完整历史约束，所以历史主体、背景、姿态或属性缺失是预期风险。 failed evaluation ids=robot_teacher metadata={"uses_history": false}
- Fix direction: current-only 只能作为弱 baseline；比较主实验时应标注它没有记忆输入。

### current-only / object_replacement_wolf_dog / Turn 2

- Instruction: Replace the wolf with a black dog.
- Failed: snow [scene_drift/history]
- Evaluation reason: The background shows dark forest ground and trees, no snow is visible.
- Attribution: 输入层 / baseline 设计层
- JSON evidence: method_metadata uses_history=false，prompt 只包含 current user request。 prompt 中没有完整历史约束，所以历史主体、背景、姿态或属性缺失是预期风险。 failed evaluation ids=snow metadata={"uses_history": false}
- Fix direction: current-only 只能作为弱 baseline；比较主实验时应标注它没有记忆输入。

### current-only / object_replacement_wolf_dog / Turn 4

- Instruction: Add a blue collar to the dog while keeping it on the left in the snow.
- Failed: black_dog [object_conflict/history]
- Evaluation reason: The dog is primarily gray and brown with white markings, not black.
- Attribution: 输入层 / baseline 设计层
- JSON evidence: method_metadata uses_history=false，prompt 只包含 current user request。 prompt 中没有完整历史约束，所以历史主体、背景、姿态或属性缺失是预期风险。 failed evaluation ids=black_dog metadata={"uses_history": false}
- Fix direction: current-only 只能作为弱 baseline；比较主实验时应标注它没有记忆输入。

### current-only / scarf_color_conflict_fox / Turn 3

- Instruction: Change the scarf to a blue scarf, replacing the red scarf.
- Failed: fox_exists [object_retention/history]
- Evaluation reason: Image shows only a folded blue fabric, no fox is visible.
- Attribution: 输入层 / baseline 设计层
- JSON evidence: method_metadata uses_history=false，prompt 只包含 current user request。 prompt 中没有完整历史约束，所以历史主体、背景、姿态或属性缺失是预期风险。 failed evaluation ids=fox_exists metadata={"uses_history": false}
- Fix direction: current-only 只能作为弱 baseline；比较主实验时应标注它没有记忆输入。

### current-only / scarf_color_conflict_fox / Turn 4

- Instruction: Add light snow while keeping the blue scarf and autumn leaves.
- Failed: fox_exists [object_retention/history]
- Evaluation reason: The main subject is a woman, not a fox. No fox is visible in the image.
- Attribution: 输入层 / baseline 设计层
- JSON evidence: method_metadata uses_history=false，prompt 只包含 current user request。 prompt 中没有完整历史约束，所以历史主体、背景、姿态或属性缺失是预期风险。 failed evaluation ids=fox_exists metadata={"uses_history": false}
- Fix direction: current-only 只能作为弱 baseline；比较主实验时应标注它没有记忆输入。

### pullprompt / object_replacement_wolf_dog / Turn 3

- Instruction: Move the black dog to the left side of the image.
- Failed: dog_left [spatial_relation/current]
- Evaluation reason: The black dog is centered in the image, not positioned on the left side.
- Attribution: 模型能力层 / 空间关系执行失败
- JSON evidence: prompt 已包含 move left / keeping it on the left，但 evaluation 判断主体仍居中。 failed evaluation ids=dog_left metadata={"uses_history": true, "history_turns": 3}
- Fix direction: 加入空间关系检查后的重试，或升级为局部编辑/布局控制。

### structured-memory / material_conflict_vase / Turn 3

- Instruction: Change the vase material to white ceramic instead of glass.
- Failed: purple_flowers [attribute_drift/history]
- Evaluation reason: The flowers are red, yellow, and white with purple tips, not fully purple as previously requested.
- Attribution: 策略与意图层 / 记忆冲突合并错误
- JSON evidence: present=clear glass vase, white ceramic, clear glass memory 保留旧对象名或旧约束，导致 prompt 同时表达 glass 与 ceramic。 failed evaluation ids=purple_flowers delta keys=add, update, remove, current_turn_goal, reason metadata={"uses_history": true, "memory_keys": ["main_subjects", "objects", "scene", "style", "constraints", "negative_constraints", "current_turn_goal", "turn_history"]}
- Fix direction: 更新 memory merge：replacement 要覆盖对象 name、attributes 和 constraints，旧材质约束应 supersede/delete。

### structured-memory / material_conflict_vase / Turn 4

- Instruction: Add rain visible through a window behind the table, keeping the ceramic vase and three purple flowers.
- Failed: ceramic_vase [material_conflict/history]; purple_flowers [attribute_drift/history]
- Evaluation reason: The vase is transparent glass with a white ceramic base, not entirely white ceramic as required. | Only one flower has purple edges; the other two are red and yellow, not purple.
- Attribution: 策略与意图层 / 记忆冲突合并错误
- JSON evidence: present=clear glass vase, white ceramic, clear glass memory 保留旧对象名或旧约束，导致 prompt 同时表达 glass 与 ceramic。 failed evaluation ids=ceramic_vase, purple_flowers delta keys=add, update, remove, current_turn_goal, reason metadata={"uses_history": true, "memory_keys": ["main_subjects", "objects", "scene", "style", "constraints", "negative_constraints", "current_turn_goal", "turn_history"]}
- Fix direction: 更新 memory merge：replacement 要覆盖对象 name、attributes 和 constraints，旧材质约束应 supersede/delete。

### structured-memory / negative_constraint_teacher / Turn 4

- Instruction: Keep the red textbook and classroom, but do not include readable text on the blackboard.
- Failed: no_readable_text [negative_constraint/current]
- Evaluation reason: The blackboard contains large, legible chalk writing including 'ABC', 'Y22C', and 'aid 2100', which violates the negative constraint.
- Attribution: 输出格式层 / 模型生成层
- JSON evidence: present=do not include readable text, text artifacts JSON/prompt 已有禁止文字，失败来自图像模型常见的文字伪影控制不足。 failed evaluation ids=no_readable_text delta keys=add, update, remove, current_turn_goal, reason metadata={"uses_history": true, "memory_keys": ["main_subjects", "objects", "scene", "style", "constraints", "negative_constraints", "current_turn_goal", "turn_history"]}
- Fix direction: 对 text/no-text 加 VLM 检查后重试，或 prompt 中加入 blank blackboard / no letters / no symbols。

### structured-memory / object_addition_wallet / Turn 3

- Instruction: Put a small white flower on the wallet.
- Failed: no_credit_card [object_removal/history]
- Evaluation reason: A credit card is partially visible, extending from the right side of the wallet, violating the constraint to remove it.
- Attribution: 策略与意图层 / 删除约束保留不强
- JSON evidence: present=credit card, remove; missing=no credit card evaluation 显示信用卡残留；若 prompt 仍弱化删除约束，生成模型会复现初始物体。 failed evaluation ids=no_credit_card delta keys=add, update, remove, current_turn_goal, reason metadata={"uses_history": true, "memory_keys": ["main_subjects", "objects", "scene", "style", "constraints", "negative_constraints", "current_turn_goal", "turn_history"]}
- Fix direction: 把 remove 转成 active negative constraint，并在 prompt 中提升为 hard constraint；更好是对信用卡区域做 inpainting。

### structured-memory / scarf_color_conflict_fox / Turn 4

- Instruction: Add light snow while keeping the blue scarf and autumn leaves.
- Failed: no_red_scarf [attribute_conflict/history]
- Evaluation reason: The fox is wearing a red scarf underneath the blue scarf, which violates the constraint to remove the red scarf.
- Attribution: 策略与意图层 / 冲突属性未彻底覆盖
- JSON evidence: present=red scarf, blue scarf evaluation 看到红围巾残留，说明替换类属性没有局部删除旧属性。 failed evaluation ids=no_red_scarf delta keys=add, update, remove, current_turn_goal, reason metadata={"uses_history": true, "memory_keys": ["main_subjects", "objects", "scene", "style", "constraints", "negative_constraints", "current_turn_goal", "turn_history"]}
- Fix direction: 冲突属性采用 latest-wins：blue scarf supersedes red scarf，并显式加入 no red scarf hard negative。
