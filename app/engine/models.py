from typing import Dict, Any, List, Optional, Callable
from pydantic import BaseModel
from enum import Enum
import uuid
from datetime import datetime


class NodeStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkflowState(BaseModel):
    """Shared state that flows between nodes"""
    data: Dict[str, Any] = {}
    metadata: Dict[str, Any] = {}
    
    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
    
    def update(self, updates: Dict[str, Any]) -> None:
        self.data.update(updates)


class NodeDefinition(BaseModel):
    """Definition of a workflow node"""
    name: str
    function_name: str
    parameters: Dict[str, Any] = {}


class GraphDefinition(BaseModel):
    """Complete workflow graph definition"""
    name: str
    nodes: List[NodeDefinition]
    edges: Dict[str, str]  # Simple mapping like {"extract": "analyze"}
    conditional_edges: Dict[str, Dict[str, str]] = {}  # {"node": {"condition": "next_node"}}
    start_node: str


class ExecutionLog(BaseModel):
    """Log entry for workflow execution"""
    timestamp: datetime
    node_name: str
    status: NodeStatus
    message: str
    state_snapshot: Optional[Dict[str, Any]] = None


class WorkflowRun(BaseModel):
    """Runtime information for a workflow execution"""
    run_id: str
    graph_id: str
    status: NodeStatus
    current_node: Optional[str] = None
    state: WorkflowState
    logs: List[ExecutionLog] = []
    created_at: datetime
    completed_at: Optional[datetime] = None
    
    @classmethod
    def create(cls, graph_id: str, initial_state: Dict[str, Any]) -> "WorkflowRun":
        return cls(
            run_id=str(uuid.uuid4()),
            graph_id=graph_id,
            status=NodeStatus.PENDING,
            state=WorkflowState(data=initial_state),
            created_at=datetime.now()
        )