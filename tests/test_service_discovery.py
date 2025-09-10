"""Unit tests for the ServiceDiscovery class."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch

from mcp_host.global_server.service_discovery import ServiceDiscovery, ServerMetadata

def test_register_server():
    """Test registering a new server."""
    discovery = ServiceDiscovery()
    server_id = discovery.register_server(
        name="Test Server",
        description="A test server",
        version="1.0.0",
        host="localhost",
        port=8000,
        tags=["test", "api"]
    )
    
    assert server_id is not None
    
    # Verify server was registered
    server = discovery.get_server(server_id)
    assert server is not None
    assert server.name == "Test Server"
    assert server.host == "localhost"
    assert server.port == 8000
    assert "test" in server.tags
    assert server.is_active is True

def test_unregister_server():
    """Test unregistering a server."""
    discovery = ServiceDiscovery()
    server_id = discovery.register_server("Test", "Test", "1.0.0", "localhost", 8000)
    
    assert discovery.unregister_server(server_id) is True
    assert discovery.get_server(server_id) is None
    
    # Test unregistering non-existent server
    assert discovery.unregister_server("non_existent_id") is False

def test_heartbeat():
    """Test server heartbeats and health checking."""
    discovery = ServiceDiscovery(heartbeat_timeout=1)  # Short timeout for testing
    server_id = discovery.register_server("Test", "Test", "1.0.0", "localhost", 8000)
    
    # Record initial heartbeat
    initial_time = discovery.get_server(server_id).last_heartbeat
    
    # Record another heartbeat
    assert discovery.record_heartbeat(server_id) is True
    
    # Verify last_heartbeat was updated
    assert discovery.get_server(server_id).last_heartbeat > initial_time
    
    # Test heartbeat for non-existent server
    assert discovery.record_heartbeat("non_existent_id") is False

def test_health_check():
    """Test server health checking."""
    # Use a very short timeout for testing
    discovery = ServiceDiscovery(heartbeat_timeout=0.1)
    server_id = discovery.register_server("Test", "Test", "1.0.0", "localhost", 8000)
    
    # Server should be active initially
    assert discovery.get_server(server_id).is_active is True
    
    # Simulate time passing without heartbeats
    import time
    time.sleep(0.2)  # Ensure we've passed the heartbeat timeout
    
    # Run health check - should mark server as inactive
    discovery.check_health()
    
    # Server should be marked as inactive
    server = discovery.get_server(server_id)
    assert server is not None
    assert server.is_active is False

def test_find_servers_by_tags():
    """Test finding servers by tags."""
    discovery = ServiceDiscovery()
    
    # Register multiple servers with different tags
    server1 = discovery.register_server(
        "Server 1", "Test 1", "1.0.0", "localhost", 8001, ["api", "v1"]
    )
    server2 = discovery.register_server(
        "Server 2", "Test 2", "1.0.0", "localhost", 8002, ["api", "v2"]
    )
    
    # Find by single tag
    results = discovery.find_servers(tags=["v1"])
    assert len(results) == 1
    assert results[0].server_id == server1
    
    # Find by multiple tags (AND condition)
    results = discovery.find_servers(tags=["api", "v2"])
    assert len(results) == 1
    assert results[0].server_id == server2

def test_find_servers_by_name():
    """Test finding servers by name pattern."""
    discovery = ServiceDiscovery()
    
    discovery.register_server("Auth Service", "Authentication", "1.0.0", "localhost", 8000)
    discovery.register_server("User Service", "User Management", "1.0.0", "localhost", 8001)
    
    # Test exact match
    results = discovery.find_servers(name_pattern="Auth Service")
    assert len(results) == 1
    
    # Test partial match
    results = discovery.find_servers(name_pattern="Service")
    assert len(results) == 2
    
    # Test case-insensitive match
    results = discovery.find_servers(name_pattern="user")
    assert len(results) == 1
    
    # Test no match
    results = discovery.find_servers(name_pattern="nonexistent")
    assert len(results) == 0

def test_get_all_servers():
    """Test getting all servers."""
    discovery = ServiceDiscovery(heartbeat_timeout=10)  # 10 second timeout
    
    # Add some servers
    for i in range(3):
        discovery.register_server(
            f"Server {i}", f"Server {i}", "1.0.0", "localhost", 8000 + i, ["test"]
        )
    
    # Test getting all servers
    servers = discovery.get_all_servers()
    assert len(servers) == 3
    
    # Test getting only active servers
    # Make one server inactive by setting its last_heartbeat to a time older than the timeout
    server_id = servers[0].server_id
    with patch('mcp_host.global_server.service_discovery.datetime') as mock_datetime:
        # Set the current time to now
        now = datetime.utcnow()
        mock_datetime.utcnow.return_value = now
        
        # Record heartbeats for active servers
        for server in servers[1:]:
            discovery.record_heartbeat(server.server_id)
        
        # Set the first server's last_heartbeat to be older than the timeout
        discovery._servers[server_id].last_heartbeat = now - timedelta(seconds=20)
        
        # Run health check to update status
        discovery.check_health()
        
        # Get active servers - should be 2 (the ones with recent heartbeats)
        active_servers = discovery.get_all_servers(active_only=True)
        assert len(active_servers) == 2
        
        # The inactive server should not be in the active list
        active_server_ids = [s.server_id for s in active_servers]
        assert server_id not in active_server_ids

def test_clear():
    """Test clearing the service discovery."""
    discovery = ServiceDiscovery()
    
    # Add some servers
    for i in range(5):
        discovery.register_server(
            f"Server {i}", f"Server {i}", "1.0.0", "localhost", 8000 + i, ["test"]
        )
    
    # Verify servers were added
    assert len(discovery.get_all_servers()) == 5
    
    # Clear the discovery
    discovery.clear()
    
    # Verify discovery is empty
    assert len(discovery.get_all_servers()) == 0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
