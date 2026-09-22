# Security

AI Usage Monitor is intended to be a local-first desktop application.

## Release rules

Never commit:

- API keys;
- OAuth tokens;
- session cookies;
- provider credentials;
- local account identifiers;
- conversation/prompt/response contents;
- monitored project source-code contents;
- local runtime databases or caches.

Generated local Codex schema snapshots are excluded from the public repository.

## Runtime boundary

The production desktop entrypoint is `src/main.py -> ui.desktop_app.DesktopApp`.

The production desktop application does not require an HTTP server. Historical
web-dashboard and task-browser entrypoints are not part of the release source
surface.

Provider authentication should remain owned by the provider's official/local
client flow. Credentials must not be copied into AI Usage Monitor configuration.

## Reporting a vulnerability

Do not include credentials, private rollout files, prompts, or proprietary
source code in a public vulnerability report. Provide the minimum reproduction
details necessary to explain the issue.
