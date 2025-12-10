from typing import Dict, Any, Callable, Optional, List
import asyncio
from datetime import datetime
import logging

from .models import (
    GraphDefinition, WorkflowRun, NodeStatus, ExecutionLog,
    WorkflowState, NodeDefinition
)

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """Core workflow execution engine"""
    
    def __init__(self):
        """Initialize the workflow engine with empty storage containers."""
        self.graphs: Dict[str, GraphDefinition] = {}  
        self.runs: Dict[str, WorkflowRun] = {} 
        self.node_functions: Dict[str, Callable] = {} 
        
    def register_function(self, name: str, func: Callable) -> None:
        """Register a function that can be used in workflow nodes."""
        self.node_functions[name] = func
        
    def create_graph(self, graph_def: GraphDefinition) -> str:
        """Create and store a workflow graph definition."""
        graph_id = f"graph_{len(self.graphs) + 1}"  # Generate unique ID
        self.graphs[graph_id] = graph_def on
        return graph_id
    
    def get_graph(self, graph_id: str) -> Optional[GraphDefinition]:
        """Retrieve a workflow graph definition by its ID."""
        return self.graphs.get(graph_id)
    
    async def run_workflow(self, graph_id: str, initial_state: Dict[str, Any]) -> WorkflowRun:
        """Execute a complete workflow from start to finish."""
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
        """Core workflow execution logic - implements state machine with transitions and loops."""
        current_node = graph.start_node
        visited_nodes = set()  # Track visited nodes for loop detection
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
                await self._execute_node(run, node_def)  
                self._add_log(run, current_node, NodeStatus.COMPLETED, f"Node {current_node} completed")
            except Exception as e:
                self._add_log(run, current_node, NodeStatus.FAILED, f"Node {current_node} failed: {str(e)}")
                raise  
            
            # Determine next node based on edges and conditions
            next_node = self._get_next_node(run, graph, current_node)
            
            # Handle looping - allow revisiting nodes if conditions permit
            if next_node in visited_nodes:
                loop_condition = self._check_loop_condition(run, graph, current_node)
                if not loop_condition:
                    break  
            
            visited_nodes.add(current_node)
            current_node = next_node
        
        # Safety check to prevent runaway workflows
        if iteration_count >= max_iterations:
            raise RuntimeError("Maximum iterations reached - possible infinite loop")
    
    async def _execute_node(self, run: WorkflowRun, node_def: NodeDefinition) -> None:
        """Execute a single workflow node by calling its associated function."""
        # Look up the function to execute for this node
        func = self.node_functions.get(node_def.function_name)
        if not func:
            raise ValueError(f"Function {node_def.function_name} not registered")
        
        # Prepare function parameters - merge node params with current state
        params = {**node_def.parameters}  
        params['state'] = run.state  
        
        # Execute function - handle both synchronous and asynchronous functions
        if asyncio.iscoroutinefunction(func):
            result = await func(**params)  
        else:
            result = func(**params)  # Call sync functions directly
        
        if result and isinstance(result, dict):
            run.state.update(result)  
    
    def _get_next_node(self, run: WorkflowRun, graph: GraphDefinition, current_node: str) -> Optional[str]:
        """Determine the next node to execute based on edges and conditional logic."""
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
        """Safely evaluate a condition string against the current workflow state."""
        try:
            # Prepare evaluation context with current state data
            context = {**state.data, **state.metadata}  # Merge state and metadata
            
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
            return False  # Default to False for invalid conditions
    
    def _check_loop_condition(self, run: WorkflowRun, graph: GraphDefinition, current_node: str) -> bool:
        """Check if a loop should continue based on conditional edges."""
        # Check if current node has conditional edges that might create loops
        if current_node in graph.conditional_edges:
            conditions = graph.conditional_edges[current_node]
            for condition, next_node in conditions.items():
                # If condition is true, the loop should continue
                if self._evaluate_condition(run.state, condition):
                    return True  # Continue looping
        
        return False  # No valid loop conditions, exit loop
    
    def _add_log(self, run: WorkflowRun, node_name: str, status: NodeStatus, message: str) -> None:
        """Add a log entry to workflow run for tracking execution."""
        # Create detailed log entry with current state snapshot
        log_entry = ExecutionLog(
            timestamp=datetime.now(),
            node_name=node_name,
            status=status,
            message=message,
            state_snapshot=run.state.data.copy()  # Capture state at this moment
        )
        
        # Store log entry in workflow run for later retrieval
        run.logs.append(log_entry)
        logger.info(f"[{run.run_id}] {node_name}: {message}")
    
    def get_run(self, run_id: str) -> Optional[WorkflowRun]:
        """Retrieve a workflow run instance by its unique ID."""
        return self.runs.get(run_id)
    
    def get_run_state(self, run_id: str) -> Optional[WorkflowState]:
        """Get the current state of a specific workflow run."""
        run = self.get_run(run_id)
        return run.state if run else None
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Calculate and return current memory usage statistics for monitoring."""
        # Calculate total log entries across all workflow runs
        total_logs = sum(len(run.logs) for run in self.runs.values())
        
        return {
            "graphs": len(self.graphs),  
            "runs": len(self.runs),  
            "functions": len(self.node_functions),  
            "total_logs": total_logs,  
        }