import os
import json
import asyncio
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Base directory for the AI Observatory data
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "web" / "data"

app = Server("ai-observatory")

@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="list_available_dates",
            description="List all available dates in the AI Observatory data. Dates are in YYYY-MM-DD format.",
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
        dates = []
        for item in DATA_DIR.iterdir():
            if item.is_dir() and item.name.count("-") == 2:
                dates.append(item.name)
        dates.sort(reverse=True)
        return [TextContent(type="text", text=json.dumps({"available_dates": dates}, indent=2))]

    elif name == "get_daily_summary":
        if not arguments or "date" not in arguments:
            return [TextContent(type="text", text="Error: 'date' argument is required.")]
        
        date = arguments["date"]
        summary_file = DATA_DIR / date / "summary.json"
        
        if not summary_file.exists():
            return [TextContent(type="text", text=f"Error: No summary found for date {date}.")]
            
        with open(summary_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        return [TextContent(type="text", text=json.dumps(data, indent=2))]

    elif name == "search_intelligence":
        if not arguments or "query" not in arguments:
            return [TextContent(type="text", text="Error: 'query' argument is required.")]
            
        query = arguments["query"].lower()
        results = []
        
        for date_dir in sorted(DATA_DIR.iterdir(), reverse=True):
            if not (date_dir.is_dir() and date_dir.name.count("-") == 2):
                continue
                
            summary_file = date_dir / "summary.json"
            if not summary_file.exists():
                continue
                
            try:
                with open(summary_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
                # Search in executive summary
                summary_text = data.get("executive_summary", "")
                if isinstance(summary_text, str):
                    if query in summary_text.lower():
                        results.append({"date": date_dir.name, "match": "executive_summary", "snippet": summary_text[:200] + "..."})
                        continue
                elif isinstance(summary_text, dict):
                    # Handle new structured summary
                    text_blob = json.dumps(summary_text)
                    if query in text_blob.lower():
                        results.append({"date": date_dir.name, "match": "executive_summary", "snippet": text_blob[:200] + "..."})
                        continue
                    
                # Search in top topics
                topics = data.get("top_topics", [])
                for topic in topics:
                    topic_text = f"{topic.get('name', '')} {topic.get('description', '')}"
                    if query in topic_text.lower():
                        results.append({"date": date_dir.name, "match": "top_topic", "topic": topic.get('name')})
                        break
                        
            except Exception as e:
                pass
                
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
