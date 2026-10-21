"""Compatibility launcher for environments that execute ``main.py``."""

from suika_elika.app import main

if __name__ == "__main__":
    raise SystemExit(main())
