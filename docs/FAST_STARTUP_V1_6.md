# Fast Startup v1.6

Startup is split into fast first-paint work and background verification.

1. The window is created immediately.
2. The previous LOCAL_OBSERVED project report is displayed from local cache.
3. Codex discovery checks normal/PATH/common locations first.
4. Bounded disk scanning is used only if the fast discovery path finds no usable
   Codex App Server runtime.
5. The last successful authentication profile is tried first on later launches.
6. Project rollout refresh continues in the background and atomically replaces
   the cached project report.
7. Account quota remains provider VERIFIED; cached project data is never treated
   as fresh billing truth.

No inference turn is created by this startup path.
