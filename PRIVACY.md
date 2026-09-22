# Privacy

AI Usage Monitor is designed to be local-first.

## Data read locally

The Codex integration may read local Codex profile metadata, rollout telemetry,
model/reasoning-effort context, and token-usage records required to calculate
project usage.

## Data intentionally not persisted by the project scanner

The project usage scanner does not persist:

- prompt bodies;
- model response bodies;
- source-code bodies from monitored projects;
- browser cookies.

## Local storage

Local aggregate/cache/configuration data is stored on the user's device and is
excluded from the public source repository.

## Network behavior

The current desktop product does not run a local web dashboard and does not
contain an AI Usage Monitor telemetry/upload service.

Codex authentication and official quota/account queries are performed through
the locally installed Codex App Server/CLI. AI Usage Monitor does not collect
the user's Codex password or browser cookies.

Future export, cloud sync, telemetry, or additional provider integrations must
be opt-in where appropriate and documented before release.
