"""
Exceptions for the MCP Host implementation.

This module defines custom exceptions used throughout the MCP Host and its components.
"""

class MCPError(Exception):
    """Base class for all MCP-related exceptions."""
    pass


class ToolNotFoundError(MCPError):
    """Raised when a requested tool is not found in the registry."""
    pass


class ServerNotFoundError(MCPError):
    """Raised when a requested server is not found or not available."""
    pass


class ToolExecutionError(MCPError):
    """Raised when there's an error executing a tool."""
    pass


class RegistrationError(MCPError):
    """Raised when there's an error registering a tool or server."""
    pass


class AuthenticationError(MCPError):
    """Raised when there's an authentication or authorization error."""
    pass


class ValidationError(MCPError):
    """Raised when there's a validation error with input data."""
    pass


class RateLimitExceededError(MCPError):
    """Raised when a rate limit has been exceeded."""
    pass


class TimeoutError(MCPError):
    """Raised when an operation times out."""
    pass


class ConfigurationError(MCPError):
    """Raised when there's an error in the configuration."""
    pass
