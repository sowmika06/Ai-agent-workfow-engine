from typing import Dict, Any, Callable, Optional, List
import asyncio
from datetime import datetime, timedelta
import logging
import json

from .models import (
    GraphDefinition, WorkflowRun, NodeStatus, ExecutionLog,
    WorkflowState, NodeDefinition
)

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """Core workflow execution engine"""
    
    def __init__(self):
        """
        Initialize the workflow engine with empty storage containers.
        
        """
        self.graphs: Dict[str, GraphDefinition] = {}  # Store workflow definitions by ID
        self.runs: Dict[str, WorkflowRun] = {}  # Store active/completed workflow executions
        self.node_functions: Dict[str, Callable] = {}  # Registry of available node functions
        self.websocket_connections: Dict[str, List] = {}  # Track WebSocket connections per run
        
    def register_function(self, name: str, func: Callable) -> None:
        """
        Register a function that can be used in workflow nodes.
        Simple dictionary mapping - nodes reference functions by name, engine looks up actual function.

        """
        self.node_functions[name] = func
        
    def create_graph(self, graph_def: GraphDefinition) -> str:
        """
        Create and store a workflow graph definition.
        Simple incremental ID generation, stores in memory dictionary for fast lookup.

        """
        graph_id = f"graph_{len(self.graphs) + 1}"  # Generate unique ID
        self.graphs[graph_id] = graph_def  # Store graph definition
        return graph_id
    
    def get_graph(self, graph_id: str) -> Optional[GraphDefinition]:
        """
        Retrieve a workflow graph definition by its ID.
        Uses dict.get() to avoid KeyError exceptions - returns None if not found.

        """
        return self.graphs.get(graph_id)
    
    async def run_workflow(self, graph_id: str, initial_state: Dict[str, Any]) -> WorkflowRun:
        """
        Execute a complete workflow from start to finish.
        Try/catch pattern ensures proper status setting even on failures, async for long-running workflows.

        """
        graph = self.get_graph(graph_id)
        if not graph:
            raise ValueError(f"Graph {graph_id} not found")
        
        # Create workflow run instance with unique ID and initial state
        run = WorkflowRun.create(graph_id, initial_state)
        self.runs[run.run_id] = run  
        
        try:
            # Execute the actual workflow logic
            await self._execute_workflow(run, graph)
            run.status = NodeStatus.COMPLETED
            run.completed_at = datetime.now()
        except Exception as e:
            # Ensure failed workflows are properly marked and logged
            run.status = NodeStatus.FAILED
            self._add_log(run, "ERROR", NodeStatus.FAILED, f"Workflow failed: {str(e)}")
            logger.error(f"Workflow {run.run_id} failed: {e}")
            
        return run
    
    async def _execute_workflow(self, run: WorkflowRun, graph: GraphDefinition) -> None:
        """
        Core workflow execution logic - implements state machine with transitions and loops.
        State machine pattern - current node → execute → determine next → repeat until done.
        """
        current_node = graph.start_node
        visited_nodes = set() 
        max_iterations = 100 
        iteration_count = 0
        
        # Continue until no more nodes or hit iteration limit
        while current_node and iteration_count < max_iterations:
            iteration_count += 1
            
            # Find the node definition for current node name
            node_def = next((n for n in graph.nodes if n.name == current_node), None)
            if not node_def:
                raise ValueError(f"Node {current_node} not found in graph")
            
            # Execute the current node
            run.current_node = current_node
            self._add_log(run, current_node, NodeStatus.RUNNING, f"Executing node {current_node}")
            
            try:
                await self._execute_node(run, node_def)  # Execute node function
                self._add_log(run, current_node, NodeStatus.COMPLETED, f"Node {current_node} completed")
            except Exception as e:
                self._add_log(run, current_node, NodeStatus.FAILED, f"Node {current_node} failed: {str(e)}")
                raise  # Re-raise to fail the entire workflow
            
            # Determine next node based on edges and conditions
            next_node = self._get_next_node(run, graph, current_node)
            
            # Handle looping - allow revisiting nodes if conditions permit
            if next_node in visited_nodes:
                loop_condition = self._check_loop_condition(run, graph, current_node)
                if not loop_condition:
                    break  # Exit loop if condition not met
            
            visited_nodes.add(current_node)
            current_node = next_node
        
        # Safety check to prevent runaway workflows
        if iteration_count >= max_iterations:
            raise RuntimeError("Maximum iterations reached - possible infinite loop")
    
    async def _execute_node(self, run: WorkflowRun, node_def: NodeDefinition) -> None:
        """
        Execute a single workflow node by calling its associated function.
        Supports both sync/async functions, passes current state, merges results back into state.

        """
        # Look up the function to execute for this node
        func = self.node_functions.get(node_def.function_name)
        if not func:
            raise ValueError(f"Function {node_def.function_name} not registered")
        
        # Prepare function parameters - merge node params with current state
        params = {**node_def.parameters}  
        params['state'] = run.state  
        
        # Execute function - handle both synchronous and asynchronous functions
        if asyncio.iscoroutinefunction(func):
            result = await func(**params)  # Await async functions
        else:
            result = func(**params) 
        
        # Update workflow state with function results (if any)
        if result and isinstance(result, dict):
            run.state.update(result)  
    
    def _get_next_node(self, run: WorkflowRun, graph: GraphDefinition, current_node: str) -> Optional[str]:
        """
        Determine the next node to execute based on edges and conditional logic.
        Priority system - conditions override simple edges, first matching condition wins.

        """
        # Check conditional edges first (for branching/looping logic)
        if current_node in graph.conditional_edges:
            conditions = graph.conditional_edges[current_node]
            for condition, next_node in conditions.items():
                # Evaluate condition against current state
                if self._evaluate_condition(run.state, condition):
                    return next_node 
        
        # Fall back to simple edge mapping: {"extract": "analyze"}
        return graph.edges.get(current_node)
    
    def _evaluate_condition(self, state: WorkflowState, condition: str) -> bool:
        """
        Safely evaluate a condition string against the current workflow state.
        
        Parses condition strings like "quality_score >= 7" and evaluates them against state.
        Uses restricted eval() 
        """
        try:
            # Prepare evaluation context with current state data
            context = {**state.data, **state.metadata}  # Merge state and metadata
            
            # Create safe evaluation environment - restrict available functions/operations
            safe_builtins = {
                '__builtins__': {}, 
                'True': True, 'False': False, 'None': None,  
                'int': int, 'float': float, 'str': str, 'len': len 
            }
            
            # Evaluate condition string safely (e.g., "quality_score >= 7")
            return eval(condition, safe_builtins, context)
        except Exception as e:
            # Log evaluation failures but don't crash workflow
            logger.warning(f"Failed to evaluate condition '{condition}': {e}")
            return False  
    
    def _check_loop_condition(self, run: WorkflowRun, graph: GraphDefinition, current_node: str) -> bool:
        """
        Check if a loop should continue based on conditional edges.
        
        loop control logic - determines when to continue or exit loops.
        If any condition evaluates to True, allow the loop to continue.
        """
        # Check if current node has conditional edges that might create loops
        if current_node in graph.conditional_edges:
            conditions = graph.conditional_edges[current_node]
            for condition, next_node in conditions.items():
                if self._evaluate_condition(run.state, condition):
                    return True  
        
        return False  
    
    def _add_log(self, run: WorkflowRun, node_name: str, status: NodeStatus, message: str) -> None:
        """
        Add a log entry to workflow run and broadcast to connected WebSocket clients.
        
        Creates log entry with timestamp/status, stores in run, broadcasts to WebSockets.
        Synchronous logging + asynchronous broadcasting for performance.
        """
        # Create detailed log entry with current state snapshot
        log_entry = ExecutionLog(
            timestamp=datetime.now(),
            node_name=node_name,
            status=status,
            message=message,
            state_snapshot=run.state.data.copy()  # Capture state at this moment
        )
        
        run.logs.append(log_entry)
        logger.info(f"[{run.run_id}] {node_name}: {message}")
        
        # Broadcast to WebSocket connections asynchronously (non-blocking)
        asyncio.create_task(self._broadcast_log(run.run_id, log_entry))
    
    async def _broadcast_log(self, run_id: str, log_entry: ExecutionLog) -> None:
        """
        Broadcast log entry to all WebSocket connections monitoring this workflow run.
        
        Converts log entry to JSON and sends to all WebSocket connections for this run.
        Async broadcasting with error handling - removes disconnected clients automatically.
        """
        if run_id not in self.websocket_connections:
            return
        
        # Prepare log data for JSON serialization
        log_data = {
            "type": "log",
            "timestamp": log_entry.timestamp.isoformat(),
            "node_name": log_entry.node_name,
            "status": log_entry.status.value,
            "message": log_entry.message,
            "state_snapshot": log_entry.state_snapshot
        }
        
        # Send to all connected WebSockets for this run (copy list to avoid modification during iteration)
        connections = self.websocket_connections[run_id].copy()
        for websocket in connections:
            try:
                await websocket.send_text(json.dumps(log_data))
            except Exception as e:
                # Clean up disconnected WebSocket connections
                logger.warning(f"WebSocket disconnected for run {run_id}: {e}")
                if websocket in self.websocket_connections[run_id]:
                    self.websocket_connections[run_id].remove(websocket)
    
    def add_websocket_connection(self, run_id: str, websocket) -> None:
        """
        Register a WebSocket connection to receive real-time updates for a workflow run.
        
        Adds WebSocket to the list of connections for a specific workflow run.
        Creates list if first connection, appends to existing list otherwise.
        """
        # Initialize connection list for this run if it doesn't exist
        if run_id not in self.websocket_connections:
            self.websocket_connections[run_id] = []
        
        # Add WebSocket to the list for this run
        self.websocket_connections[run_id].append(websocket)
        logger.info(f"WebSocket connected for run {run_id}")
    
    def remove_websocket_connection(self, run_id: str, websocket) -> None:
        """
        Unregister a WebSocket connection when client disconnects.
        
        """
        if run_id in self.websocket_connections and websocket in self.websocket_connections[run_id]:
            self.websocket_connections[run_id].remove(websocket)
            logger.info(f"WebSocket disconnected for run {run_id}")
            
            # Clean up empty connection lists to prevent memory leaks
            if not self.websocket_connections[run_id]:
                del self.websocket_connections[run_id]
    
    def get_run(self, run_id: str) -> Optional[WorkflowRun]:
        """
        Retrieve a workflow run instance by its unique ID.
        
        """
        return self.runs.get(run_id)
    
    def get_run_state(self, run_id: str) -> Optional[WorkflowState]:
        """
        Get the current state of a specific workflow run.
        
        """
        run = self.get_run(run_id)
        return run.state if run else None
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """
        Calculate and return current memory usage statistics for monitoring.
        
        """
        total_logs = sum(len(run.logs) for run in self.runs.values())
        
        active_websockets = sum(len(conns) for conns in self.websocket_connections.values())
        
        return {
            "graphs": len(self.graphs),  # Number of stored workflow definitions
            "runs": len(self.runs),  # Number of workflow executions
            "functions": len(self.node_functions),  # Number of registered functions
            "total_logs": total_logs,  # Total log entries across all runs
            "active_websockets": active_websockets  # Total active WebSocket connections
        }