"""
MCP server configuration builder for containerized MCP servers.

This module provides utilities to dynamically generate MCP server configurations
for containerized MCP servers, where each server runs in its own Docker container
and exposes an HTTP/SSE endpoint.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_mcp_server_config(
    mcp_servers: List[Dict[str, Any]],
    port_mapping: Dict[str, int],
    host: str = "127.0.0.1",
) -> Dict[str, Any]:
    """
    Build MCP server configuration for containerized MCP servers.

    This function generates a server configuration dictionary that can be passed
    to `MCPManager(config=...)` to connect to MCP servers running in Docker containers.

    For servers that go through Gateway (like filesystem), we don't set sse_address
    and let MCPManager use MCP_GATEWAY_ADDRESS instead.

    For servers that support native SSE (like media_tools), we set sse_address directly.

    Args:
        mcp_servers: List of MCP server specifications from task config.
            Each dict should have at least a "name" field.
        port_mapping: Dictionary mapping server names to their assigned ports.
            e.g. {"filesystem": 3333, "media_tools": 4444}
        host: Host address where containers are accessible (default: "127.0.0.1").

    Returns:
        A dictionary in the format expected by MCPManager.load_configs().
        For Gateway-based servers (stdio-only), no sse_address is set.
        For native SSE servers, sse_address is set to direct SSE endpoint.

    Example:
        >>> servers = [{"name": "filesystem"}, {"name": "media_tools"}]
        >>> ports = {"filesystem": 3333, "media_tools": 4444}
        >>> config = build_mcp_server_config(servers, ports)
        >>> # config will have:
        >>> # {
        >>> #   "filesystem": {
        >>> #     # No sse_address - will use MCP_GATEWAY_ADDRESS
        >>> #   },
        >>> #   "media_tools": {
        >>> #     "sse_address": "http://127.0.0.1:4444/sse"
        >>> #   }
        >>> # }
    """
    config: Dict[str, Any] = {}

    # Servers that go through Gateway (stdio-only servers)
    gateway_servers = {"filesystem"}  # Add more stdio-only servers here if needed

    for server_spec in mcp_servers:
        server_name = server_spec.get("name")
        if not server_name:
            continue

        port = port_mapping.get(server_name)
        if port is None:
            # If no port mapping, skip this server (or use default stdio config)
            continue

        if server_name in gateway_servers:
            # For Gateway-based servers, don't set sse_address
            # MCPManager will use MCP_GATEWAY_ADDRESS to construct the URL
            # Gateway exposes endpoints at: {GATEWAY_ADDRESS}/{server_name}/sse
            config[server_name] = {
                # No sse_address - will use MCP_GATEWAY_ADDRESS
                "stdio": {
                    "command": "echo",
                    "args": ["MCP server is containerized, use Gateway"],
                },
                "sse": {
                    "command": "",
                    "args": [],
                },
            }
        else:
            # For native SSE servers (like media_tools), set direct SSE address
            # FastMCP servers expose SSE at root /sse endpoint
            sse_url = f"http://{host}:{port}/sse"
            
            config[server_name] = {
                "sse_address": sse_url,
                "stdio": {
                    "command": "echo",
                    "args": ["MCP server is containerized, use SSE transport"],
                },
                "sse": {
                    "command": "",
                    "args": [],
                },
            }

    return config


def get_default_port_for_server(server_name: str, base_port: int = 30000) -> int:
    """
    Generate a deterministic port number for a server based on its name.

    This is useful for parallel task execution where each task needs unique ports.

    Args:
        server_name: Name of the MCP server.
        base_port: Base port number (default: 30000).

    Returns:
        A port number based on server name hash.

    Note:
        This is a simple hash-based approach. For production, consider using
        a port pool manager to avoid collisions.
    """
    # Simple hash-based port assignment
    # This ensures same server name always gets same port (modulo range)
    hash_value = hash(server_name) % 1000
    return base_port + hash_value

