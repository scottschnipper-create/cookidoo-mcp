"""Entry point for the Cookidoo MCP server."""

from cookidoo_mcp.server import mcp


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
