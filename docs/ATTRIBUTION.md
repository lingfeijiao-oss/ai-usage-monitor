# Usage Attribution

AI Usage Monitor separates account-wide monitoring from exact per-thread attribution.

## ACCOUNT_PASSIVE

The provider exposes account-wide quota and/or aggregate token usage.

This mode can answer:

- how much quota is used
- when quota resets
- how many aggregate tokens are recorded
- how usage changes over time

It must not claim which external Codex thread, model, or reasoning effort caused
an account-level delta unless the provider explicitly supplies that attribution.

## LOCAL_APP_SERVER_THREAD

A token event was emitted for a thread visible to the monitor's App Server.

The event is VERIFIED for that visible thread, but does not imply visibility into
all Codex clients on the account.

## MANAGED_THREAD

The monitor starts/owns the App Server thread and turn. In this mode the monitor
can bind model, reasoning effort, thread token events, elapsed time and observed
quota deltas to the same managed work unit.

This is the preferred mode for exact model/effort efficiency benchmarking.

## Privacy

The public product should not require storing prompts, source code, thread IDs or
turn IDs to perform resource accounting.
