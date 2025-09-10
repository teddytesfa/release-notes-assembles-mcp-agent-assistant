"""
Tool Registry Service for the Global MCP Server.

This module implements the tool registration and discovery functionality that
allows MCP servers to register their tools and clients to discover available tools.
"""

from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
import uuid


@dataclass
class ToolMetadata:
    """Metadata for a registered tool."""
    name: str
    description: str
    input_schema: dict
    output_schema: dict
    tags: Set[str] = field(default_factory=set)
    server_id: Optional[str] = None
    version: str = "1.0.0"
    last_updated: datetime = field(default_factory=datetime.utcnow)
    is_active: bool = True


class ToolRegistry:
    """
    Central registry for all MCP tools in the system.
    
    This class manages the registration, discovery, and lifecycle of all tools
    available through the MCP system.
    """
    
    def __init__(self):
        self._tools: Dict[str, ToolMetadata] = {}
        self._server_tools: Dict[str, Set[str]] = {}
        self._tags_index: Dict[str, Set[str]] = {}
    
    def register_tool(self, tool_metadata: ToolMetadata) -> str:
        """
        Register a new tool with the registry.
        
        Args:
            tool_metadata: Metadata describing the tool
            
        Returns:
            str: A unique ID for the registered tool
        """
        tool_id = f"tool_{uuid.uuid4().hex[:8]}"
        tool_metadata.last_updated = datetime.utcnow()
        
        # Store the tool
        self._tools[tool_id] = tool_metadata
        
        # Update server-tools index
        if tool_metadata.server_id:
            if tool_metadata.server_id not in self._server_tools:
                self._server_tools[tool_metadata.server_id] = set()
            self._server_tools[tool_metadata.server_id].add(tool_id)
        
        # Update tags index
        for tag in tool_metadata.tags:
            if tag not in self._tags_index:
                self._tags_index[tag] = set()
            self._tags_index[tag].add(tool_id)
        
        return tool_id
    
    def unregister_tool(self, tool_id: str) -> bool:
        """
        Remove a tool from the registry.
        
        Args:
            tool_id: ID of the tool to remove
            
        Returns:
            bool: True if the tool was found and removed, False otherwise
        """
        if tool_id not in self._tools:
            return False
        
        tool = self._tools[tool_id]
        
        # Remove from server-tools index
        if tool.server_id and tool.server_id in self._server_tools:
            self._server_tools[tool.server_id].discard(tool_id)
            if not self._server_tools[tool.server_id]:
                del self._server_tools[tool.server_id]
        
        # Remove from tags index
        for tag in tool.tags:
            if tag in self._tags_index:
                self._tags_index[tag].discard(tool_id)
                if not self._tags_index[tag]:
                    del self._tags_index[tag]
        
        # Remove from main registry
        del self._tools[tool_id]
        return True
    
    def get_tool(self, tool_id: str) -> Optional[ToolMetadata]:
        """
        Retrieve metadata for a specific tool.
        
        Args:
            tool_id: ID of the tool to retrieve
            
        Returns:
            Optional[ToolMetadata]: The tool's metadata, or None if not found
        """
        return self._tools.get(tool_id)
    
    def find_tools(
        self,
        tags: Optional[List[str]] = None,
        server_id: Optional[str] = None,
        name_pattern: Optional[str] = None
    ) -> List[ToolMetadata]:
        """
        Find tools matching the given criteria.
        
        Args:
            tags: List of tags that must all be present
            server_id: ID of the server that registered the tool
            name_pattern: Case-insensitive substring to match against tool names
            
        Returns:
            List[ToolMetadata]: List of matching tools
        """
        # Start with all tools
        tool_ids = set(self._tools.keys())
        
        # Filter by server if specified
        if server_id and server_id in self._server_tools:
            tool_ids.intersection_update(self._server_tools[server_id])
        
        # Filter by tags if specified
        if tags:
            for tag in tags:
                if tag in self._tags_index:
                    tool_ids.intersection_update(self._tags_index[tag])
                else:
                    # If any tag doesn't exist, no tools will match
                    return []
        
        # Filter by name pattern if specified
        if name_pattern:
            name_lower = name_pattern.lower()
            tool_ids = {
                tid for tid in tool_ids
                if name_lower in self._tools[tid].name.lower()
            }
        
        return [self._tools[tid] for tid in tool_ids]
    
    def get_server_tools(self, server_id: str) -> List[ToolMetadata]:
        """
        Get all tools registered by a specific server.
        
        Args:
            server_id: ID of the server
            
        Returns:
            List[ToolMetadata]: List of tools registered by the server
        """
        if server_id not in self._server_tools:
            return []
        return [self._tools[tid] for tid in self._server_tools[server_id]]
    
    def get_all_tools(self) -> List[ToolMetadata]:
        """
        Get all registered tools.
        
        Returns:
            List[ToolMetadata]: List of all registered tools
        """
        return list(self._tools.values())
    
    def clear(self) -> None:
        """Clear all registered tools from the registry."""
        self._tools.clear()
        self._server_tools.clear()
        self._tags_index.clear()
