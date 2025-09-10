"""Unit tests for the ToolRegistry class."""

import pytest
from datetime import datetime, timedelta
from mcp_host.global_server.tool_registry import ToolRegistry, ToolMetadata

def test_register_tool():
    """Test registering a new tool."""
    registry = ToolRegistry()
    tool = ToolMetadata(
        name="test_tool",
        description="A test tool",
        input_schema={"type": "object"},
        output_schema={"type": "string"},
        tags={"test", "demo"},
        server_id="test_server"
    )
    
    tool_id = registry.register_tool(tool)
    assert tool_id is not None
    
    # Verify the tool was registered correctly
    registered_tool = registry.get_tool(tool_id)
    assert registered_tool is not None
    assert registered_tool.name == "test_tool"
    assert registered_tool.description == "A test tool"
    assert "test" in registered_tool.tags
    assert registered_tool.server_id == "test_server"

def test_unregister_tool():
    """Test unregistering a tool."""
    registry = ToolRegistry()
    tool = ToolMetadata(
        name="test_tool",
        description="A test tool",
        input_schema={"type": "object"},
        output_schema={"type": "string"}
    )
    
    tool_id = registry.register_tool(tool)
    assert registry.unregister_tool(tool_id) is True
    assert registry.get_tool(tool_id) is None
    
    # Test unregistering non-existent tool
    assert registry.unregister_tool("non_existent_id") is False

def test_find_tools_by_tags():
    """Test finding tools by tags."""
    registry = ToolRegistry()
    
    # Register multiple tools with different tags
    tool1 = ToolMetadata(
        name="tool1", 
        description="Tool 1", 
        input_schema={}, 
        output_schema={},
        tags={"tag1", "tag2"}
    )
    tool2 = ToolMetadata(
        name="tool2", 
        description="Tool 2", 
        input_schema={}, 
        output_schema={},
        tags={"tag2", "tag3"}
    )
    
    registry.register_tool(tool1)
    registry.register_tool(tool2)
    
    # Find by single tag
    results = registry.find_tools(tags=["tag1"])
    assert len(results) == 1
    assert results[0].name == "tool1"
    
    # Find by multiple tags (AND condition)
    results = registry.find_tools(tags=["tag2", "tag3"])
    assert len(results) == 1
    assert results[0].name == "tool2"

def test_find_tools_by_name():
    """Test finding tools by name pattern."""
    registry = ToolRegistry()
    
    tool = ToolMetadata(
        name="awesome_tool", 
        description="An awesome tool", 
        input_schema={}, 
        output_schema={}
    )
    registry.register_tool(tool)
    
    # Test exact match
    results = registry.find_tools(name_pattern="awesome_tool")
    assert len(results) == 1
    
    # Test partial match
    results = registry.find_tools(name_pattern="some")
    assert len(results) == 1
    
    # Test case-insensitive match
    results = registry.find_tools(name_pattern="AWESOME")
    assert len(results) == 1
    
    # Test no match
    results = registry.find_tools(name_pattern="nonexistent")
    assert len(results) == 0

def test_get_server_tools():
    """Test getting tools by server ID."""
    registry = ToolRegistry()
    
    # Register tools for different servers
    tool1 = ToolMetadata(
        name="server1_tool", 
        description="Tool from server 1", 
        input_schema={}, 
        output_schema={},
        server_id="server1"
    )
    tool2 = ToolMetadata(
        name="server2_tool", 
        description="Tool from server 2", 
        input_schema={}, 
        output_schema={},
        server_id="server2"
    )
    
    registry.register_tool(tool1)
    registry.register_tool(tool2)
    
    # Get tools for server1
    server1_tools = registry.get_server_tools("server1")
    assert len(server1_tools) == 1
    assert server1_tools[0].name == "server1_tool"
    
    # Get tools for non-existent server
    assert len(registry.get_server_tools("nonexistent")) == 0

def test_clear_registry():
    """Test clearing the registry."""
    registry = ToolRegistry()
    
    # Add some tools
    for i in range(5):
        tool = ToolMetadata(
            name=f"tool_{i}", 
            description=f"Tool {i}", 
            input_schema={}, 
            output_schema={},
            tags={"test"}
        )
        registry.register_tool(tool)
    
    # Verify tools were added
    assert len(registry.get_all_tools()) == 5
    
    # Clear the registry
    registry.clear()
    
    # Verify registry is empty
    assert len(registry.get_all_tools()) == 0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
