"""Unit tests for the GlobalMCPServer class."""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from mcp_host.global_server.server import GlobalMCPServer
from mcp_host.global_server.tool_registry import ToolMetadata
from mcp_host.global_server.service_discovery import ServerMetadata

@pytest.fixture
def mcp_server():
    """Create a GlobalMCPServer instance for testing."""
    server = GlobalMCPServer(heartbeat_timeout=1)  # Short timeout for testing
    return server

@pytest.mark.asyncio
async def test_start_stop(mcp_server):
    """Test starting and stopping the MCP server."""
    # Start the server
    await mcp_server.start()
    assert mcp_server._running is True
    assert mcp_server._health_check_task is not None
    
    # Stop the server
    await mcp_server.stop()
    assert mcp_server._running is False
    assert mcp_server._health_check_task is None

@pytest.mark.asyncio
async def test_register_unregister_tool(mcp_server):
    """Test registering and unregistering a tool."""
    await mcp_server.start()
    
    # Register a tool
    tool = ToolMetadata(
        name="test_tool",
        description="A test tool",
        input_schema={"type": "object"},
        output_schema={"type": "string"},
        tags={"test"},
        server_id="test_server"
    )
    
    tool_id = mcp_server.register_tool(tool)
    assert tool_id is not None
    
    # Verify the tool was registered
    tools = mcp_server.find_tools(name_pattern="test_tool")
    assert len(tools) == 1
    assert tools[0].name == "test_tool"
    
    # Unregister the tool
    assert mcp_server.unregister_tool(tool_id) is True
    
    # Verify the tool was unregistered
    tools = mcp_server.find_tools(name_pattern="test_tool")
    assert len(tools) == 0
    
    await mcp_server.stop()

@pytest.mark.asyncio
async def test_register_unregister_server(mcp_server):
    """Test registering and unregistering a server."""
    await mcp_server.start()
    
    # Register a server
    server_id = mcp_server.register_server(
        name="Test Server",
        description="A test server",
        version="1.0.0",
        host="localhost",
        port=8000,
        tags=["test"]
    )
    
    assert server_id is not None
    
    # Verify the server was registered
    servers = mcp_server.service_discovery.find_servers(tags=["test"])
    assert len(servers) == 1
    assert servers[0].name == "Test Server"
    
    # Unregister the server
    assert mcp_server.unregister_server(server_id) is True
    
    # Verify the server was unregistered
    servers = mcp_server.service_discovery.find_servers(tags=["test"])
    assert len(servers) == 0
    
    await mcp_server.stop()

@pytest.mark.asyncio
async def test_heartbeat(mcp_server):
    """Test recording a server heartbeat."""
    await mcp_server.start()
    
    # Register a server
    server_id = mcp_server.register_server("Test", "Test", "1.0.0", "localhost", 8000)
    
    # Record a heartbeat
    assert mcp_server.record_heartbeat(server_id) is True
    
    # Verify the server is active
    server = mcp_server.service_discovery.get_server(server_id)
    assert server.is_active is True
    
    await mcp_server.stop()

@pytest.mark.asyncio
async def test_route_tool_request(mcp_server):
    """Test routing a tool execution request."""
    await mcp_server.start()
    
    # Register a server and a tool
    server_id = mcp_server.register_server("Test", "Test", "1.0.0", "localhost", 8000)
    
    tool = ToolMetadata(
        name="test_tool",
        description="A test tool",
        input_schema={"type": "object"},
        output_schema={"type": "string"},
        server_id=server_id
    )
    
    tool_id = mcp_server.register_tool(tool)
    
    # Update the router's tool-to-server mapping
    mcp_server.router.update_tool_mapping(tool.name, server_id)
    
    # Route a tool request
    result = mcp_server.route_tool_request("test_tool")
    assert result is not None
    result_server_id, _ = result
    assert result_server_id == server_id
    
    await mcp_server.stop()

@pytest.mark.asyncio
async def test_health_check_loop(mcp_server, monkeypatch):
    """Test the health check background task."""
    # Mock the sleep to avoid waiting
    sleep_calls = 0
    async def mock_sleep(seconds):
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls > 1:  # Only run the loop twice
            mcp_server._running = False
    
    monkeypatch.setattr(asyncio, "sleep", mock_sleep)
    
    # Register a server with a short timeout
    server_id = mcp_server.register_server("Test", "Test", "1.0.0", "localhost", 8000)
    
    # Start the server (which starts the health check loop)
    await mcp_server.start()
    
    # Let the loop run a couple of times
    await asyncio.sleep(0.1)
    
    # The server should still be active because we recorded a heartbeat during registration
    server = mcp_server.service_discovery.get_server(server_id)
    assert server.is_active is True
    
    # Stop the server
    await mcp_server.stop()

def test_find_tools(mcp_server):
    """Test finding tools with various filters."""
    # Register multiple tools with different properties
    tool1 = ToolMetadata(
        name="tool1",
        description="Tool 1",
        input_schema={"type": "object"},
        output_schema={"type": "string"},
        tags={"tag1", "tag2"},
        server_id="server1"
    )
    
    tool2 = ToolMetadata(
        name="tool2",
        description="Tool 2",
        input_schema={"type": "object"},
        output_schema={"type": "number"},
        tags={"tag2", "tag3"},
        server_id="server2"
    )
    
    mcp_server.register_tool(tool1)
    mcp_server.register_tool(tool2)
    
    # Find by name
    tools = mcp_server.find_tools(name_pattern="tool1")
    assert len(tools) == 1
    assert tools[0].name == "tool1"
    
    # Find by tag
    tools = mcp_server.find_tools(tags=["tag3"])
    assert len(tools) == 1
    assert tools[0].name == "tool2"
    
    # Find by server
    tools = mcp_server.find_tools(server_id="server1")
    assert len(tools) == 1
    assert tools[0].name == "tool1"
    
    # Find with multiple criteria
    tools = mcp_server.find_tools(name_pattern="tool", tags=["tag2"])
    assert len(tools) == 2  # Both tools have "tool" in name and "tag2"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
