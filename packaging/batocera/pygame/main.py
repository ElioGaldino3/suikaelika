#!/usr/bin/env python3
"""Start Suika Elika from the self-contained Batocera package directory."""

from __future__ import annotations

from bootstrap import ensure_pymunk

ensure_pymunk()

from suika_elika.app import main


if __name__ == "__main__":
    raise SystemExit(main())
