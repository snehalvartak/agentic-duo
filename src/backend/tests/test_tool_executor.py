"""
Unit tests for ToolExecutor

Tests tool registration, execution, error handling, and response formatting.
"""

import pytest
from unittest.mock import Mock, AsyncMock

from google.genai.types import FunctionDeclaration

from slidekick.tool_executor import ToolExecutor
from slidekick.exceptions import ToolExecutorError


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def tool_executor():
    """Create a ToolExecutor instance for testing."""
    return ToolExecutor(verbose=False)  # Disable verbose for clean test output


@pytest.fixture
def sample_tool():
    """Create a sample async tool function."""
    async def sample_func(message: str = "test"):
        """Sample tool for testing."""
        return f"Executed with: {message}"
    
    return sample_func


@pytest.fixture
def sample_declaration():
    """Create a sample FunctionDeclaration."""
    return FunctionDeclaration(
        name="sample_func",
        description="A sample test function"
    )


# =============================================================================
# Initialization Tests
# =============================================================================


class TestToolExecutorInitialization:
    """Tests for ToolExecutor initialization."""
    
    @pytest.mark.asyncio
    async def test_initialization_verbose(self):
        """Test that ToolExecutor initializes correctly with verbose=True."""
        executor = ToolExecutor(verbose=True)
        
        assert executor.verbose is True
        assert len(executor._tools) == 0
        assert len(executor.declarations) == 0
    
    @pytest.mark.asyncio
    async def test_initialization_non_verbose(self):
        """Test that ToolExecutor initializes correctly with verbose=False."""
        executor = ToolExecutor(verbose=False)
        
        assert executor.verbose is False
        assert len(executor._tools) == 0
    
    @pytest.mark.asyncio
    async def test_tools_property_returns_declarations(self, tool_executor, sample_tool):
        """Test that tools property returns list of declarations."""
        decl = FunctionDeclaration(name="tool1", description="Test")
        tool_executor.register_tool("tool1", sample_tool, decl)
        
        tools = tool_executor.tools
        assert isinstance(tools, list)
        assert len(tools) == 1
        assert isinstance(tools[0], FunctionDeclaration)


# =============================================================================
# Tool Registration Tests
# =============================================================================


class TestToolRegistration:
    """Tests for tool registration functionality."""
    
    @pytest.mark.asyncio
    async def test_register_tool(self, tool_executor, sample_tool, sample_declaration):
        """Test registering a tool."""
        tool_executor.register_tool("sample_func", sample_tool, sample_declaration)
        
        assert tool_executor.has_tool("sample_func")
        assert "sample_func" in tool_executor.declarations
        assert len(tool_executor.tools) == 1
    
    @pytest.mark.asyncio
    async def test_register_duplicate_tool_raises_error(
        self, tool_executor, sample_tool, sample_declaration
    ):
        """Test that registering a duplicate tool raises an error."""
        tool_executor.register_tool("sample_func", sample_tool, sample_declaration)
        
        with pytest.raises(ValueError, match="already registered"):
            tool_executor.register_tool("sample_func", sample_tool, sample_declaration)
    
    @pytest.mark.asyncio
    async def test_register_non_async_tool_raises_error(
        self, tool_executor, sample_declaration
    ):
        """Test that registering a non-async function raises an error."""
        def sync_func():
            return "sync"
        
        with pytest.raises(ValueError, match="must be an async function"):
            tool_executor.register_tool("sync_func", sync_func, sample_declaration)
    
    @pytest.mark.asyncio
    async def test_register_multiple_tools(self, tool_executor):
        """Test registering multiple tools."""
        async def tool1():
            return "tool1"
        
        async def tool2():
            return "tool2"
        
        decl1 = FunctionDeclaration(name="tool1", description="First tool")
        decl2 = FunctionDeclaration(name="tool2", description="Second tool")
        
        tool_executor.register_tool("tool1", tool1, decl1)
        tool_executor.register_tool("tool2", tool2, decl2)
        
        assert len(tool_executor.tools) == 2
        assert tool_executor.has_tool("tool1")
        assert tool_executor.has_tool("tool2")


# =============================================================================
# Tool Query Tests
# =============================================================================


class TestToolQueries:
    """Tests for tool query methods."""
    
    @pytest.mark.asyncio
    async def test_has_tool_true(self, tool_executor, sample_tool, sample_declaration):
        """Test has_tool returns True for registered tool."""
        tool_executor.register_tool("sample_func", sample_tool, sample_declaration)
        
        assert tool_executor.has_tool("sample_func") is True
    
    @pytest.mark.asyncio
    async def test_has_tool_false(self, tool_executor):
        """Test has_tool returns False for unregistered tool."""
        assert tool_executor.has_tool("nonexistent_tool") is False
    
    @pytest.mark.asyncio
    async def test_tools_property(self, tool_executor, sample_tool):
        """Test tools property returns all declarations."""
        decl1 = FunctionDeclaration(name="tool1", description="First")
        decl2 = FunctionDeclaration(name="tool2", description="Second")
        
        async def tool1():
            return "1"
        async def tool2():
            return "2"
        
        tool_executor.register_tool("tool1", tool1, decl1)
        tool_executor.register_tool("tool2", tool2, decl2)
        
        declarations = tool_executor.tools
        assert len(declarations) == 2
        assert all(isinstance(d, FunctionDeclaration) for d in declarations)


# =============================================================================
# Tool Execution Tests
# =============================================================================


class TestToolExecution:
    """Tests for tool execution functionality."""
    
    @pytest.mark.asyncio
    async def test_execute_tool_success(
        self, tool_executor, sample_tool, sample_declaration
    ):
        """Test executing a registered tool successfully."""
        tool_executor.register_tool("sample_func", sample_tool, sample_declaration)
        
        response = await tool_executor.execute_tool(
            func_name="sample_func",
            func_id="test_id_123",
            args={"message": "hello"}
        )
        
        assert response.id == "test_id_123"
        assert response.name == "sample_func"
        assert response.response["status"] == "success"
        assert "Executed with: hello" in str(response.response["data"])
        assert response.response["error"] is None
    
    @pytest.mark.asyncio
    async def test_execute_tool_without_args(self, tool_executor, sample_declaration):
        """Test executing a tool with default arguments."""
        async def tool_with_default(value: str = "default"):
            return f"Got: {value}"
        
        tool_executor.register_tool("tool_with_default", tool_with_default, sample_declaration)
        
        response = await tool_executor.execute_tool(
            func_name="tool_with_default",
            func_id="test_id",
            args={}
        )
        
        assert response.response["status"] == "success"
        assert "Got: default" in str(response.response["data"])
    
    @pytest.mark.asyncio
    async def test_execute_tool_with_none_args(self, tool_executor, sample_declaration):
        """Test executing a tool with None args (should use empty dict)."""
        async def simple_tool():
            return "executed"
        
        tool_executor.register_tool("simple_tool", simple_tool, sample_declaration)
        
        response = await tool_executor.execute_tool(
            func_name="simple_tool",
            func_id="test_id",
            args=None
        )
        
        assert response.response["status"] == "success"
        assert response.response["data"] == "executed"
    
    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self, tool_executor):
        """Test executing a tool that doesn't exist."""
        response = await tool_executor.execute_tool(
            func_name="unknown_tool",
            func_id="test_id_456",
            args={}
        )
        
        assert response.id == "test_id_456"
        assert response.name == "unknown_tool"
        assert response.response["status"] == "error"
        assert "not registered" in response.response["error"]
        assert response.response["data"] is None
    
    @pytest.mark.asyncio
    async def test_execute_tool_with_exception(self, tool_executor, sample_declaration):
        """Test executing a tool that raises an exception."""
        async def error_tool():
            raise ValueError("Intentional error")
        
        tool_executor.register_tool("error_tool", error_tool, sample_declaration)
        
        response = await tool_executor.execute_tool(
            func_name="error_tool",
            func_id="test_id_789",
            args={}
        )
        
        assert response.id == "test_id_789"
        assert response.response["status"] == "error"
        assert "Intentional error" in response.response["error"]
        assert response.response["data"] is None
    
    @pytest.mark.asyncio
    async def test_execute_tool_preserves_function_id(self, tool_executor, sample_tool, sample_declaration):
        """Test that function ID is preserved in response."""
        tool_executor.register_tool("sample_func", sample_tool, sample_declaration)
        
        unique_id = "gemini-call-abc123xyz"
        response = await tool_executor.execute_tool(
            func_name="sample_func",
            func_id=unique_id,
            args={"message": "test"}
        )
        
        assert response.id == unique_id


# =============================================================================
# Tool Execution with Complex Args Tests
# =============================================================================


class TestToolExecutionComplexArgs:
    """Tests for tool execution with complex argument types."""
    
    @pytest.mark.asyncio
    async def test_execute_tool_with_dict_return(self, tool_executor, sample_declaration):
        """Test tool that returns a dictionary."""
        async def dict_tool():
            return {"key": "value", "number": 42}
        
        tool_executor.register_tool("dict_tool", dict_tool, sample_declaration)
        
        response = await tool_executor.execute_tool(
            func_name="dict_tool",
            func_id="test_id",
            args={}
        )
        
        assert response.response["status"] == "success"
        assert response.response["data"] == {"key": "value", "number": 42}
    
    @pytest.mark.asyncio
    async def test_execute_tool_with_multiple_args(self, tool_executor, sample_declaration):
        """Test tool with multiple arguments."""
        async def multi_arg_tool(a: str, b: int, c: bool = False):
            return f"a={a}, b={b}, c={c}"
        
        tool_executor.register_tool("multi_arg_tool", multi_arg_tool, sample_declaration)
        
        response = await tool_executor.execute_tool(
            func_name="multi_arg_tool",
            func_id="test_id",
            args={"a": "hello", "b": 42, "c": True}
        )
        
        assert response.response["status"] == "success"
        assert response.response["data"] == "a=hello, b=42, c=True"
    
    @pytest.mark.asyncio
    async def test_execute_tool_with_optional_args(self, tool_executor, sample_declaration):
        """Test tool with optional arguments."""
        async def optional_args_tool(required: str, optional: str = "default"):
            return f"{required} - {optional}"
        
        tool_executor.register_tool("optional_args_tool", optional_args_tool, sample_declaration)
        
        # Without optional arg
        response = await tool_executor.execute_tool(
            func_name="optional_args_tool",
            func_id="test_id",
            args={"required": "hello"}
        )
        
        assert response.response["data"] == "hello - default"
        
        # With optional arg
        response = await tool_executor.execute_tool(
            func_name="optional_args_tool",
            func_id="test_id2",
            args={"required": "hello", "optional": "world"}
        )
        
        assert response.response["data"] == "hello - world"


# =============================================================================
# Verbose Mode Tests
# =============================================================================


class TestVerboseMode:
    """Tests for verbose mode logging behavior."""
    
    @pytest.mark.asyncio
    async def test_verbose_mode_logs_registration(self, caplog):
        """Test that verbose mode logs tool registration."""
        executor = ToolExecutor(verbose=True)
        
        async def test_tool():
            return "test"
        
        decl = FunctionDeclaration(name="test_tool", description="Test")
        
        with caplog.at_level("INFO"):
            executor.register_tool("test_tool", test_tool, decl)
        
        assert "Registered tool: test_tool" in caplog.text
    
    @pytest.mark.asyncio
    async def test_verbose_mode_logs_execution(self, caplog):
        """Test that verbose mode logs tool execution."""
        executor = ToolExecutor(verbose=True)
        
        async def test_tool():
            return "test"
        
        decl = FunctionDeclaration(name="test_tool", description="Test")
        executor.register_tool("test_tool", test_tool, decl)
        
        with caplog.at_level("INFO"):
            await executor.execute_tool("test_tool", "test_id", {})
        
        assert "Executing tool function" in caplog.text
        assert "completed successfully" in caplog.text
    
    @pytest.mark.asyncio
    async def test_non_verbose_mode_no_logs(self, caplog):
        """Test that non-verbose mode doesn't log."""
        executor = ToolExecutor(verbose=False)
        
        async def test_tool():
            return "test"
        
        decl = FunctionDeclaration(name="test_tool", description="Test")
        executor.register_tool("test_tool", test_tool, decl)
        
        with caplog.at_level("INFO"):
            await executor.execute_tool("test_tool", "test_id", {})
        
        # Should not have execution logs
        assert "Executing tool function" not in caplog.text


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling in tool execution."""
    
    @pytest.mark.asyncio
    async def test_exception_creates_tool_executor_error(self, tool_executor, sample_declaration):
        """Test that exceptions are wrapped in ToolExecutorError."""
        async def failing_tool():
            raise RuntimeError("Something went wrong")
        
        tool_executor.register_tool("failing_tool", failing_tool, sample_declaration)
        
        response = await tool_executor.execute_tool(
            func_name="failing_tool",
            func_id="test_id",
            args={}
        )
        
        assert response.response["status"] == "error"
        assert "Something went wrong" in response.response["error"]
    
    @pytest.mark.asyncio
    async def test_missing_required_arg_error(self, tool_executor, sample_declaration):
        """Test error when required argument is missing."""
        async def required_arg_tool(required_param: str):
            return required_param
        
        tool_executor.register_tool("required_arg_tool", required_arg_tool, sample_declaration)
        
        response = await tool_executor.execute_tool(
            func_name="required_arg_tool",
            func_id="test_id",
            args={}  # Missing required_param
        )
        
        assert response.response["status"] == "error"
        assert "error" in response.response
    
    @pytest.mark.asyncio
    async def test_async_exception_handling(self, tool_executor, sample_declaration):
        """Test handling of async exceptions."""
        async def async_failing_tool():
            import asyncio
            await asyncio.sleep(0.01)
            raise ConnectionError("Network failure")
        
        tool_executor.register_tool("async_failing_tool", async_failing_tool, sample_declaration)
        
        response = await tool_executor.execute_tool(
            func_name="async_failing_tool",
            func_id="test_id",
            args={}
        )
        
        assert response.response["status"] == "error"
        assert "Network failure" in response.response["error"]
