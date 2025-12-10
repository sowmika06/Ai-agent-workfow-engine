# Agent Workflow Engine

A flexible workflow execution engine built with FastAPI that supports state-driven node execution, conditional branching, and looping.

##  How to Run

```bash
# Setup
python -m venv venv
source venv/bin/activate 
# On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Start server
python -m app.main
```

Server runs at `http://localhost:8000` 

## What Agent Workflow Engine Supports

### Core Features
- **Simple Edge Mapping**: `{"extract": "analyze", "analyze": "quality"}`
- **Conditional Branching**: Route to different nodes based on state values (`quality_score >= 7`)
- **Looping**: Repeat nodes until conditions are met (`quality_score < 8`)
- **State Management**: Dictionary-based state flows between nodes
- **WebSocket Streaming**: Real-time execution log streaming
- **Tool Registry**: Both pre-registered and API-based tool registration

### API Endpoints
```
POST /api/v1/graph/create     # Create workflow graph
POST /api/v1/graph/run        # Execute workflow
GET  /api/v1/graph/state/{id} # Get current state
WS   /api/v1/ws/workflow/{id} # Real-time log streaming
```

### Sample Workflow: Code Review Mini-Agent
Complete 5-step workflow with looping:
1. **Extract functions** from code
2. **Check complexity** using cyclomatic complexity
3. **Detect issues** (style, documentation, maintenance)
4. **Suggest improvements** based on analysis
5. **Loop until quality_score >= threshold**

## What You Would Improve With More Time

### Performance & Scalability
- **Parallel Node Execution**: Execute independent nodes concurrently
- **Database Integration**: Persistent storage for graphs and runs (PostgreSQL/MongoDB)
- **Caching Layer**: Redis for function results and state snapshots
- **Distributed Execution**: Multi-worker support with message queues

### Advanced Features
- **Visual Workflow Builder**: Web UI for drag-and-drop workflow creation
- **Workflow Templates**: Pre-built patterns for common use cases
- **Advanced Scheduling**: Cron-based and event-triggered execution
- **Monitoring Dashboard**: Real-time metrics, execution history, performance analytics

### Enterprise Features
- **Authentication & Authorization**: JWT-based user management and RBAC
- **Multi-tenancy**: Isolated workspaces for different teams/projects
- **Audit Logging**: Complete execution history for compliance
- **High Availability**: Load balancing, failover, and auto-scaling

### Developer Experience
- **Workflow Debugging**: Step-through debugging with breakpoints
- **Better Error Handling**: Detailed error context and recovery suggestions
- **SDK/Client Libraries**: Python, JavaScript, and Go client libraries
- **Integration Ecosystem**: Plugins for GitHub, Slack, Jenkins, Docker

