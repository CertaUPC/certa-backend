"""Arranque del trabajador: `py -m apps.worker`."""

import asyncio
import sys

from .loop import main

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
