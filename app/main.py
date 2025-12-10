from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.api.routes import router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Workflow Engine API",
    description="A simple agent workflow engine for executing multi-step processes",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api/v1")


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Workflow Engine API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "create_graph": "POST /api/v1/graph/create",
            "run_workflow": "POST /api/v1/graph/run", 
            "get_state": "GET /api/v1/graph/state/{run_id}",
            "websocket_logs": "WS /api/v1/ws/workflow/{run_id}",
            "list_graphs": "GET /api/v1/graphs",
            "list_tools": "GET /api/v1/tools",
            "memory_stats": "GET /api/v1/memory/stats",
            "memory_cleanup": "POST /api/v1/memory/cleanup",
            "demo_code_review": "POST /api/v1/demo/code-review"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)