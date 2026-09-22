# v1.3.1 design

This revision supersedes the unexecuted v1.3 plan.

## Compact window

Collapsed mode remains the normal monitoring surface.

It shows:

- current project folder
- current locally observed execution model
- current locally observed reasoning effort
- official account quota and reset time
- project total tokens
- project input/cached/new/output/reasoning/cache-hit metrics

## Model history

`MODELS` expands the same foreground window.

For the selected project it groups historical usage as:

`model -> reasoning effort -> total / cached / new tokens`

The data already exists for historical Codex rollouts. It does not begin only
after v1.3.1 is installed.

Project/model token data is labeled `LOCAL_OBSERVED`.

## Platforms

The shared source targets Windows, macOS and Linux.

Normal usage on every platform remains:

`Install -> Launch -> auto-detect Codex -> login if required -> monitor`

No normal-use flow asks the user to browse for the Codex executable or manually
select a disk/mount.

## Release artifacts

- Windows: installer EXE
- macOS: DMG containing `.app`
- Linux: DEB plus portable tar.gz

Native artifacts are built on their matching operating systems.
