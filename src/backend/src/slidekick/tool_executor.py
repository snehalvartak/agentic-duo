"""
Tool Executor Module

Handles tool registration and execution for the Gemini Live API.
Extracted from intent_client.py for reusability across the application.

This module provides:
- Tool registration system with function declarations
- Tool execution with error handling
- Function response generation for Gemini sessions
"""

import asyncio
import logging
from typing import Any, Callable

from google.genai.types import FunctionDeclaration, FunctionResponse

from slidekick.exceptions import ToolExecutorError

logger = logging.getLogger(__name__)


class ToolExecutor:
    """
    Manages tool registration and execution for Gemini function calling.

    Provides a registry-based approach to register Python functions as tools,
    execute them when called by Gemini, and generate appropriate responses.
    """

    def __init__(self, verbose: bool = True):
        """
        Initialize the tool executor.

        Args:
            verbose: If True, print execution logs to console
        """
        self._tools: dict[str, Callable] = {}
        self.declarations: dict[str, FunctionDeclaration] = {}
        self.verbose = verbose

    @property
    def tools(self) -> list[FunctionDeclaration]:
        """List all registered tool declarations for Gemini API."""
        return list(self.declarations.values())

    def register_tool(self, name: str, func: Callable, declaration: FunctionDeclaration):
        """
        Register a tool with its function and declaration.

        Args:
            name (str): The unique name of the tool (must match function name)
            func (Callable): The async function to execute when tool is called
            declaration (FunctionDeclaration): FunctionDeclaration object for Gemini API

        Raises:
            ValueError: If tool name is already registered
        """
        if self.has_tool(name):
            raise ValueError(f"Tool '{name}' is already registered")

        if not asyncio.iscoroutinefunction(func):
            raise ValueError(f"Tool '{name}' must be an async function")

        self._tools[name] = func
        self.declarations[name] = declaration

        if self.verbose:
            logger.info(f"Registered tool: {name}")

    def has_tool(self, name: str) -> bool:
        """
        Check if a tool is registered.

        Args:
            name (str): Tool name to check

        Returns:
            bool: True if tool is registered, False otherwise
        """
        return name in self._tools

    async def execute_tool(
        self,
        func_name: str,
        func_id: str,
        args: dict[str, Any] | None = None,
    ) -> FunctionResponse:
        """
        Execute a registered tool and return a `FunctionResponse`.

        Args:
            func_name (str): Name of the tool to execute
            func_id (str): Unique ID for this function call (from Gemini)
            args (dict[str, Any] | None): Optional dict of function arguments

        Returns:
            FunctionResponse: `FunctionResponse` object to send back to Gemini
        """
        args = args or {}

        if not self.has_tool(func_name):
            error_msg = (
                f"Unknown tool function requested: '{func_name}' is not registered."
            )

            if self.verbose:
                logger.error(error_msg)

            return FunctionResponse(
                id=func_id,
                name=func_name,
                response={"status": "error", "error": error_msg, "data": None},
            )

        try:
            if self.verbose:
                logger.info(f"Executing tool function: '{func_name}(args={args})'")

            # Call the function with unpacked args
            result = await self._tools[func_name](**args)

            if self.verbose:
                logger.info(f"Tool function '{func_name}' completed successfully")

            return FunctionResponse(
                id=func_id,
                name=func_name,
                response={"status": "success", "data": result, "error": None},
            )
        except Exception as e:
            error_msg = f"Error executing tool function '{func_name}': {e}"
            task_err = ToolExecutorError(error_msg, e)

            if self.verbose:
                logger.error(error_msg, exc_info=True)

            return FunctionResponse(
                id=func_id,
                name=func_name,
                response={"status": "error", "error": str(task_err), "data": None},
            )
