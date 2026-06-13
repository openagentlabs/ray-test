"""
GraphRAG Microservice - Runs on Python 3.12
FastAPI server that handles GraphRAG queries independently
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import json
import subprocess
import sys
from pathlib import Path
import os
from datetime import datetime

app = FastAPI(title="GraphRAG Service", version="1.0.0")

class QueryRequest(BaseModel):
    query: str
    query_type: str = "local"
    max_tokens: int = 3500
    agent_name: str = "Unknown"

class QueryResponse(BaseModel):
    success: bool
    context: str
    error: Optional[str] = None
    execution_time: Optional[float] = None

class GraphRAGQueryHandler:
    def __init__(self):
        # Get paths relative to this service
        self.service_root = Path(__file__).parent.parent
        self.graphrag_root = self.service_root / "knowledge_repo_kg"
        self.query_script = self.service_root / "graphrag_query_runner.py"
        
        # Verify GraphRAG is available
        if not self._verify_setup():
            raise RuntimeError("GraphRAG setup verification failed")
    
    def _verify_setup(self) -> bool:
        """Verify GraphRAG environment is properly configured"""
        return (
            self.graphrag_root.exists() and
            (self.graphrag_root / "output").exists() and
            self.query_script.exists() and
            os.getenv("LLM_GATEWAY_VIRTUAL_KEY") is not None
        )
    
    def execute_query(self, request: QueryRequest) -> QueryResponse:
        """Execute GraphRAG query"""
        import time
        start_time = time.time()
        
        try:
            # Use current Python (3.12) to run query
            cmd = [
                sys.executable,  # This will be Python 3.12
                str(self.query_script),
                "--root", str(self.graphrag_root),
                "--query", request.query,
                "--method", request.query_type,
                "--max-tokens", str(request.max_tokens)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=1200,
                cwd=str(self.graphrag_root),
                env=os.environ.copy()
            )
            
            execution_time = time.time() - start_time
            
            if result.returncode != 0:
                error_msg = result.stderr[:500] if result.stderr else f"Process exited with code {result.returncode}"
                return QueryResponse(
                    success=False,
                    context="",
                    error=error_msg,
                    execution_time=execution_time
                )
            
            # Parse JSON response
            try:
                response_data = json.loads(result.stdout)
                context = response_data.get("context", "")
                
                return QueryResponse(
                    success=True,
                    context=context,
                    error=None,
                    execution_time=execution_time
                )
            except json.JSONDecodeError as e:
                return QueryResponse(
                    success=False,
                    context="",
                    error=f"Invalid JSON response: {str(e)}",
                    execution_time=execution_time
                )
                
        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            return QueryResponse(
                success=False,
                context="",
                error="Query timeout after 1200 seconds",
                execution_time=execution_time
            )
        except Exception as e:
            execution_time = time.time() - start_time
            return QueryResponse(
                success=False,
                context="",
                error=str(e),
                execution_time=execution_time
            )

# Initialize handler
handler = GraphRAGQueryHandler()

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "python_version": sys.version,
        "graphrag_available": handler._verify_setup()
    }

@app.post("/query", response_model=QueryResponse)
async def query_knowledge_graph(request: QueryRequest):
    """Execute GraphRAG query"""
    return handler.execute_query(request)

@app.get("/status")
async def get_status():
    """Get service status"""
    return {
        "service": "graphrag",
        "version": "1.0.0",
        "python_version": sys.version,
        "graphrag_root": str(handler.graphrag_root),
        "available": handler._verify_setup()
    }

if __name__ == "__main__":
    import uvicorn
    # Run on port 8001 (configurable)
    port = int(os.getenv("GRAPHRAG_SERVICE_PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port)