"""
vault404 Command Line Interface

Usage:
    vault404 stats           Show knowledge base statistics
    vault404 export [PATH]   Export all data to JSON
    vault404 purge           Delete all data (requires confirmation)
    vault404 search QUERY    Search for solutions
    vault404 encrypt         Enable encryption for data at rest
    vault404 serve           Start the REST API server
    vault404 serve-mcp       Start the MCP server
"""

import argparse
import asyncio
import json
import sys
import os
from pathlib import Path

# Fix Windows console encoding for Unicode
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from .storage import get_storage, configure_storage, reset_storage
from .tools.maintenance import get_stats, export_all, purge_all
from .tools.querying import find_solution, find_decision, find_pattern


def print_json(data: dict) -> None:
    """Pretty print JSON data."""
    print(json.dumps(data, indent=2, ensure_ascii=False))


def cmd_stats(args: argparse.Namespace) -> int:
    """Show knowledge base statistics."""
    async def run():
        result = await get_stats()
        if args.json:
            print_json(result)
        else:
            stats = result.get("stats", {})
            print("\n📊 vault404 Statistics")
            print("=" * 40)
            print(f"  Error Fixes:  {stats.get('error_fixes', 0)}")
            print(f"  Decisions:    {stats.get('decisions', 0)}")
            print(f"  Patterns:     {stats.get('patterns', 0)}")
            print(f"  ─────────────────────────")
            print(f"  Total:        {stats.get('total_records', 0)}")
            print(f"\n  Data dir: {stats.get('data_directory', 'N/A')}")
        return 0

    return asyncio.run(run())


def cmd_export(args: argparse.Namespace) -> int:
    """Export all data to JSON file."""
    async def run():
        result = await export_all(args.output)
        if args.json:
            print_json(result)
        else:
            if result.get("success"):
                print(f"\n✅ {result.get('message')}")
                records = result.get("records_exported", {})
                print(f"   Error fixes: {records.get('error_fixes', 0)}")
                print(f"   Decisions:   {records.get('decisions', 0)}")
                print(f"   Patterns:    {records.get('patterns', 0)}")
            else:
                print(f"\n❌ Export failed: {result.get('message')}")
                return 1
        return 0

    return asyncio.run(run())


def cmd_purge(args: argparse.Namespace) -> int:
    """Delete all vault404 data."""
    if not args.confirm:
        print("\n⚠️  WARNING: This will permanently delete ALL vault404 data!")
        print("   This action cannot be undone.\n")
        confirm = input("   Type 'DELETE' to confirm: ")
        if confirm != "DELETE":
            print("\n   Aborted.")
            return 1

    async def run():
        result = await purge_all(confirm=True)
        if result.get("success"):
            print(f"\n✅ {result.get('message')}")
        else:
            print(f"\n❌ {result.get('message')}")
            return 1
        return 0

    return asyncio.run(run())


def cmd_search(args: argparse.Namespace) -> int:
    """Search for solutions, decisions, or patterns."""
    async def run():
        query = " ".join(args.query)

        if args.type == "solution" or args.type == "all":
            result = await find_solution(query, limit=args.limit)
            if args.json:
                print_json({"solutions": result})
            else:
                print("\n🔍 Solutions:")
                if result.get("found"):
                    for s in result.get("solutions", []):
                        print(f"\n  [{s.get('confidence', 0):.0%}] {s.get('original_error', '')[:60]}")
                        print(f"       → {s.get('solution', '')[:80]}")
                        if s.get("verified"):
                            print("       ✓ Verified")
                else:
                    print("  No solutions found.")

        if args.type == "decision" or args.type == "all":
            result = await find_decision(query, limit=args.limit)
            if args.json:
                print_json({"decisions": result})
            else:
                print("\n📋 Decisions:")
                if result.get("found"):
                    for d in result.get("decisions", []):
                        print(f"\n  [{d.get('relevance', 0):.0%}] {d.get('title', '')}")
                        print(f"       → {d.get('choice', '')}")
                else:
                    print("  No decisions found.")

        if args.type == "pattern" or args.type == "all":
            result = await find_pattern(query, limit=args.limit)
            if args.json:
                print_json({"patterns": result})
            else:
                print("\n📐 Patterns:")
                if result.get("found"):
                    for p in result.get("patterns", []):
                        print(f"\n  [{p.get('relevance', 0):.0%}] {p.get('name', '')} ({p.get('category', '')})")
                        print(f"       Problem: {p.get('problem', '')[:60]}")
                        print(f"       Solution: {p.get('solution', '')[:60]}")
                else:
                    print("  No patterns found.")

        print()
        return 0

    return asyncio.run(run())


def cmd_encrypt(args: argparse.Namespace) -> int:
    """Enable encryption for data at rest."""
    import os

    # Check if already encrypted
    storage = get_storage()
    if storage.encrypted:
        print("\n✅ Encryption is already enabled.")
        return 0

    print("\n🔐 Enabling encryption for vault404 data...")
    print("   This will encrypt all future data at rest using AES-256.")

    if args.password:
        password = args.password
    else:
        import getpass
        password = getpass.getpass("   Enter encryption password (or press Enter for auto-generated): ")
        if not password:
            password = None
            print("   Using auto-generated encryption key.")

    # Reset and reconfigure with encryption
    reset_storage()
    configure_storage(encrypted=True, password=password)

    print("\n✅ Encryption enabled!")
    print("   Set VAULT404_ENCRYPTED=true to enable on future runs.")
    if password:
        print("   Set VAULT404_PASSWORD to your password to unlock data.")

    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    """Start the REST API server."""
    try:
        from .api.server import run_server
    except ImportError as e:
        print(f"\nError: Could not import API server: {e}")
        print("Make sure FastAPI and uvicorn are installed:")
        print("  pip install fastapi uvicorn")
        return 1

    print(f"\n🚀 Starting Vault404 REST API server...")
    print(f"   Host: {args.host}")
    print(f"   Port: {args.port}")
    print(f"   Docs: http://{args.host}:{args.port}/docs")
    print()

    run_server(
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="debug" if args.verbose else "info",
    )
    return 0


def cmd_serve_mcp(args: argparse.Namespace) -> int:
    """Start the MCP server."""
    from .mcp_server import main
    main()
    return 0


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="vault404",
        description="vault404: AI Coding Agent Memory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    vault404 stats                      Show statistics
    vault404 export ~/backup.json       Export data
    vault404 search "connection error"  Search solutions
    vault404 encrypt                    Enable encryption
    vault404 serve --port 8000          Start REST API server
    vault404 serve-mcp                  Start MCP server
        """,
    )

    parser.add_argument("--json", action="store_true", help="Output as JSON")

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # stats
    stats_parser = subparsers.add_parser("stats", help="Show knowledge base statistics")
    stats_parser.set_defaults(func=cmd_stats)

    # export
    export_parser = subparsers.add_parser("export", help="Export all data to JSON")
    export_parser.add_argument("output", nargs="?", help="Output file path")
    export_parser.set_defaults(func=cmd_export)

    # purge
    purge_parser = subparsers.add_parser("purge", help="Delete all data")
    purge_parser.add_argument("--confirm", action="store_true", help="Skip confirmation prompt")
    purge_parser.set_defaults(func=cmd_purge)

    # search
    search_parser = subparsers.add_parser("search", help="Search knowledge base")
    search_parser.add_argument("query", nargs="+", help="Search query")
    search_parser.add_argument(
        "--type", "-t",
        choices=["solution", "decision", "pattern", "all"],
        default="all",
        help="Type of record to search",
    )
    search_parser.add_argument("--limit", "-n", type=int, default=5, help="Max results")
    search_parser.set_defaults(func=cmd_search)

    # encrypt
    encrypt_parser = subparsers.add_parser("encrypt", help="Enable encryption")
    encrypt_parser.add_argument("--password", "-p", help="Encryption password")
    encrypt_parser.set_defaults(func=cmd_encrypt)

    # serve (REST API)
    serve_parser = subparsers.add_parser("serve", help="Start REST API server")
    serve_parser.add_argument(
        "--host", "-H",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)"
    )
    serve_parser.add_argument(
        "--port", "-p",
        type=int,
        default=8000,
        help="Port to listen on (default: 8000)"
    )
    serve_parser.add_argument(
        "--reload", "-r",
        action="store_true",
        help="Enable auto-reload for development"
    )
    serve_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    serve_parser.set_defaults(func=cmd_serve)

    # serve-mcp (MCP server)
    serve_mcp_parser = subparsers.add_parser("serve-mcp", help="Start MCP server")
    serve_mcp_parser.set_defaults(func=cmd_serve_mcp)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
