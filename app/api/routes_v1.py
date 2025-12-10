from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from pydantic import BaseModel

from app.engine.engine import WorkflowEngine
from app.engine.models import GraphDefinition, WorkflowState
from app.tools.registry import ToolRegistry
from app.agent_workflow.code_review import create_code_review_workflow, SAMPLE_CODE

router = APIRouter()

# Global instances
engine = WorkflowEngine()
tool_registry = ToolRegistry()

# Register tools with engine
for tool_name in tool_registry.list_tools():
    engine.register_function(tool_name, tool_registry.get(tool_name))

# Pre-create the code review workflow
code_review_graph = create_code_review_workflow()
CODE_REVIEW_GRAPH_ID = engine.create_graph(code_review_graph)


# Request/Response models
class CreateGraphRequest(BaseModel):
    name: str
    nodes: list
    edges: dict  # Simple mapping like {"extract": "analyze"}
    conditional_edges: dict = {}  # Optional conditional routing
    start_node: str


class CreateGraphResponse(BaseModel):
    graph_id: str
    message: str


class RunWorkflowRequest(BaseModel):
    graph_id: str
    initial_state: Dict[str, Any]


class RunWorkflowResponse(BaseModel):
    run_id: str
    status: str
    final_state: Dict[str, Any]
    logs: list


class StateResponse(BaseModel):
    run_id: str
    status: str
    current_node: str = None
    state: Dict[str, Any]


@router.post("/graph/create", response_model=CreateGraphResponse)
async def create_graph(request: CreateGraphRequest):
    """Create a new workflow graph"""
    try:
        # Convert request to GraphDefinition
        graph_def = GraphDefinition(
            name=request.name,
            nodes=request.nodes,
            edges=request.edges,
            conditional_edges=request.conditional_edges,
            start_node=request.start_node
        )
        
        graph_id = engine.create_graph(graph_def)
        
        return CreateGraphResponse(
            graph_id=graph_id,
            message=f"Graph '{request.name}' created successfully"
        )
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/graph/run", response_model=RunWorkflowResponse)
async def run_workflow(request: RunWorkflowRequest):
    """Run a workflow with initial state"""
    try:
        run = await engine.run_workflow(request.graph_id, request.initial_state)
        
        return RunWorkflowResponse(
            run_id=run.run_id,
            status=run.status.value,
            final_state=run.state.data,
            logs=[{
                "timestamp": log.timestamp.isoformat(),
                "node_name": log.node_name,
                "status": log.status.value,
                "message": log.message
            } for log in run.logs]
        )
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/graph/state/{run_id}", response_model=StateResponse)
async def get_workflow_state(run_id: str):
    """Get current state of a workflow run"""
    run = engine.get_run(run_id)
    
    if not run:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    
    return StateResponse(
        run_id=run.run_id,
        status=run.status.value,
        current_node=run.current_node,
        state=run.state.data
    )


@router.get("/graphs")
async def list_graphs():
    """List all available graphs"""
    return {
        "graphs": [
            {
                "graph_id": graph_id,
                "name": graph.name,
                "node_count": len(graph.nodes),
                "edge_count": len(graph.edges)
            }
            for graph_id, graph in engine.graphs.items()
        ]
    }


@router.get("/tools")
async def list_tools():
    """List all available tools"""
    return {
        "tools": tool_registry.list_tools()
    }


@router.get("/memory/stats")
async def get_memory_stats():
    """Get current memory usage statistics"""
    return engine.get_memory_stats()