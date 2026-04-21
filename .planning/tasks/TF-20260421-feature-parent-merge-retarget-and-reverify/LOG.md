# Log

## Timeline

- Created task
- Added stacked child retarget detection to merge receipt recording
- Added retarget metadata to the promotion bundle and blocked workflow phase handling
- Ran targeted and full unittest regression suites

## Notes

- Parent merge receipt recording now marks stacked children with `retarget_required`, `reverify_required`, and a blocking `PARENT_RETARGET_REQUIRED` gate.
- Affected children move to `workflow_phase=retarget_required` and `verify_status=not_run` so operator retarget work is explicit.
- Merge receipt results now include `child_retargeted_task_ids` for follow-up visibility.

## Follow-ups

- Add an operator or MCP action that clears the retarget gate after the child PR is retargeted and verified again.
