"""Start the Sky Q MCP server with uvicorn."""

import logging

import uvicorn

from skyq_mcp import settings
from skyq_mcp.server import create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


def main() -> None:
    uvicorn.run(
        create_app(),
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        log_level="info",
    )


if __name__ == "__main__":
    main()
