"""Allow running the server with `python -m skyq_mcp`."""

import asyncio
import logging

from .server import run

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    asyncio.run(run())
