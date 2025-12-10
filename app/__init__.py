"""
Workflow Engine Package

A simple but powerful agent workflow engine for executing multi-step processes.
"""

__version__ = "1.0.0"
__author__ = "AI Engineering Assignment"

from .core.engine import WorkflowEngine
from .core.models import WorkflowState, GraphDefinition, NodeDefinition
from .tools.registry import ToolRegistry

__all__ = [
    "WorkflowEngine",
    "WorkflowState", 
    "GraphDefinition",
    "NodeDefinition",
    "ToolRegistry"
]