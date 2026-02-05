#!/usr/bin/env python3
"""
Universal wrapper to bridge stdio-only MCP servers to SSE transport.

This allows any stdio-only MCP server to run in a container and be accessed via HTTP/SSE.

Usage:
    python mcp_stdio_sse_bridge.py \
        --server-name filesystem \
        --command npx \
        --args "-y" "@modelcontextprotocol/server-filesystem" "/workspace" \
        --port 3333

Or via environment variables:
    MCP_SERVER_NAME=filesystem
    MCP_COMMAND=npx
    MCP_ARGS='["-y", "@modelcontextprotocol/server-filesystem", "/workspace"]'
    MCP_PORT=3333
    python mcp_stdio_sse_bridge.py
"""

import os
import sys
import json
import asyncio
import argparse
from pathlib import Path

# Add MCP-Universe to path if mounted
mcp_universe_path = Path("/mcp-universe")
if mcp_universe_path.exists():
    sys.path.insert(0, str(mcp_universe_path))

try:
    from mcpuniverse.mcp.gateway import ServerConnector
    from mcpuniverse.mcp.config import ServerConfig, CommandConfig
    from mcp.server.sse import SseServerTransport
    from starlette.applications import Starlette
    from starlette.routing import Route, Mount
    import uvicorn
except ImportError as e:
    print(f"Error importing required modules: {e}", file=sys.stderr)
    print("Make sure MCP-Universe is mounted at /mcp-universe", file=sys.stderr)
    sys.exit(1)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Bridge stdio-only MCP server to SSE transport"
    )
    parser.add_argument(
        "--server-name",
        default=os.environ.get("MCP_SERVER_NAME", "mcp_server"),
        help="Server name (used in URL path, e.g., /filesystem/sse)"
    )
    parser.add_argument(
        "--command",
        default=os.environ.get("MCP_COMMAND", ""),
        help="Command to run the stdio MCP server (e.g., 'npx', 'python3')"
    )
    parser.add_argument(
        "--args",
        default=os.environ.get("MCP_ARGS", "[]"),
        help="JSON array of command arguments (e.g., '[\"-y\", \"@modelcontextprotocol/server-filesystem\", \"/workspace\"]')"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("MCP_PORT", "3333")),
        help="Port to listen on for SSE transport"
    )
    parser.add_argument(
        "--env",
        default=os.environ.get("MCP_ENV", "{}"),
        help="JSON object of environment variables to pass to the server"
    )
    
    return parser.parse_args()


async def main():
    """Run stdio MCP server with SSE transport."""
    args = parse_args()
    
    if not args.command:
        print("Error: --command is required", file=sys.stderr)
        sys.exit(1)
    
    # Parse JSON arguments
    try:
        server_args = json.loads(args.args) if isinstance(args.args, str) else args.args
        if not isinstance(server_args, list):
            server_args = []
    except json.JSONDecodeError:
        print(f"Warning: Failed to parse --args as JSON, using as single argument: {args.args}", file=sys.stderr)
        server_args = [args.args]
    
    # Parse environment variables
    try:
        env_vars = json.loads(args.env) if isinstance(args.env, str) else args.env
        if not isinstance(env_vars, dict):
            env_vars = {}
    except json.JSONDecodeError:
        print(f"Warning: Failed to parse --env as JSON, using empty dict", file=sys.stderr)
        env_vars = {}
    
    print(f"Starting MCP stdio-to-SSE bridge for server '{args.server_name}' on port {args.port}")
    print(f"Command: {args.command}")
    print(f"Args: {server_args}")
    print(f"Env: {env_vars}")
    
    # Create ServerConfig for the stdio server
    server_config = ServerConfig(
        stdio=CommandConfig(
            command=args.command,
            args=server_args
        ),
        sse=CommandConfig(),
        env=env_vars
    )
    
    # Create SSE transport
    # MCP SSE endpoint pattern: /{server_name}/messages/
    sse = SseServerTransport(f"/{args.server_name}/messages/")
    
    async def handle_sse(request):
        """Handle SSE connection and bridge to stdio server."""
        connector = ServerConnector()
        try:
            async with sse.connect_sse(
                request.scope, request.receive, request._send
            ) as streams:
                await connector.connect_to_stdio_server(server_config)
                await connector.run(streams[0], streams[1])
        finally:
            await connector.cleanup()
    
    # Create Starlette app
    # MCP SSE endpoint pattern: /{server_name}/sse for SSE connection
    # and /{server_name}/messages/ for POST requests
    routes = [
        Route(f"/{args.server_name}/sse", endpoint=handle_sse),
        Mount(f"/{args.server_name}/messages/", app=sse.handle_post_message),
    ]
    
    app = Starlette(debug=False, routes=routes)
    
    # Run server
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=args.port,
        log_level="info"
    )
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())

