# AI Usage Monitor — Product Design V1

## Product promise

Normal use must be:

1. Install.
2. Launch.
3. Sign in when needed.
4. Monitor.
5. Close the window to exit completely.

The user must not manually locate Codex, choose a drive, find a config folder,
start an App Server, start a web server, or manage a background service.

## Foreground-only lifecycle

AI Usage Monitor is a foreground desktop application.

Provider helper processes may exist only as children of the visible application.
When the main window closes, every helper process created by the application
must be terminated.

Forbidden as a normal-use requirement:

- Windows service
- scheduled collector
- tray-only daemon
- mandatory autostart
- hidden persistent process
- manual terminal command
- manual localhost dashboard startup

## Automatic device discovery

At launch the application automatically detects installed provider runtimes.

For Codex, discovery is ordered:

1. current process PATH;
2. provider/environment hints;
3. official/common per-user and system install locations;
4. previously validated local discovery cache;
5. fixed local drives such as C:, D:, F: and other fixed volumes.

The user never has to select a drive.

Discovery validates candidates by executing only safe identity/capability probes:

- `codex --version`
- `codex app-server --help`

A file named `codex.exe` is not trusted merely because the filename matches.

If multiple valid installations are found, the application selects a compatible
candidate deterministically and retains the alternatives for diagnostics.

## Automatic Codex profile discovery

The application separately discovers Codex homes/task stores, including:

- `%CODEX_HOME%` when present;
- `%USERPROFILE%\.codex`;
- root-level `.codex` directories on fixed drives;
- profiles associated with validated Codex installations;
- bounded discovery of `.codex` directories on local fixed drives.

Existing provider credentials are never copied.

Each discovered profile is tested through Codex-supported interfaces. If no
usable authenticated profile exists, the application launches the provider's
official login flow itself.

## Project model

The user-facing accounting unit is a project folder, not a conversation.

All observable Codex sessions whose working directory belongs to one project
are grouped into that project.

The monitor should expose per-project cumulative:

- input tokens
- cached input tokens
- new input tokens
- output tokens
- reasoning output tokens
- total tokens

Derived:

`new_input = max(input - cached_input, 0)`

`cache_hit_rate = cached_input / input` when input > 0.

## Model observation

The monitor distinguishes:

- selected/configured model and reasoning effort;
- observed execution model and reasoning effort.

If the provider/local execution record exposes an execution-model change, the
floating window updates immediately and records the transition locally.

The product must not claim to detect a server-side routing change that the
provider does not expose to the client/runtime.

## Data provenance

Every displayed metric is classified as one of:

- VERIFIED — provider directly returned the metric;
- LOCAL_OBSERVED — read from provider-owned local execution records;
- OBSERVED — calculated from before/after observations;
- ESTIMATED — derived estimate;
- UNSUPPORTED — unavailable from the provider/runtime.

## Privacy

Default behavior:

- no prompt upload;
- no source-code upload;
- no browser-cookie scraping;
- no account ID persistence;
- no raw thread ID persistence in analytics;
- local SQLite only;
- no telemetry upload by default.
