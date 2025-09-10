"""
Service Discovery for the Global MCP Server.

This module implements the service discovery functionality that allows MCP servers
to register themselves and clients to discover available services.
"""

from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import uuid


@dataclass
class ServerMetadata:
    """Metadata for a registered MCP server."""
    server_id: str
    name: str
    description: str
    version: str
    host: str
    port: int
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)
    tags: Set[str] = field(default_factory=set)
    metadata: dict = field(default_factory=dict)
    is_active: bool = True


class ServiceDiscovery:
    """
    Service Discovery component for the Global MCP Server.
    
    This class manages the registration, health checking, and discovery of
    MCP servers in the system.
    """
    
    def __init__(self, heartbeat_timeout: int = 300):
        """
        Initialize the ServiceDiscovery.
        
        Args:
            heartbeat_timeout: Number of seconds after which a server is 
                             considered offline if no heartbeat is received.
        """
        self._servers: Dict[str, ServerMetadata] = {}
        self._tags_index: Dict[str, Set[str]] = {}
        self.heartbeat_timeout = timedelta(seconds=heartbeat_timeout)
    
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
        Register a new MCP server.
        
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
        """
        server_id = f"srv_{uuid.uuid4().hex[:8]}"
        now = datetime.utcnow()
        
        server = ServerMetadata(
            server_id=server_id,
            name=name,
            description=description,
            version=version,
            host=host,
            port=port,
            last_heartbeat=now,
            tags=set(tags or []),
            metadata=metadata or {}
        )
        
        self._servers[server_id] = server
        
        # Update tags index
        for tag in server.tags:
            if tag not in self._tags_index:
                self._tags_index[tag] = set()
            self._tags_index[tag].add(server_id)
        
        return server_id
    
    def unregister_server(self, server_id: str) -> bool:
        """
        Remove a server from the discovery service.
        
        Args:
            server_id: ID of the server to remove
            
        Returns:
            bool: True if the server was found and removed, False otherwise
        """
        if server_id not in self._servers:
            return False
        
        # Remove from tags index
        server = self._servers[server_id]
        for tag in server.tags:
            if tag in self._tags_index:
                self._tags_index[tag].discard(server_id)
                if not self._tags_index[tag]:
                    del self._tags_index[tag]
        
        # Remove from main registry
        del self._servers[server_id]
        return True
    
    def record_heartbeat(self, server_id: str) -> bool:
        """
        Record a heartbeat from a server.
        
        Args:
            server_id: ID of the server sending the heartbeat
            
        Returns:
            bool: True if the server is registered, False otherwise
        """
        if server_id not in self._servers:
            return False
        
        self._servers[server_id].last_heartbeat = datetime.utcnow()
        self._servers[server_id].is_active = True
        return True
    
    def check_health(self) -> None:
        """
        Check the health of all registered servers and mark inactive ones.
        
        This should be called periodically to update server status based on
        heartbeat activity.
        """
        now = datetime.utcnow()
        for server in self._servers.values():
            if now - server.last_heartbeat > self.heartbeat_timeout:
                server.is_active = False
    
    def find_servers(
        self,
        tags: Optional[List[str]] = None,
        name_pattern: Optional[str] = None,
        active_only: bool = True
    ) -> List[ServerMetadata]:
        """
        Find servers matching the given criteria.
        
        Args:
            tags: List of tags that must all be present
            name_pattern: Case-insensitive substring to match against server names
            active_only: If True, only return servers that are currently active
            
        Returns:
            List[ServerMetadata]: List of matching servers
        """
        # Start with all servers (or active ones if requested)
        servers = [
            server for server in self._servers.values()
            if not active_only or server.is_active
        ]
        
        # Filter by tags if specified
        if tags:
            tag_sets = [
                set(self._tags_index.get(tag, set()))
                for tag in tags
            ]
            if not tag_sets:
                return []
                
            # Find intersection of all tag sets
            matching_server_ids = set.intersection(*tag_sets)
            servers = [s for s in servers if s.server_id in matching_server_ids]
        
        # Filter by name pattern if specified
        if name_pattern:
            name_lower = name_pattern.lower()
            servers = [
                s for s in servers
                if name_lower in s.name.lower()
            ]
        
        return servers
    
    def get_server(self, server_id: str) -> Optional[ServerMetadata]:
        """
        Get metadata for a specific server.
        
        Args:
            server_id: ID of the server to retrieve
            
        Returns:
            Optional[ServerMetadata]: The server's metadata, or None if not found
        """
        return self._servers.get(server_id)
    
    def get_all_servers(self, active_only: bool = True) -> List[ServerMetadata]:
        """
        Get all registered servers.
        
        Args:
            active_only: If True, only return active servers
            
        Returns:
            List[ServerMetadata]: List of all registered servers
        """
        if active_only:
            return [s for s in self._servers.values() if s.is_active]
        return list(self._servers.values())
    
    def clear(self) -> None:
        """Clear all registered servers from the discovery service."""
        self._servers.clear()
        self._tags_index.clear()
