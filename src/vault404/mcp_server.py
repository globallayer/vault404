"""
vault404 MCP Server

Collective AI Coding vault404.
Every verified fix makes ALL AI agents smarter.
Automatic sharing, fully anonymized.
"""

import asyncio
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .tools.recording import log_error_fix, log_decision, log_pattern
from .tools.querying import find_solution, find_decision, find_pattern
from .tools.maintenance import verify_solution, get_stats

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vault404")

# Create MCP server
server = Server("vault404")


# =============================================================================
# Tool Definitions
# =============================================================================

TOOLS = [
    # Recording tools
    Tool(
        name="log_error_fix",
        description="""Log an error and its solution to the vault404.

Use this after fixing any error to build the knowledge base.
Future encounters of similar errors will return this solution.

Required: error_message, solution
Optional: error_type, stack_trace, file, line, code_change, files_modified,
         project, language, framework, database, platform, category, time_to_solve, verified""",
        inputSchema={
            "type": "object",
            "properties": {
                "error_message": {"type": "string", "description": "The error message encountered"},
                "solution": {"type": "string", "description": "How the error was fixed"},
                "error_type": {"type": "string", "description": "Type of error (e.g., ConnectionError)"},
                "stack_trace": {"type": "string", "description": "Full stack trace"},
                "file": {"type": "string", "description": "File where error occurred"},
                "line": {"type": "integer", "description": "Line number"},
                "code_change": {"type": "string", "description": "The code change made"},
                "files_modified": {"type": "array", "items": {"type": "string"}},
                "project": {"type": "string", "description": "Project name"},
                "language": {"type": "string", "description": "Programming language"},
                "framework": {"type": "string", "description": "Framework being used"},
                "database": {"type": "string", "description": "Database being used"},
                "platform": {"type": "string", "description": "Deployment platform"},
                "category": {"type": "string", "description": "Issue category"},
                "time_to_solve": {"type": "string", "description": "Time taken (e.g., '5m')"},
                "verified": {"type": "boolean", "description": "Whether solution is verified"},
            },
            "required": ["error_message", "solution"],
        },
    ),
    Tool(
        name="log_decision",
        description="""Log an architectural decision to the vault404.

Use this when making significant technical choices.
Helps remember why decisions were made and their outcomes.

Required: title, choice
Optional: alternatives, pros, cons, deciding_factor, project, component, language, framework""",
        inputSchema={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short title for the decision"},
                "choice": {"type": "string", "description": "What was chosen"},
                "alternatives": {"type": "array", "items": {"type": "string"}},
                "pros": {"type": "array", "items": {"type": "string"}},
                "cons": {"type": "array", "items": {"type": "string"}},
                "deciding_factor": {"type": "string"},
                "project": {"type": "string"},
                "component": {"type": "string"},
                "language": {"type": "string"},
                "framework": {"type": "string"},
            },
            "required": ["title", "choice"],
        },
    ),
    Tool(
        name="log_pattern",
        description="""Log a reusable pattern to the vault404.

Use this to capture patterns that solve recurring problems.
Makes the knowledge reusable across projects.

Required: name, category, problem, solution
Optional: languages, frameworks, databases, scenarios, before_code, after_code, explanation""",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Pattern name"},
                "category": {"type": "string", "description": "Category (database, auth, api, etc.)"},
                "problem": {"type": "string", "description": "Problem this solves"},
                "solution": {"type": "string", "description": "How it solves it"},
                "languages": {"type": "array", "items": {"type": "string"}},
                "frameworks": {"type": "array", "items": {"type": "string"}},
                "databases": {"type": "array", "items": {"type": "string"}},
                "scenarios": {"type": "array", "items": {"type": "string"}},
                "before_code": {"type": "string"},
                "after_code": {"type": "string"},
                "explanation": {"type": "string"},
            },
            "required": ["name", "category", "problem", "solution"],
        },
    ),
    # Query tools
    Tool(
        name="find_solution",
        description="""Find solutions for an error from the vault404.

ALWAYS check this first when encountering an error.
Returns past solutions ranked by relevance and context match.

Required: error_message
Optional: project, language, framework, database, platform, category, limit""",
        inputSchema={
            "type": "object",
            "properties": {
                "error_message": {"type": "string", "description": "The error to find solutions for"},
                "project": {"type": "string"},
                "language": {"type": "string"},
                "framework": {"type": "string"},
                "database": {"type": "string"},
                "platform": {"type": "string"},
                "category": {"type": "string"},
                "limit": {"type": "integer", "default": 3},
            },
            "required": ["error_message"],
        },
    ),
    Tool(
        name="find_decision",
        description="""Find past decisions on a topic from the vault404.

Check this before making architectural choices to learn from history.

Required: topic
Optional: project, component, limit""",
        inputSchema={
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Topic to search for"},
                "project": {"type": "string"},
                "component": {"type": "string"},
                "limit": {"type": "integer", "default": 3},
            },
            "required": ["topic"],
        },
    ),
    Tool(
        name="find_pattern",
        description="""Find reusable patterns for a problem from the vault404.

Search for established patterns before implementing solutions.

Required: problem
Optional: category, language, framework, limit""",
        inputSchema={
            "type": "object",
            "properties": {
                "problem": {"type": "string", "description": "Problem to find patterns for"},
                "category": {"type": "string"},
                "language": {"type": "string"},
                "framework": {"type": "string"},
                "limit": {"type": "integer", "default": 3},
            },
            "required": ["problem"],
        },
    ),
    # Maintenance tools
    Tool(
        name="verify_solution",
        description="""Verify whether a solution worked. AUTO-CONTRIBUTES to community brain if success=True.

Call this after trying a suggested solution.
If it worked, the anonymized solution is automatically shared with all agents.

Required: record_id, success""",
        inputSchema={
            "type": "object",
            "properties": {
                "record_id": {"type": "string", "description": "The record ID"},
                "success": {"type": "boolean", "description": "Whether it worked - if True, auto-contributes to community"},
            },
            "required": ["record_id", "success"],
        },
    ),
    Tool(
        name="agent_brain_stats",
        description="""Get statistics about the vault404 knowledge base.

Shows total records, entities, and relationship types.""",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
]


# =============================================================================
# Tool Handlers
# =============================================================================

@server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available tools"""
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls"""
    logger.info(f"Tool called: {name} with args: {arguments}")

    try:
        if name == "log_error_fix":
            result = await log_error_fix(**arguments)
        elif name == "log_decision":
            result = await log_decision(**arguments)
        elif name == "log_pattern":
            result = await log_pattern(**arguments)
        elif name == "find_solution":
            result = await find_solution(**arguments)
        elif name == "find_decision":
            result = await find_decision(**arguments)
        elif name == "find_pattern":
            result = await find_pattern(**arguments)
        elif name == "verify_solution":
            result = await verify_solution(**arguments)
        elif name == "agent_brain_stats":
            result = await get_stats()
        else:
            result = {"error": f"Unknown tool: {name}"}

        return [TextContent(type="text", text=str(result))]

    except Exception as e:
        logger.error(f"Error in {name}: {e}")
        return [TextContent(type="text", text=f"Error: {str(e)}")]


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    """Run the MCP server"""
    logger.info("Starting vault404 MCP Server...")

    async def run():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    asyncio.run(run())


if __name__ == "__main__":
    main()
