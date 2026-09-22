# Project Usage Accounting

The primary user-facing unit is a project folder (`cwd`), not a conversation.

## Source

Codex local rollout JSONL records are scanned read-only.

The scanner parses only:

- `session_meta`
- `turn_context`
- `token_usage_record`
- legacy token-count records when needed

Prompt messages, assistant responses, tool output and source-code bodies are not
parsed into the analytics model or persisted by AI Usage Monitor.

## Project grouping

A rollout belongs to the project recorded in `session_meta.cwd`.

All rollouts/threads with the same normalized `cwd` are accumulated into the
same project.

## Token accounting

For current Codex rollouts, `token_usage_record` is preferred.

Records are deduplicated by `response_id`, then accumulated across every thread
belonging to the project.

Metrics:

- input
- cached input
- new input = input - cached input
- cache-write input when exposed
- output
- reasoning output
- total
- cache-hit rate = cached input / input

Reasoning output is displayed separately but is not added again to total.

Older rollouts without per-response usage records fall back to their latest
cumulative token count and are explicitly marked as a legacy local source.

## Model and reasoning attribution

`turn_context.turn_id` binds an observed model/reasoning effort to the
corresponding `token_usage_record.turn_id`.

This permits project totals to be split by actual locally recorded
model + reasoning effort.

Changes in `turn_context.model` or effort are recorded as local model/effort
switch observations.

## Accuracy boundary

These figures are `LOCAL_OBSERVED`.

They are stronger than inferring project usage from account totals, but they are
not provider billing totals. Some Codex versions have known cases where local
rollout accounting can omit auto-compaction overhead.

AI Usage Monitor must never relabel these local totals as provider-billing
`VERIFIED` values.
