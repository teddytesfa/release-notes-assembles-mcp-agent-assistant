"""
Global MCP Server implementation.

This module contains the main server class that brings together the Tool Registry,
Service Discovery, and Router components to provide a complete MCP server.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple

from .tool_registry import ToolRegistry, ToolMetadata
from .service_discovery import ServiceDiscovery, ServerMetadata
from .router import Router
from ..exceptions import MCPError, ToolNotFoundError, ServerNotFoundError


class GlobalMCPServer:
    """
    Global MCP Server implementation.
    
    This class provides the main interface for the Global MCP Server, which includes:
    - Tool registration and discovery
    - Server registration and health monitoring
    - Request routing and load balancing
    """
    
    def __init__(self, heartbeat_timeout: int = 300):
        """
        Initialize the Global MCP Server.
        
        Args:
            heartbeat_timeout: Number of seconds after which a server is 
                             considered offline if no heartbeat is received.
        """
        self.logger = logging.getLogger(__name__)
        self.tool_registry = ToolRegistry()
        self.service_discovery = ServiceDiscovery(heartbeat_timeout=heartbeat_timeout)
        self.router = Router(self.service_discovery)
        self._running = False
        self._health_check_task = None
    
    async def start(self) -> None:
        """Start the Global MCP Server and its background tasks."""
        if self._running:
            self.logger.warning("Global MCP Server is already running")
            return
        
        self._running = True
        # Start health check background task
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        self.logger.info("Global MCP Server started")
    
    async def stop(self) -> None:
        """Stop the Global MCP Server and clean up resources."""
        if not self._running:
            return
        
        self._running = False
        
        # Cancel the health check task
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None
        
        self.logger.info("Global MCP Server stopped")
    
    async def _health_check_loop(self) -> None:
        """Background task to periodically check server health."""
        while self._running:
            try:
                # Check server health
                self.service_discovery.check_health()
                
                # Clean up any inactive servers from the router
                for server in self.service_discovery.get_all_servers(active_only=False):
                    if not server.is_active:
                        affected_tools = self.router.remove_server_mappings(server.server_id)
                        if affected_tools:
                            self.logger.warning(
                                f"Server {server.name} ({server.server_id}) is inactive. "
                                f"Removed mappings for tools: {', '.join(affected_tools)}"
                            )
                
                # Sleep for a while before next check
                await asyncio.sleep(60)  # Check every minute
                
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger.error(f"Error in health check loop: {e}", exc_info=True)
                await asyncio.sleep(10)  # On error, wait before retrying
    
    # Tool Management
    
    def register_tool(self, tool_metadata: ToolMetadata) -> str:
        """
        Register a new tool with the Global MCP Server.
        
        Args:
            tool_metadata: Metadata describing the tool
            
        Returns:
            str: A unique ID for the registered tool
            
        Raises:
            MCPError: If there's an error registering the tool
        """
        try:
            tool_id = self.tool_registry.register_tool(tool_metadata)
            
            # Update the router's tool-to-server mapping
            if tool_metadata.server_id:
                self.router.update_tool_mapping(tool_metadata.name, tool_metadata.server_id)
            
            self.logger.info(f"Registered tool: {tool_metadata.name} (ID: {tool_id})")
            return tool_id
            
        except Exception as e:
            self.logger.error(f"Failed to register tool {tool_metadata.name}: {e}", exc_info=True)
            raise MCPError(f"Failed to register tool: {e}")
    
    def unregister_tool(self, tool_id: str) -> bool:
        """
        Unregister a tool from the Global MCP Server.
        
        Args:
            tool_id: ID of the tool to unregister
            
        Returns:
            bool: True if the tool was found and unregistered, False otherwise
            
        Raises:
            MCPError: If there's an error unregistering the tool
        """
        try:
            tool = self.tool_registry.get_tool(tool_id)
            if not tool:
                return False
            
            # Remove from router's tool-to-server mapping
            if tool.server_id:
                self.router.remove_tool_mapping(tool.name, tool.server_id)
            
            # Remove from tool registry
            success = self.tool_registry.unregister_tool(tool_id)
            
            if success:
                self.logger.info(f"Unregistered tool: {tool.name} (ID: {tool_id})")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to unregister tool {tool_id}: {e}", exc_info=True)
            raise MCPError(f"Failed to unregister tool: {e}")
    
    def find_tools(
        self,
        name_pattern: Optional[str] = None,
        tags: Optional[List[str]] = None,
        server_id: Optional[str] = None
    ) -> List[ToolMetadata]:
        """
        Find tools matching the given criteria.
        
        Args:
            name_pattern: Case-insensitive substring to match against tool names
            tags: List of tags that must all be present
            server_id: ID of the server that registered the tool
            
        Returns:
            List[ToolMetadata]: List of matching tools
            
        Raises:
            MCPError: If there's an error searching for tools
        """
        try:
            # First filter by server if specified
            if server_id:
                tools = self.tool_registry.get_server_tools(server_id)
            else:
                tools = self.tool_registry.get_all_tools()
            
            # Apply additional filters
            if name_pattern or tags:
                filtered_tools = []
                name_lower = (name_pattern or "").lower()
                
                for tool in tools:
                    # Filter by name pattern
                    if name_pattern and name_lower not in tool.name.lower():
                        continue
                    
                    # Filter by tags
                    if tags and not all(tag in tool.tags for tag in tags):
                        continue
                    
                    filtered_tools.append(tool)
                
                return filtered_tools
            
            return tools
            
        except Exception as e:
            self.logger.error(f"Error finding tools: {e}", exc_info=True)
            raise MCPError(f"Error finding tools: {e}")
    
    # Server Management
    
    def register_server(
        self,
        name: str,
        description: str,
        version: str,
        host: str,
        port: int,
        tags: Optional[List[str]] = None,
        metadata: Optional[dict] = None
    ) -> str:
        """
        Register a new MCP server with the Global MCP Server.
        
        Args:
            name: Human-readable name of the server
            description: Description of the server's purpose
            version: Version string (e.g., "1.0.0")
            host: Hostname or IP where the server can be reached
            port: Port number where the server is listening
            tags: Optional list of tags for categorization
            metadata: Additional metadata about the server
            
        Returns:
            str: A unique ID for the registered server
            
        Raises:
            MCPError: If there's an error registering the server
        """
        try:
            server_id = self.service_discovery.register_server(
                name=name,
                description=description,
                version=version,
                host=host,
                port=port,
                tags=tags,
                metadata=metadata or {}
            )
            
            self.logger.info(f"Registered server: {name} (ID: {server_id})")
            return server_id
            
        except Exception as e:
            self.logger.error(f"Failed to register server {name}: {e}", exc_info=True)
            raise MCPError(f"Failed to register server: {e}")
    
    def unregister_server(self, server_id: str) -> bool:
        """
        Unregister an MCP server from the Global MCP Server.
        
        Args:
            server_id: ID of the server to unregister
            
        Returns:
            bool: True if the server was found and unregistered, False otherwise
            
        Raises:
            MCPError: If there's an error unregistering the server
        """
        try:
            # Remove all tool mappings for this server
            affected_tools = self.router.remove_server_mappings(server_id)
            
            # Unregister the server
            success = self.service_discovery.unregister_server(server_id)
            
            if success:
                self.logger.info(
                    f"Unregistered server ID: {server_id}. "
                    f"Removed mappings for tools: {', '.join(affected_tools) if affected_tools else 'None'}"
                )
            
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to unregister server {server_id}: {e}", exc_info=True)
            raise MCPError(f"Failed to unregister server: {e}")
    
    def record_heartbeat(self, server_id: str) -> bool:
        """
        Record a heartbeat from an MCP server.
        
        Args:
            server_id: ID of the server sending the heartbeat
            
        Returns:
            bool: True if the server is registered, False otherwise
            
        Raises:
            MCPError: If there's an error recording the heartbeat
        """
        try:
            return self.service_discovery.record_heartbeat(server_id)
        except Exception as e:
            self.logger.error(f"Error recording heartbeat for server {server_id}: {e}", exc_info=True)
            raise MCPError(f"Error recording heartbeat: {e}")
    
    # Request Routing
    
    def route_tool_request(
        self,
        tool_name: str,
        strategy: str = "round_robin"
    ) -> Tuple[str, ServerMetadata]:
        """
        Route a tool execution request to the appropriate server.
        
        Args:
            tool_name: Name of the tool to execute
            strategy: Load balancing strategy to use ('round_robin', 'random', 'least_loaded')
            
        Returns:
            Tuple of (server_id, server_metadata) for the selected server
            
        Raises:
            ToolNotFoundError: If no server provides the requested tool
            ServerNotFoundError: If no active servers are available for the tool
            MCPError: If there's an error routing the request
        """
        try:
            # First, verify the tool exists
            tools = self.find_tools(name_pattern=tool_name)
            if not tools:
                raise ToolNotFoundError(f"No tool found with name: {tool_name}")
            
            # Get the best server for this tool
            result = self.router.get_server_for_tool(tool_name, strategy=strategy)
            if not result:
                raise ServerNotFoundError(
                    f"No active servers available for tool: {tool_name}"
                )
            
            server_id, server_metadata = result
            return server_id, server_metadata
            
        except (ToolNotFoundError, ServerNotFoundError):
            raise
        except Exception as e:
            self.logger.error(f"Error routing tool request for {tool_name}: {e}", exc_info=True)
            raise MCPError(f"Error routing tool request: {e}")
    
    def record_tool_completion(self, server_id: str) -> None:
        """
        Record completion of a tool execution.
        
        This should be called after a tool execution completes to update
        the server's load metrics.
        
        Args:
            server_id: ID of the server that executed the tool
            
        Raises:
            MCPError: If there's an error recording the completion
        """
        try:
            self.router.record_tool_completion(server_id)
        except Exception as e:
            self.logger.error(
                f"Error recording tool completion for server {server_id}: {e}",
                exc_info=True
            )
            raise MCPError(f"Error recording tool completion: {e}")
