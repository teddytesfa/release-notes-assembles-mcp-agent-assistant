"""
Global MCP Server for the Release Notes Assembler.
This module implements the central MCP server that will manage tool registration,
discovery, and routing for all MCP services in the system.
"""

__all__ = [
    'ToolRegistry',
    'ServiceDiscovery',
    'Router',
    'HealthMonitor',
    'GlobalMCPServer'
]
