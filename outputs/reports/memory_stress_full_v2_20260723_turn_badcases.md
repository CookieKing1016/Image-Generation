# Per-turn Evaluation Matrix: memory_stress_full_v2_20260723

- Total turns: 101
- Bad turns: 17

## Badcase Index

| method | case_id | turn_index | status | checklist_score | history_retention | current_success | failed_items | failed_reasons | instruction |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| current-only | background_only_dog | 3 | BAD | 0.25 | 0.0 | 1.0 | dog_exists [object_retention/history]; dog_sitting [pose_retention/history]; red_scarf [attribute_drift/history] | No dog is visible in the image; only a snowy forest is present. / No dog is present, so sitting pose cannot be verified. / No dog is visible, so no scarf can be observed. | Change only the background to a snowy forest. |
| current-only | background_only_dog | 4 | BAD | 0.6 | 0.5 | 1.0 | red_scarf [attribute_drift/history]; snowy_forest [scene_drift/history] | The scarf is brown, not red, as requested in history. / The background is a plain, warm-toned gradient, not a snowy forest. | Add warm lighting without changing the dog, scarf, or sitting pose. |
| current-only | count_conflict_balloons | 2 | BAD | 0.6667 | 0.5 | 1.0 | child_exists [object_retention/history] | No child is visible in the image; only two balloons are present. | Make one balloon red and one balloon yellow. |
| current-only | count_conflict_balloons | 3 | BAD | 0.6667 | 0.0 | 1.0 | child_exists [object_retention/history] | No child is visible in the image; only three balloons are present. | Change the count to exactly three balloons by adding one blue balloon. |
| current-only | negative_constraint_teacher | 2 | BAD | 0.6667 | 0.5 | 1.0 | blackboard [scene_drift/history] | The background shows a laboratory or office setting with microscopes and monitors, but no classroom blackboard is visible. | Make the robot hold a red textbook. |
| current-only | negative_constraint_teacher | 3 | BAD | 0.3333 | 0.0 | 1.0 | red_textbook [attribute_drift/history]; robot_teacher [object_retention/history] | The child is holding a blue book with illustrations; no red textbook is visible. / The main subject is a child reading a book, not a teacher robot. | Use children's book illustration style. |
| current-only | negative_constraint_teacher | 4 | BAD | 0.75 | 0.6667 | 1.0 | robot_teacher [object_retention/history] | No robot is visible in the image; only a classroom with desks and a red textbook. | Keep the red textbook and classroom, but do not include readable text on the blackboard. |
| current-only | object_replacement_wolf_dog | 2 | BAD | 0.6667 | 0.0 | 1.0 | snow [scene_drift/history] | The background shows dark forest ground and trees, no snow is visible. | Replace the wolf with a black dog. |
| current-only | object_replacement_wolf_dog | 4 | BAD | 0.75 | 0.6667 | 1.0 | black_dog [object_conflict/history] | The dog is primarily gray and brown with white markings, not black. | Add a blue collar to the dog while keeping it on the left in the snow. |
| current-only | scarf_color_conflict_fox | 3 | BAD | 0.6667 | 0.0 | 1.0 | fox_exists [object_retention/history] | Image shows only a folded blue fabric, no fox is visible. | Change the scarf to a blue scarf, replacing the red scarf. |
| current-only | scarf_color_conflict_fox | 4 | BAD | 0.75 | 0.6667 | 1.0 | fox_exists [object_retention/history] | The main subject is a woman, not a fox. No fox is visible in the image. | Add light snow while keeping the blue scarf and autumn leaves. |
| pullprompt | object_replacement_wolf_dog | 3 | BAD | 0.6667 | 1.0 | 0.0 | dog_left [spatial_relation/current] | The black dog is centered in the image, not positioned on the left side. | Move the black dog to the left side of the image. |
| structured-memory | material_conflict_vase | 3 | BAD | 0.75 | 0.5 | 1.0 | purple_flowers [attribute_drift/history] | The flowers are red, yellow, and white with purple tips, not fully purple as previously requested. | Change the vase material to white ceramic instead of glass. |
| structured-memory | material_conflict_vase | 4 | BAD | 0.5 | 0.3333 | 1.0 | ceramic_vase [material_conflict/history]; purple_flowers [attribute_drift/history] | The vase is transparent glass with a white ceramic base, not entirely white ceramic as required. / Only one flower has purple edges; the other two are red and yellow, not purple. | Add rain visible through a window behind the table, keeping the ceramic vase and three purple flowers. |
| structured-memory | negative_constraint_teacher | 4 | BAD | 0.75 | 1.0 | 0.0 | no_readable_text [negative_constraint/current] | The blackboard contains large, legible chalk writing including 'ABC', 'Y22C', and 'aid 2100', which violates the negative constraint. | Keep the red textbook and classroom, but do not include readable text on the blackboard. |
| structured-memory | object_addition_wallet | 3 | BAD | 0.6667 | 0.5 | 1.0 | no_credit_card [object_removal/history] | A credit card is partially visible, extending from the right side of the wallet, violating the constraint to remove it. | Put a small white flower on the wallet. |
| structured-memory | scarf_color_conflict_fox | 4 | BAD | 0.75 | 0.6667 | 1.0 | no_red_scarf [attribute_conflict/history] | The fox is wearing a red scarf underneath the blue scarf, which violates the constraint to remove the red scarf. | Add light snow while keeping the blue scarf and autumn leaves. |

## All Turns

| method | case_id | turn_index | status | checklist_score | history_retention | current_success | failed_items | instruction |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| current-only | background_only_dog | 1 | OK | 1.0 | 1.0 | 1.0 | - | Generate a dog sitting in the center of a park. |
| current-only | background_only_dog | 2 | OK | 1.0 | 1.0 | 1.0 | - | Make the dog wear a red scarf. |
| current-only | background_only_dog | 3 | BAD | 0.25 | 0.0 | 1.0 | dog_exists [object_retention/history]; dog_sitting [pose_retention/history]; red_scarf [attribute_drift/history] | Change only the background to a snowy forest. |
| current-only | background_only_dog | 4 | BAD | 0.6 | 0.5 | 1.0 | red_scarf [attribute_drift/history]; snowy_forest [scene_drift/history] | Add warm lighting without changing the dog, scarf, or sitting pose. |
| current-only | count_conflict_balloons | 1 | OK | 1.0 | 1.0 | 1.0 | - | Generate a child holding exactly two balloons. |
| current-only | count_conflict_balloons | 2 | BAD | 0.6667 | 0.5 | 1.0 | child_exists [object_retention/history] | Make one balloon red and one balloon yellow. |
| current-only | count_conflict_balloons | 3 | BAD | 0.6667 | 0.0 | 1.0 | child_exists [object_retention/history] | Change the count to exactly three balloons by adding one blue balloon. |
| current-only | count_conflict_balloons | 4 | OK | 1.0 | 1.0 | 1.0 | - | Put the child on a beach, keeping exactly three balloons and no extra balloons. |
| current-only | negative_constraint_teacher | 1 | OK | 1.0 | 1.0 | 1.0 | - | Generate a teacher robot standing beside a classroom blackboard. |
| current-only | negative_constraint_teacher | 2 | BAD | 0.6667 | 0.5 | 1.0 | blackboard [scene_drift/history] | Make the robot hold a red textbook. |
| current-only | negative_constraint_teacher | 3 | BAD | 0.3333 | 0.0 | 1.0 | red_textbook [attribute_drift/history]; robot_teacher [object_retention/history] | Use children's book illustration style. |
| current-only | negative_constraint_teacher | 4 | BAD | 0.75 | 0.6667 | 1.0 | robot_teacher [object_retention/history] | Keep the red textbook and classroom, but do not include readable text on the blackboard. |
| current-only | object_addition_wallet | 1 | OK | 1.0 | 1.0 | 1.0 | - | Generate a black leather wallet on a marble countertop with a credit card partially sticking out. |
| current-only | object_replacement_wolf_dog | 1 | OK | 1.0 | 1.0 | 1.0 | - | Generate a gray wolf standing in the snow. |
| current-only | object_replacement_wolf_dog | 2 | BAD | 0.6667 | 0.0 | 1.0 | snow [scene_drift/history] | Replace the wolf with a black dog. |
| current-only | object_replacement_wolf_dog | 3 | OK | 1.0 | 1.0 | 1.0 | - | Move the black dog to the left side of the image. |
| current-only | object_replacement_wolf_dog | 4 | BAD | 0.75 | 0.6667 | 1.0 | black_dog [object_conflict/history] | Add a blue collar to the dog while keeping it on the left in the snow. |
| current-only | scarf_color_conflict_fox | 1 | OK | 1.0 | 1.0 | 1.0 | - | Generate a fox standing in autumn leaves. |
| current-only | scarf_color_conflict_fox | 2 | OK | 1.0 | 1.0 | 1.0 | - | Make the fox wear a red scarf. |
| current-only | scarf_color_conflict_fox | 3 | BAD | 0.6667 | 0.0 | 1.0 | fox_exists [object_retention/history] | Change the scarf to a blue scarf, replacing the red scarf. |
| current-only | scarf_color_conflict_fox | 4 | BAD | 0.75 | 0.6667 | 1.0 | fox_exists [object_retention/history] | Add light snow while keeping the blue scarf and autumn leaves. |
| pullprompt | background_only_dog | 1 | OK | 1.0 | 1.0 | 1.0 | - | Generate a dog sitting in the center of a park. |
| pullprompt | background_only_dog | 2 | OK | 1.0 | 1.0 | 1.0 | - | Make the dog wear a red scarf. |
| pullprompt | background_only_dog | 3 | OK | 1.0 | 1.0 | 1.0 | - | Change only the background to a snowy forest. |
| pullprompt | background_only_dog | 4 | OK | 1.0 | 1.0 | 1.0 | - | Add warm lighting without changing the dog, scarf, or sitting pose. |
| pullprompt | count_conflict_balloons | 1 | OK | 1.0 | 1.0 | 1.0 | - | Generate a child holding exactly two balloons. |
| pullprompt | count_conflict_balloons | 2 | OK | 1.0 | 1.0 | 1.0 | - | Make one balloon red and one balloon yellow. |
| pullprompt | count_conflict_balloons | 3 | OK | 1.0 | 1.0 | 1.0 | - | Change the count to exactly three balloons by adding one blue balloon. |
| pullprompt | count_conflict_balloons | 4 | OK | 1.0 | 1.0 | 1.0 | - | Put the child on a beach, keeping exactly three balloons and no extra balloons. |
| pullprompt | material_conflict_vase | 1 | OK | 1.0 | 1.0 | 1.0 | - | Generate a clear glass vase with exactly three flowers on a wooden table. |
| pullprompt | material_conflict_vase | 2 | OK | 1.0 | 1.0 | 1.0 | - | Make the flowers purple. |
| pullprompt | material_conflict_vase | 3 | OK | 1.0 | 1.0 | 1.0 | - | Change the vase material to white ceramic instead of glass. |
| pullprompt | material_conflict_vase | 4 | OK | 1.0 | 1.0 | 1.0 | - | Add rain visible through a window behind the table, keeping the ceramic vase and three purple flowers. |
| pullprompt | negative_constraint_teacher | 1 | OK | 1.0 | 1.0 | 1.0 | - | Generate a teacher robot standing beside a classroom blackboard. |
| pullprompt | negative_constraint_teacher | 2 | OK | 1.0 | 1.0 | 1.0 | - | Make the robot hold a red textbook. |
| pullprompt | negative_constraint_teacher | 3 | OK | 1.0 | 1.0 | 1.0 | - | Use children's book illustration style. |
| pullprompt | negative_constraint_teacher | 4 | OK | 1.0 | 1.0 | 1.0 | - | Keep the red textbook and classroom, but do not include readable text on the blackboard. |
| pullprompt | negative_extra_performers | 1 | OK | 1.0 | 1.0 | 1.0 | - | Generate a robot playing a violin on a stage. |
| pullprompt | negative_extra_performers | 2 | OK | 1.0 | 1.0 | 1.0 | - | Make the violin golden. |
| pullprompt | negative_extra_performers | 3 | OK | 1.0 | 1.0 | 1.0 | - | Do not add any extra performers. |
| pullprompt | negative_extra_performers | 4 | OK | 1.0 | 1.0 | 1.0 | - | Add blue spotlights, keeping the robot playing the golden violin with no extra performers. |
| pullprompt | object_addition_wallet | 1 | OK | 1.0 | 1.0 | 1.0 | - | Generate a black leather wallet on a marble countertop with a credit card partially sticking out. |
| pullprompt | object_addition_wallet | 2 | OK | 1.0 | 1.0 | 1.0 | - | Remove the credit card from the wallet, but keep the wallet. |
| pullprompt | object_addition_wallet | 3 | OK | 1.0 | 1.0 | 1.0 | - | Put a small white flower on the wallet. |
| pullprompt | object_addition_wallet | 4 | OK | 1.0 | 1.0 | 1.0 | - | Add soft studio lighting while keeping the flower on the wallet and no credit card. |
| pullprompt | object_replacement_wolf_dog | 1 | OK | 1.0 | 1.0 | 1.0 | - | Generate a gray wolf standing in the snow. |
| pullprompt | object_replacement_wolf_dog | 2 | OK | 1.0 | 1.0 | 1.0 | - | Replace the wolf with a black dog. |
| pullprompt | object_replacement_wolf_dog | 3 | BAD | 0.6667 | 1.0 | 0.0 | dog_left [spatial_relation/current] | Move the black dog to the left side of the image. |
| pullprompt | object_replacement_wolf_dog | 4 | OK | 1.0 | 1.0 | 1.0 | - | Add a blue collar to the dog while keeping it on the left in the snow. |
| pullprompt | scarf_color_conflict_fox | 1 | OK | 1.0 | 1.0 | 1.0 | - | Generate a fox standing in autumn leaves. |
| pullprompt | scarf_color_conflict_fox | 2 | OK | 1.0 | 1.0 | 1.0 | - | Make the fox wear a red scarf. |
| pullprompt | scarf_color_conflict_fox | 3 | OK | 1.0 | 1.0 | 1.0 | - | Change the scarf to a blue scarf, replacing the red scarf. |
| pullprompt | scarf_color_conflict_fox | 4 | OK | 1.0 | 1.0 | 1.0 | - | Add light snow while keeping the blue scarf and autumn leaves. |
| pullprompt | spatial_relation_cat_book | 1 | OK | 1.0 | 1.0 | 1.0 | - | Generate a cat sleeping beside a book near a window. |
| pullprompt | spatial_relation_cat_book | 2 | OK | 1.0 | 1.0 | 1.0 | - | Make the cat orange. |
| pullprompt | spatial_relation_cat_book | 3 | OK | 1.0 | 1.0 | 1.0 | - | Change the room into a cozy library. |
| pullprompt | spatial_relation_cat_book | 4 | OK | 1.0 | 1.0 | 1.0 | - | Add morning sunlight, keeping the orange cat beside the book. |
| pullprompt | style_conflict_robot | 1 | OK | 1.0 | 1.0 | 1.0 | - | Generate a friendly robot standing in a classroom in pixel art style. |
| pullprompt | style_conflict_robot | 2 | OK | 1.0 | 1.0 | 1.0 | - | Make the robot hold a red book. |
| pullprompt | style_conflict_robot | 3 | OK | 1.0 | 1.0 | 1.0 | - | Change the whole image to realistic photo style instead of pixel art. |
| pullprompt | style_conflict_robot | 4 | OK | 1.0 | 1.0 | 1.0 | - | Add warm window light, keeping the realistic photo style and red book. |
| structured-memory | background_only_dog | 1 | OK | 1.0 | 1.0 | 1.0 | - | Generate a dog sitting in the center of a park. |
| structured-memory | background_only_dog | 2 | OK | 1.0 | 1.0 | 1.0 | - | Make the dog wear a red scarf. |
| structured-memory | background_only_dog | 3 | OK | 1.0 | 1.0 | 1.0 | - | Change only the background to a snowy forest. |
| structured-memory | background_only_dog | 4 | OK | 1.0 | 1.0 | 1.0 | - | Add warm lighting without changing the dog, scarf, or sitting pose. |
| structured-memory | count_conflict_balloons | 1 | OK | 1.0 | 1.0 | 1.0 | - | Generate a child holding exactly two balloons. |
| structured-memory | count_conflict_balloons | 2 | OK | 1.0 | 1.0 | 1.0 | - | Make one balloon red and one balloon yellow. |
| structured-memory | count_conflict_balloons | 3 | OK | 1.0 | 1.0 | 1.0 | - | Change the count to exactly three balloons by adding one blue balloon. |
| structured-memory | count_conflict_balloons | 4 | OK | 1.0 | 1.0 | 1.0 | - | Put the child on a beach, keeping exactly three balloons and no extra balloons. |
| structured-memory | material_conflict_vase | 1 | OK | 1.0 | 1.0 | 1.0 | - | Generate a clear glass vase with exactly three flowers on a wooden table. |
| structured-memory | material_conflict_vase | 2 | OK | 1.0 | 1.0 | 1.0 | - | Make the flowers purple. |
| structured-memory | material_conflict_vase | 3 | BAD | 0.75 | 0.5 | 1.0 | purple_flowers [attribute_drift/history] | Change the vase material to white ceramic instead of glass. |
| structured-memory | material_conflict_vase | 4 | BAD | 0.5 | 0.3333 | 1.0 | ceramic_vase [material_conflict/history]; purple_flowers [attribute_drift/history] | Add rain visible through a window behind the table, keeping the ceramic vase and three purple flowers. |
| structured-memory | negative_constraint_teacher | 1 | OK | 1.0 | 1.0 | 1.0 | - | Generate a teacher robot standing beside a classroom blackboard. |
| structured-memory | negative_constraint_teacher | 2 | OK | 1.0 | 1.0 | 1.0 | - | Make the robot hold a red textbook. |
| structured-memory | negative_constraint_teacher | 3 | OK | 1.0 | 1.0 | 1.0 | - | Use children's book illustration style. |
| structured-memory | negative_constraint_teacher | 4 | BAD | 0.75 | 1.0 | 0.0 | no_readable_text [negative_constraint/current] | Keep the red textbook and classroom, but do not include readable text on the blackboard. |
| structured-memory | negative_extra_performers | 1 | OK | 1.0 | 1.0 | 1.0 | - | Generate a robot playing a violin on a stage. |
| structured-memory | negative_extra_performers | 2 | OK | 1.0 | 1.0 | 1.0 | - | Make the violin golden. |
| structured-memory | negative_extra_performers | 3 | OK | 1.0 | 1.0 | 1.0 | - | Do not add any extra performers. |
| structured-memory | negative_extra_performers | 4 | OK | 1.0 | 1.0 | 1.0 | - | Add blue spotlights, keeping the robot playing the golden violin with no extra performers. |
| structured-memory | object_addition_wallet | 1 | OK | 1.0 | 1.0 | 1.0 | - | Generate a black leather wallet on a marble countertop with a credit card partially sticking out. |
| structured-memory | object_addition_wallet | 2 | OK | 1.0 | 1.0 | 1.0 | - | Remove the credit card from the wallet, but keep the wallet. |
| structured-memory | object_addition_wallet | 3 | BAD | 0.6667 | 0.5 | 1.0 | no_credit_card [object_removal/history] | Put a small white flower on the wallet. |
| structured-memory | object_addition_wallet | 4 | OK | 1.0 | 1.0 | 1.0 | - | Add soft studio lighting while keeping the flower on the wallet and no credit card. |
| structured-memory | object_replacement_wolf_dog | 1 | OK | 1.0 | 1.0 | 1.0 | - | Generate a gray wolf standing in the snow. |
| structured-memory | object_replacement_wolf_dog | 2 | OK | 1.0 | 1.0 | 1.0 | - | Replace the wolf with a black dog. |
| structured-memory | object_replacement_wolf_dog | 3 | OK | 1.0 | 1.0 | 1.0 | - | Move the black dog to the left side of the image. |
| structured-memory | object_replacement_wolf_dog | 4 | OK | 1.0 | 1.0 | 1.0 | - | Add a blue collar to the dog while keeping it on the left in the snow. |
| structured-memory | scarf_color_conflict_fox | 1 | OK | 1.0 | 1.0 | 1.0 | - | Generate a fox standing in autumn leaves. |
| structured-memory | scarf_color_conflict_fox | 2 | OK | 1.0 | 1.0 | 1.0 | - | Make the fox wear a red scarf. |
| structured-memory | scarf_color_conflict_fox | 3 | OK | 1.0 | 1.0 | 1.0 | - | Change the scarf to a blue scarf, replacing the red scarf. |
| structured-memory | scarf_color_conflict_fox | 4 | BAD | 0.75 | 0.6667 | 1.0 | no_red_scarf [attribute_conflict/history] | Add light snow while keeping the blue scarf and autumn leaves. |
| structured-memory | spatial_relation_cat_book | 1 | OK | 1.0 | 1.0 | 1.0 | - | Generate a cat sleeping beside a book near a window. |
| structured-memory | spatial_relation_cat_book | 2 | OK | 1.0 | 1.0 | 1.0 | - | Make the cat orange. |
| structured-memory | spatial_relation_cat_book | 3 | OK | 1.0 | 1.0 | 1.0 | - | Change the room into a cozy library. |
| structured-memory | spatial_relation_cat_book | 4 | OK | 1.0 | 1.0 | 1.0 | - | Add morning sunlight, keeping the orange cat beside the book. |
| structured-memory | style_conflict_robot | 1 | OK | 1.0 | 1.0 | 1.0 | - | Generate a friendly robot standing in a classroom in pixel art style. |
| structured-memory | style_conflict_robot | 2 | OK | 1.0 | 1.0 | 1.0 | - | Make the robot hold a red book. |
| structured-memory | style_conflict_robot | 3 | OK | 1.0 | 1.0 | 1.0 | - | Change the whole image to realistic photo style instead of pixel art. |
| structured-memory | style_conflict_robot | 4 | OK | 1.0 | 1.0 | 1.0 | - | Add warm window light, keeping the realistic photo style and red book. |
