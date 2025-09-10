"""
Router for the Global MCP Server.

This module implements the routing functionality that directs tool execution
requests to the appropriate MCP servers based on tool registration and
server availability.
"""

from typing import Any, Dict, List, Optional, Tuple
import logging
import random

from .tool_registry import ToolMetadata
from .service_discovery import ServerMetadata, ServiceDiscovery


class Router:
    """
    Router for directing tool execution requests to the appropriate MCP servers.
    
    This class is responsible for:
    1. Maintaining a mapping of tool names to servers that provide them
    2. Selecting the appropriate server for a given tool execution
    3. Handling load balancing between multiple servers that provide the same tool
    4. Managing failover between servers
    """
    
    def __init__(self, service_discovery: ServiceDiscovery):
        """
        Initialize the Router.
        
        Args:
            service_discovery: The ServiceDiscovery instance to use for server lookups
        """
        self.service_discovery = service_discovery
        self.logger = logging.getLogger(__name__)
        self._tool_to_servers: Dict[str, List[str]] = {}
        self._server_load: Dict[str, int] = {}
    
    def update_tool_mapping(self, tool_name: str, server_id: str) -> None:
        """
        Update the mapping of a tool to its available servers.
        
        Args:
            tool_name: Name of the tool
            server_id: ID of the server that provides this tool
        """
        if tool_name not in self._tool_to_servers:
            self._tool_to_servers[tool_name] = []
        
        if server_id not in self._tool_to_servers[tool_name]:
            self._tool_to_servers[tool_name].append(server_id)
            self._server_load[server_id] = self._server_load.get(server_id, 0)
    
    def remove_tool_mapping(self, tool_name: str, server_id: str) -> None:
        """
        Remove a tool mapping for a specific server.
        
        Args:
            tool_name: Name of the tool
            server_id: ID of the server to remove the mapping for
        """
        if tool_name in self._tool_to_servers:
            if server_id in self._tool_to_servers[tool_name]:
                self._tool_to_servers[tool_name].remove(server_id)
                # If no more servers provide this tool, clean up
                if not self._tool_to_servers[tool_name]:
                    del self._tool_to_servers[tool_name]
    
    def remove_server_mappings(self, server_id: str) -> List[str]:
        """
        Remove all tool mappings for a specific server.
        
        Args:
            server_id: ID of the server to remove
            
        Returns:
            List of tool names that were affected by this removal
        """
        affected_tools = []
        for tool_name, server_ids in list(self._tool_to_servers.items()):
            if server_id in server_ids:
                server_ids.remove(server_id)
                affected_tools.append(tool_name)
                # If no more servers provide this tool, clean up
                if not server_ids:
                    del self._tool_to_servers[tool_name]
        
        # Clean up server load tracking
        if server_id in self._server_load:
            del self._server_load[server_id]
            
        return affected_tools
    
    def get_server_for_tool(
        self,
        tool_name: str,
        strategy: str = "round_robin"
    ) -> Optional[Tuple[str, ServerMetadata]]:
        """
        Get the best server to execute a tool.
        
        Args:
            tool_name: Name of the tool to execute
            strategy: Load balancing strategy to use ('round_robin', 'random', 'least_loaded')
            
        Returns:
            Tuple of (server_id, server_metadata) if a server is available, or None
        """
        if tool_name not in self._tool_to_servers:
            self.logger.warning(f"No servers found for tool: {tool_name}")
            return None
        
        available_servers = []
        for server_id in self._tool_to_servers[tool_name]:
            server = self.service_discovery.get_server(server_id)
            if server and server.is_active:
                available_servers.append((server_id, server))
        
        if not available_servers:
            self.logger.warning(f"No active servers found for tool: {tool_name}")
            return None
        
        # Select server based on strategy
        if strategy == "round_robin":
            # Simple round-robin by moving the first server to the end
            server_id, server = available_servers[0]
            self._tool_to_servers[tool_name] = (
                self._tool_to_servers[tool_name][1:] + [server_id]
            )
            self._server_load[server_id] = self._server_load.get(server_id, 0) + 1
            return server_id, server
            
        elif strategy == "random":
            server_id, server = random.choice(available_servers)
            self._server_load[server_id] = self._server_load.get(server_id, 0) + 1
            return server_id, server
            
        elif strategy == "least_loaded":
            # Find server with the least current load
            server_id, server = min(
                available_servers,
                key=lambda x: self._server_load.get(x[0], 0)
            )
            self._server_load[server_id] = self._server_load.get(server_id, 0) + 1
            return server_id, server
            
        else:
            # Default to first available server
            server_id, server = available_servers[0]
            self._server_load[server_id] = self._server_load.get(server_id, 0) + 1
            return server_id, server
    
    def record_tool_completion(self, server_id: str) -> None:
        """
        Record completion of a tool execution.
        
        This should be called after a tool execution completes to update
        the server's load metrics.
        
        Args:
            server_id: ID of the server that executed the tool
        """
        if server_id in self._server_load and self._server_load[server_id] > 0:
            self._server_load[server_id] -= 1
    
    def get_server_load(self, server_id: str) -> int:
        """
        Get the current load for a server.
        
        Args:
            server_id: ID of the server
            
        Returns:
            Current load (number of active tool executions)
        """
        return self._server_load.get(server_id, 0)
    
    def get_tool_servers(self, tool_name: str) -> List[str]:
        """
        Get all servers that provide a specific tool.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            List of server IDs that provide the tool
        """
        return self._tool_to_servers.get(tool_name, [])
    
    def clear(self) -> None:
        """Clear all routing information."""
        self._tool_to_servers.clear()
        self._server_load.clear()
