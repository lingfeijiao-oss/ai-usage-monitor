from __future__ import annotations

import sys

from ui.desktop_app import DesktopApp, smoke_test


def main() -> int:
    if "--smoke" in sys.argv:
        return smoke_test()

    DesktopApp().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
