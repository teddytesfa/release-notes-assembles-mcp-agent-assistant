"""Unit tests for the Router class."""

import pytest
from unittest.mock import MagicMock
from mcp_host.global_server.router import Router
from mcp_host.global_server.service_discovery import ServiceDiscovery, ServerMetadata

@pytest.fixture
def mock_service_discovery():
    """Create a mock ServiceDiscovery for testing."""
    # Create a real ServiceDiscovery instance but mock its methods
    service_discovery = ServiceDiscovery()
    
    # Register some test servers
    server1 = ServerMetadata(
        server_id="server1",
        name="Server 1",
        description="Test Server 1",
        version="1.0.0",
        host="localhost",
        port=8001,
        is_active=True
    )
    
    server2 = ServerMetadata(
        server_id="server2",
        name="Server 2",
        description="Test Server 2",
        version="1.0.0",
        host="localhost",
        port=8002,
        is_active=True
    )
    
    # Add servers to the service discovery
    service_discovery._servers = {
        "server1": server1,
        "server2": server2
    }
    
    # Mock the get_server method
    def get_server(server_id):
        return service_discovery._servers.get(server_id)
    
    service_discovery.get_server = get_server
    
    return service_discovery

def test_update_tool_mapping(mock_service_discovery):
    """Test updating the tool-to-server mapping."""
    router = Router(mock_service_discovery)
    
    # Update mapping for a tool
    router.update_tool_mapping("test_tool", "server1")
    
    # Verify the mapping was updated
    assert "test_tool" in router._tool_to_servers
    assert "server1" in router._tool_to_servers["test_tool"]
    assert "server1" in router._server_load
    assert router._server_load["server1"] == 0

def test_remove_tool_mapping(mock_service_discovery):
    """Test removing a tool-to-server mapping."""
    router = Router(mock_service_discovery)
    
    # Add a mapping
    router.update_tool_mapping("test_tool", "server1")
    assert "test_tool" in router._tool_to_servers
    
    # Remove the mapping
    router.remove_tool_mapping("test_tool", "server1")
    assert "test_tool" not in router._tool_to_servers

def test_remove_server_mappings(mock_service_discovery):
    """Test removing all mappings for a server."""
    router = Router(mock_service_discovery)
    
    # Add mappings for multiple tools to server1
    router.update_tool_mapping("tool1", "server1")
    router.update_tool_mapping("tool2", "server1")
    router.update_tool_mapping("tool3", "server2")
    
    # Remove all mappings for server1
    affected_tools = router.remove_server_mappings("server1")
    
    # Verify the correct tools were affected
    assert set(affected_tools) == {"tool1", "tool2"}
    
    # Verify the mappings were removed
    assert "tool1" not in router._tool_to_servers
    assert "tool2" not in router._tool_to_servers
    assert "tool3" in router._tool_to_servers  # Should still exist
    
    # Verify server1 was removed from load tracking
    assert "server1" not in router._server_load

def test_round_robin_routing(mock_service_discovery):
    """Test round-robin load balancing strategy."""
    router = Router(mock_service_discovery)
    
    # Add multiple servers for the same tool
    router.update_tool_mapping("test_tool", "server1")
    router.update_tool_mapping("test_tool", "server2")
    
    # First request should go to server1
    result = router.get_server_for_tool("test_tool", strategy="round_robin")
    assert result is not None
    server_id, _ = result
    assert server_id == "server1"
    
    # Second request should go to server2
    result = router.get_server_for_tool("test_tool", strategy="round_robin")
    assert result is not None
    server_id, _ = result
    assert server_id == "server2"
    
    # Third request should wrap around to server1
    result = router.get_server_for_tool("test_tool", strategy="round_robin")
    assert result is not None
    server_id, _ = result
    assert server_id == "server1"

def test_random_routing(mock_service_discovery, monkeypatch):
    """Test random load balancing strategy."""
    # Mock random.choice to return a predictable value
    def mock_choice(seq):
        return seq[0]  # Always return first element
    
    monkeypatch.setattr("random.choice", mock_choice)
    
    router = Router(mock_service_discovery)
    router.update_tool_mapping("test_tool", "server1")
    router.update_tool_mapping("test_tool", "server2")
    
    # With our mock, should always return the first server
    result = router.get_server_for_tool("test_tool", strategy="random")
    assert result is not None
    server_id, _ = result
    assert server_id == "server1"  # Because our mock returns first element

def test_least_loaded_routing(mock_service_discovery):
    """Test least-loaded load balancing strategy."""
    router = Router(mock_service_discovery)
    
    # Add multiple servers for the same tool
    router.update_tool_mapping("test_tool", "server1")
    router.update_tool_mapping("test_tool", "server2")
    
    # Initially, both servers have 0 load, so it should choose the first one
    result = router.get_server_for_tool("test_tool", strategy="least_loaded")
    assert result is not None
    server_id, _ = result
    assert server_id == "server1"
    
    # Record that server1 now has some load
    router._server_load["server1"] = 5
    
    # Next request should go to server2 (lower load)
    result = router.get_server_for_tool("test_tool", strategy="least_loaded")
    assert result is not None
    server_id, _ = result
    assert server_id == "server2"

def test_record_tool_completion(mock_service_discovery):
    """Test recording tool completion and updating server load."""
    router = Router(mock_service_discovery)
    
    # Add a server and record some load
    router.update_tool_mapping("test_tool", "server1")
    router._server_load["server1"] = 3
    
    # Record completion of a tool
    router.record_tool_completion("server1")
    
    # Verify load was decremented
    assert router._server_load["server1"] == 2
    
    # Test that load doesn't go below 0
    router._server_load["server1"] = 0
    router.record_tool_completion("server1")
    assert router._server_load["server1"] == 0

def test_get_server_load(mock_service_discovery):
    """Test getting the current load for a server."""
    router = Router(mock_service_discovery)
    
    # Test with no load recorded
    assert router.get_server_load("server1") == 0
    
    # Test with some load
    router._server_load["server1"] = 5
    assert router.get_server_load("server1") == 5

def test_clear_router():
    """Test clearing the router's state."""
    service_discovery = ServiceDiscovery()
    router = Router(service_discovery)
    
    # Add some data
    router.update_tool_mapping("tool1", "server1")
    router.update_tool_mapping("tool2", "server2")
    
    # Clear the router
    router.clear()
    
    # Verify all data was cleared
    assert not router._tool_to_servers
    assert not router._server_load

def test_get_tool_servers(mock_service_discovery):
    """Test getting all servers that provide a specific tool."""
    router = Router(mock_service_discovery)
    
    # Add multiple servers for a tool
    router.update_tool_mapping("test_tool", "server1")
    router.update_tool_mapping("test_tool", "server2")
    
    # Get all servers for the tool
    servers = router.get_tool_servers("test_tool")
    assert set(servers) == {"server1", "server2"}
    
    # Test with non-existent tool
    assert router.get_tool_servers("non_existent_tool") == []

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
