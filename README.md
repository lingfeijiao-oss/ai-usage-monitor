# AI Usage Monitor

AI Usage Monitor is a local-first desktop monitor for AI development usage.

Current provider support focuses on OpenAI Codex. The internal provider boundary
is designed so additional providers can be implemented without changing the
core project/accounting model.

## What it shows

For Codex, the desktop window can show:

- official account quota state and reset time when exposed by Codex App Server;
- locally observed project-folder token totals;
- input, cached input, new input, output and reasoning-output tokens;
- cache-hit rate;
- current locally observed model and reasoning effort;
- historical token usage grouped by model and reasoning effort;
- model share of project tokens and reasoning-effort share of model tokens.

Metrics are deliberately labeled by provenance. Account quota is not inferred
from local token counts.

## Normal use

The intended product flow is:

`Install -> Launch -> auto-detect Codex -> login if required -> monitor`

Users should not need to locate a Codex executable, select disks, start a local
web server, or manage a background collector.

The visible application owns its helper processes. Closing the application ends
monitoring.

## Platforms

Release infrastructure targets:

- Windows
- macOS
- Linux

Native packages must be built on their matching operating system.

## Privacy

The Codex project scanner reads local rollout telemetry needed for usage
accounting. It does not persist prompt bodies, response bodies, or monitored
project source-code bodies.

Local account/project state is not uploaded by AI Usage Monitor.

See `PRIVACY.md` and `SECURITY.md`.

## Metric provenance

- `VERIFIED`: supplied by an official/local provider interface.
- `LOCAL_OBSERVED`: derived from provider telemetry stored on the local device.
- `OBSERVED`: directly observed but not provider-billing verified.
- `ESTIMATED`: calculated estimate.
- `UNSUPPORTED`: the requested metric is not available.

Codex project token totals are `LOCAL_OBSERVED`; they must not be represented as
provider-billing totals or converted into quota percentages without provider
evidence.

## Development

Run unit tests:

```text
python -m unittest discover -s tests/unit -v
```

Run the source desktop application on the current Windows development checkout:

```text
pwsh -File .\scripts\run_app.ps1
```

Run the command from the repository root.

## License

Apache License 2.0. See `LICENSE`.

