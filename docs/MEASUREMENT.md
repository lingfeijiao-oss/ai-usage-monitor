# Measurement attribution

`ACCOUNT_EXCLUSIVE_WINDOW` is an observed attribution mode for work performed
outside AI Usage Monitor.

The monitor records an official account snapshot before and after a user-selected
measurement window. The selected model and reasoning effort are validated against
the provider's official model catalog.

The resulting token and quota deltas are `OBSERVED`, not `VERIFIED` attribution,
because other account activity during the same interval can contribute to the
account-wide counters.

If a quota window resets between the two snapshots, the quota percentage delta is
not compared.

Any derived "tokens per quota percentage point" ratio is marked `ESTIMATED`.

Exact per-task attribution requires a future `MANAGED_THREAD` mode where AI Usage
Monitor owns the App Server thread and turn.
