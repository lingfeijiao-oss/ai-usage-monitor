# Release Scope

## Production entrypoint

`src/main.py`

The packaged application imports the desktop UI and the provider/core modules
required by that desktop UI.

## Excluded from public/runtime state

The following are local/generated and are ignored by Git:

- `data/`
- `config/local.*`
- `schemas/`
- `.env*` except `.env.example`
- `secrets/`
- build/package output

## Removed legacy entrypoints

The historical local HTTP dashboard and task-browser user entrypoints were
removed before public release hardening. The normal product does not require a
web server.

## Network boundary

No literal external HTTP/HTTPS endpoint was found in the current `src` runtime
during the release-hardening scan after legacy web-dashboard isolation.

Codex account/quota access is delegated to the local Codex App Server process.
