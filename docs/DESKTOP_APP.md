# Unified Desktop Application

Normal user flow:

`Install -> Launch -> Automatic detection -> Login if needed -> Monitor`

No manual Codex path selection is part of normal use.

## Process lifecycle

The visible desktop application owns all monitoring work.

It uses in-process worker threads for local rollout scanning. When an account
query is needed it owns the Codex App Server child process. If login is needed,
it owns the Codex login child process.

Closing the visible window:

- signals every worker to stop;
- terminates an active login child process;
- closes/terminates the owned App Server;
- destroys the UI process.

There is no Windows service, scheduled monitor, web server, tray-only daemon or
mandatory autostart component.

## Live project display

The application groups Codex usage by `cwd` project folder.

The AUTO project is the project whose latest observed `turn_context` is newest.

Local rollout changes are checked every two seconds using an incremental cache:
unchanged historical rollout files are not reparsed.

The live panel shows:

- current project
- observed execution model
- observed reasoning effort
- model/effort change indication
- official account quota and reset countdown
- project total tokens
- input tokens
- cached input tokens
- new input tokens
- output tokens
- reasoning output tokens
- cache-hit rate

Account quota is provider VERIFIED.
Project/model token accounting is LOCAL_OBSERVED.
