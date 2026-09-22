# Managed Thread Mode

Managed Thread Mode is the exact-attribution path for Codex.

The monitor creates the App Server thread and turn itself, explicitly binding:

- model
- reasoning effort
- sandbox mode
- elapsed time
- thread token-usage notifications
- account quota before and after the managed turn

## Safety

Execution requires an explicit `--execute` flag.

Before starting any thread/turn, the runner reads the official account quota and
blocks execution when ordinary usage is not allowed or a reported quota window
has zero remaining capacity.

The monitor rejects `danger-full-access`. Supported managed measurement sandboxes
are `read-only` and `workspace-write`.

## Privacy

The persistent run record does not store:

- prompt content
- source-code content
- raw thread IDs
- raw turn IDs
- email/account ID
- authentication tokens

Raw thread/turn IDs exist only in process memory while matching App Server
notifications. Persisted identifiers are SHA-256 hashes.

## Attribution

Model, reasoning effort, and thread token events are VERIFIED when the monitor
owns the thread and turn.

Account quota snapshots are VERIFIED. A quota percentage change observed across
the turn is still an observed account delta: unrelated concurrent account
activity can affect it.

## Dry-run

Without `--execute`, the command performs validation only and starts no inference.
