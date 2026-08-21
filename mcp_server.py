import json
import asyncio
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from mcp_report_store import available_dates, daily_summary, search_summaries

# Base directory for the R[AI]DAR data
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "web" / "data"

app = Server("wiredframe-radar")

@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="list_available_dates",
            description="List all available dates in the R[AI]DAR data. Dates are in YYYY-MM-DD format.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_daily_summary",
            description="Get the executive summary and top topics for a specific date.",
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "The date to get the summary for (YYYY-MM-DD)."
                    }
                },
                "required": ["date"]
            }
        ),
        Tool(
            name="search_intelligence",
            description="Search through the daily summaries for a specific keyword or query.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The keyword or topic to search for."
                    }
                },
                "required": ["query"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any] | None) -> list[TextContent]:
    """Handle tool calls."""
    if not DATA_DIR.exists():
        return [TextContent(type="text", text="Error: Data directory not found.")]

    if name == "list_available_dates":
        try:
            dates = available_dates(DATA_DIR)
        except FileNotFoundError as exc:
            return [TextContent(type="text", text=f"Error: {exc}")]
        return [TextContent(type="text", text=json.dumps({"available_dates": dates}, indent=2))]

    elif name == "get_daily_summary":
        if not arguments or "date" not in arguments:
            return [TextContent(type="text", text="Error: 'date' argument is required.")]
        
        date = str(arguments["date"])
        try:
            data = daily_summary(DATA_DIR, date)
        except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError) as exc:
            return [TextContent(type="text", text=f"Error: {exc}")]
            
        return [TextContent(type="text", text=json.dumps(data, indent=2))]

    elif name == "search_intelligence":
        if not arguments or "query" not in arguments:
            return [TextContent(type="text", text="Error: 'query' argument is required.")]
            
        query = str(arguments["query"])
        try:
            results = search_summaries(DATA_DIR, query)
        except (FileNotFoundError, ValueError) as exc:
            return [TextContent(type="text", text=f"Error: {exc}")]
                
        if not results:
            return [TextContent(type="text", text=f"No results found for '{query}'.")]
            
        return [TextContent(type="text", text=json.dumps({"query": query, "matches": results}, indent=2))]
        
    else:
        return [TextContent(type="text", text=f"Error: Unknown tool {name}")]

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())
