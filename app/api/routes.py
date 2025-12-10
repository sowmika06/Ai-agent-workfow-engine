from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from typing import Dict, Any
from pydantic import BaseModel
import json
import asyncio

from app.core.engine import WorkflowEngine
from app.core.models import GraphDefinition, WorkflowState
from app.tools.registry import ToolRegistry
from app.workflows.code_review import create_code_review_workflow, SAMPLE_CODE

router = APIRouter()

# Global instances - initialized once when module loads
engine = WorkflowEngine()  # Core workflow execution engine
tool_registry = ToolRegistry()  # Registry of available workflow functions

# Register all tools with the engine for workflow execution
# Makes all registered tools available for use in workflow nodes
# Iterates through registry and registers each tool with the engine

for tool_name in tool_registry.list_tools():
    engine.register_function(tool_name, tool_registry.get(tool_name))

# Creates workflow definition and stores it for immediate use
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
    """
    Create a new workflow graph definition.
    
    allows dynamic creation of workflow graphs via API.
    Accepts graph definition JSON and creates reusable workflow template.
    Validates input, converts to internal model, stores in engine, returns ID.
    """
    try:
        # Convert API request to internal GraphDefinition model
        # Pydantic handles validation of required fields and types
        graph_def = GraphDefinition(
            name=request.name,
            nodes=request.nodes,  
            edges=request.edges,  
            conditional_edges=request.conditional_edges,  # Branching/looping logic
            start_node=request.start_node
        )
        
        # Store graph in engine and get unique ID
        graph_id = engine.create_graph(graph_def)
        
        return CreateGraphResponse(
            graph_id=graph_id,
            message=f"Graph '{request.name}' created successfully"
        )
    
    except Exception as e:
        # Convert any errors to HTTP 400 Bad Request
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/graph/run", response_model=RunWorkflowResponse)
async def run_workflow(request: RunWorkflowRequest):
    """
    Execute a workflow with provided initial state.
    
    main execution endpoint for running workflows.
    Takes graph ID and initial state, executes workflow, returns results and logs.
    Async execution with full error handling and detailed response formatting.
    """
    try:
        # Execute the workflow asynchronously
        run = await engine.run_workflow(request.graph_id, request.initial_state)
        
        # Format response with execution details
        return RunWorkflowResponse(
            run_id=run.run_id,
            status=run.status.value,  # Convert enum to string
            final_state=run.state.data,  
            logs=[{  # Convert log objects to JSON-serializable format
                "timestamp": log.timestamp.isoformat(),
                "node_name": log.node_name,
                "status": log.status.value,
                "message": log.message
            } for log in run.logs]
        )
    
    except Exception as e:
        # Handle workflow execution errors
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/graph/state/{run_id}", response_model=StateResponse)
async def get_workflow_state(run_id: str):
    """
    Get the current state of an ongoing or completed workflow run.
    
    allows monitoring workflow progress and accessing results.
    Returns current execution status, active node, and state data for a workflow run.
    Simple lookup with 404 error for missing runs, safe state extraction.
    """
    # Look up the workflow run by ID
    run = engine.get_run(run_id)
    
    # Return 404 if run doesn't exist
    if not run:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    
    # Return current state information
    return StateResponse(
        run_id=run.run_id,
        status=run.status.value,  
        current_node=run.current_node,  
        state=run.state.data 
    )


@router.get("/graphs")
async def list_graphs():
    """
    List all available workflow graphs with summary information.
    
    Returns list of all stored graphs with basic metadata.
    Iterates through stored graphs and extracts summary information.
    """
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
    """
    List all available workflow tools/functions.
    
    Returns list of all registered tool names.
    Simple delegation to tool registry for current tool list.
    """
    return {
        "tools": tool_registry.list_tools()
    }


@router.get("/memory/stats")
async def get_memory_stats():
    """
    Get current memory usage statistics for monitoring.
    
    Provides visibility into engine resource usage for debugging and monitoring.
    Returns counts of stored objects and memory usage metrics.
    Delegates to engine's memory statistics calculation.
    """
    return engine.get_memory_stats()



class RegisterToolRequest(BaseModel):
    name: str
    code: str  


@router.post("/tools/register")
async def register_tool(request: RegisterToolRequest):
    """Register a new tool function via API"""
    try:
        # Create a safe namespace for the function
        namespace = {}
        
        
        exec(request.code, namespace)
        
        # Find the function in the namespace (assume it's the only function defined)
        func = None
        for name, obj in namespace.items():
            if callable(obj) and not name.startswith('__'):
                func = obj
                break
        
        if not func:
            raise ValueError("No function found in provided code")
        
        # Register the tool
        tool_registry.register(request.name, func)
        engine.register_function(request.name, func)
        
        return {
            "message": f"Tool '{request.name}' registered successfully",
            "tool_name": request.name,
            "total_tools": len(tool_registry.list_tools())
        }
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to register tool: {str(e)}")


@router.post("/demo/code-review")
async def demo_code_review(code: str = None):
    """Demo endpoint to run code review on sample or provided code"""
    if code is None:
        code = SAMPLE_CODE
    
    initial_state = {"code": code}
    
    try:
        run = await engine.run_workflow(CODE_REVIEW_GRAPH_ID, initial_state)
        
        return {
            "run_id": run.run_id,
            "status": run.status.value,
            "results": {
                "quality_score": run.state.get("quality_score"),
                "quality_level": run.state.get("quality_level"),
                "function_count": run.state.get("function_count"),
                "issue_count": run.state.get("issue_count"),
                "suggestions": run.state.get("suggestions", []),
                "complexity_scores": run.state.get("complexity_scores", [])
            },
            "execution_log": [
                {
                    "timestamp": log.timestamp.isoformat(),
                    "node": log.node_name,
                    "status": log.status.value,
                    "message": log.message
                }
                for log in run.logs
            ]
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/ws/workflow/{run_id}")
async def websocket_workflow_logs(websocket: WebSocket, run_id: str):
    """WebSocket endpoint to stream workflow logs in real-time"""
    await websocket.accept()
    
    try:
        # Add WebSocket connection to engine
        engine.add_websocket_connection(run_id, websocket)
        
        # Send initial connection message
        await websocket.send_text(json.dumps({
            "type": "connected",
            "message": f"Connected to workflow {run_id}",
            "run_id": run_id
        }))
        
        # Check if run exists and send existing logs
        run = engine.get_run(run_id)
        if run:
            # Send existing logs
            for log in run.logs:
                log_data = {
                    "type": "log",
                    "timestamp": log.timestamp.isoformat(),
                    "node_name": log.node_name,
                    "status": log.status.value,
                    "message": log.message,
                    "state_snapshot": log.state_snapshot
                }
                await websocket.send_text(json.dumps(log_data))
            
            # Send current status
            await websocket.send_text(json.dumps({
                "type": "status",
                "run_id": run_id,
                "status": run.status.value,
                "current_node": run.current_node
            }))
        else:
            # Run doesn't exist yet, wait for it to be created
            await websocket.send_text(json.dumps({
                "type": "waiting",
                "message": f"Waiting for workflow {run_id} to start..."
            }))
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for messages from client (ping/pong, etc.)
                data = await websocket.receive_text()
                message = json.loads(data)
                
                if message.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                
            except WebSocketDisconnect:
                break
            except Exception as e:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"Error: {str(e)}"
                }))
                break
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_text(json.dumps({
                "type": "error", 
                "message": f"WebSocket error: {str(e)}"
            }))
        except:
            pass
    finally:
        # Remove WebSocket connection from engine
        engine.remove_websocket_connection(run_id, websocket)