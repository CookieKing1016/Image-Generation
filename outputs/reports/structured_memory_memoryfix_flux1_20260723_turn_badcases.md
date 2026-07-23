# Per-turn Evaluation Matrix: structured_memory_memoryfix_flux1_20260723

- Total turns: 13
- Bad turns: 2

## Badcase Index

| method | case_id | turn_index | status | checklist_score | history_retention | current_success | failed_items | failed_reasons | instruction |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| structured-memory | negative_constraint_teacher | 4 | BAD | 0.75 | 1.0 | 0.0 | no_readable_text [negative_constraint/current] | The blackboard contains the clearly readable word 'Ardo' written in white chalk. | Keep the red textbook and classroom, but do not include readable text on the blackboard. |
| structured-memory | object_addition_wallet | 4 | BAD | 0.75 | 0.6667 | 1.0 | no_credit_card [object_removal/history] | Orange card is visible sticking out from the wallet's edge, violating the no credit card constraint. | Add soft studio lighting while keeping the flower on the wallet and no credit card. |

## All Turns

| method | case_id | turn_index | status | checklist_score | history_retention | current_success | failed_items | instruction |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| structured-memory | material_conflict_vase | 1 | OK | 1.0 | 1.0 | 1.0 | - | Generate a clear glass vase with exactly three flowers on a wooden table. |
| structured-memory | material_conflict_vase | 2 | OK | 1.0 | 1.0 | 1.0 | - | Make the flowers purple. |
| structured-memory | material_conflict_vase | 3 | OK | 1.0 | 1.0 | 1.0 | - | Change the vase material to white ceramic instead of glass. |
| structured-memory | material_conflict_vase | 4 | OK | 1.0 | 1.0 | 1.0 | - | Add rain visible through a window behind the table, keeping the ceramic vase and three purple flowers. |
| structured-memory | negative_constraint_teacher | 1 | OK | 1.0 | 1.0 | 1.0 | - | Generate a teacher robot standing beside a classroom blackboard. |
| structured-memory | negative_constraint_teacher | 2 | OK | 1.0 | 1.0 | 1.0 | - | Make the robot hold a red textbook. |
| structured-memory | negative_constraint_teacher | 3 | OK | 1.0 | 1.0 | 1.0 | - | Use children's book illustration style. |
| structured-memory | negative_constraint_teacher | 4 | BAD | 0.75 | 1.0 | 0.0 | no_readable_text [negative_constraint/current] | Keep the red textbook and classroom, but do not include readable text on the blackboard. |
| structured-memory | object_addition_wallet | 1 | OK | 1.0 | 1.0 | 1.0 | - | Generate a black leather wallet on a marble countertop with a credit card partially sticking out. |
| structured-memory | object_addition_wallet | 2 | OK | 1.0 | 1.0 | 1.0 | - | Remove the credit card from the wallet, but keep the wallet. |
| structured-memory | object_addition_wallet | 3 | OK | 1.0 | 1.0 | 1.0 | - | Put a small white flower on the wallet. |
| structured-memory | object_addition_wallet | 4 | BAD | 0.75 | 0.6667 | 1.0 | no_credit_card [object_removal/history] | Add soft studio lighting while keeping the flower on the wallet and no credit card. |
| structured-memory | scarf_color_conflict_fox | 1 | OK | 1.0 | 1.0 | 1.0 | - | Generate a fox standing in autumn leaves. |
