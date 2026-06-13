import subprocess
import json
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
from app.core.logging_config import get_logger
import threading
from typing import Optional

class GraphRAGService:
    def __init__(self):
        self.logger = get_logger(__name__)
        self.graphrag_root = Path(__file__).parent.parent.parent / "knowledge_repo_kg"
        self.python_312_path = self._find_python_312()
        self.query_script_path = Path(__file__).parent.parent.parent / "graphrag_query_runner.py"
        self._cache = {}  # ✅ Add simple cache
        self._cache_ttl = 300  # 5 minutes
        # Persistent cache directory
        self._persistent_cache_dir = Path(__file__).parent.parent.parent / "kg_cache"
        self._persistent_cache_dir.mkdir(exist_ok=True)
        self._persistent_cache_ttl = 864000  # 24 hours
        self._prefetch_cache = {}  # Stores prefetch results
        self._prefetch_threads = {}

    def start_prefetch_query(
        self,
        user_query: str,
        query_types: List[str] = None,
        prefetch_id: str = None,
        cache_key: str = None,
    ) -> str:
        """
        Start GraphRAG queries in background for all potential agent types
        Returns a prefetch_id to retrieve results later
        """
        import uuid
        import time
        
        if prefetch_id is None:
            prefetch_id = str(uuid.uuid4())
        if query_types is None:
            query_types = ["planning"]
        
        self.logger.info(f"Starting prefetch for query types: {query_types}")
        
        # Function to run in thread
        def prefetch_worker():
            results = {}
            for context_type in query_types:
                try:
                    # Use cache checking internally
                    result = self.get_relevant_context_for_plan(
                        user_query=user_query,
                        dataset_summary="",
                        context_type=context_type,
                        agent_name=f"Prefetch-{context_type.title()}"
                    )
                    results[context_type] = result
                    if cache_key and result:
                        self._cache[f"{cache_key}:{context_type}"] = (result, time.time())
                    self.logger.info(f"Prefetch completed for {context_type}")
                except Exception as e:
                    self.logger.warning(f"Prefetch failed for {context_type}: {e}")
                    results[context_type] = ""
            
            # Store results
            self._prefetch_cache[prefetch_id] = {
                "results": results,
                "completed_at": time.time(),
                 "cache_key": cache_key,
            }
        
        # Start background thread
        thread = threading.Thread(target=prefetch_worker, daemon=True)
        thread.start()
        self._prefetch_threads[prefetch_id] = thread
        
        return prefetch_id
    
    def get_prefetch_result(
        self,
        prefetch_id: str,
        context_type: str,
        timeout: float = 30.0
    ) -> str:
        """
        Get prefetch result for a specific context type
        Waits if not ready yet (up to timeout)
        """
        import time
        start_time = time.time()
        
        # Wait for prefetch to complete
        while prefetch_id not in self._prefetch_cache:
            if time.time() - start_time > timeout:
                self.logger.warning(f"Prefetch timeout for {prefetch_id}")
                return ""
            
            # Check if thread is still alive
            thread = self._prefetch_threads.get(prefetch_id)
            if thread and not thread.is_alive():
                self.logger.warning(f"Prefetch thread died for {prefetch_id}")
                return ""
            
            time.sleep(0.1)  # Poll every 100ms
        
        # Get result
        cache_data = self._prefetch_cache.get(prefetch_id, {})
        results = cache_data.get("results", {})
        result = results.get(context_type, "")
        
        wait_time = time.time() - start_time
        if result:
            self.logger.info(f"Retrieved prefetch result for {context_type} (waited {wait_time:.2f}s)")
        else:
            self.logger.warning(f"No prefetch result for {context_type}")
        
        return result
    
    def cleanup_prefetch(self, prefetch_id: str):
        """Clean up prefetch data after use"""
        self._prefetch_cache.pop(prefetch_id, None)
        self._prefetch_threads.pop(prefetch_id, None)
        
    def _get_cache_key(self, user_query: str, query_type: str) -> str:
        """Generate consistent cache key"""
        import hashlib
        query_hash = hashlib.md5(f"{query_type}:{user_query}".encode()).hexdigest()
        return query_hash
    
    def get_cached_context(self, cache_key: str, context_type: str = "planning") -> Optional[str]:
        typed_key = f"{cache_key}:{context_type}"
        if typed_key in self._cache:
            result, _ = self._cache[typed_key]
            return result.get("context", "")
        persistent_result = self._load_from_persistent_cache(f"{typed_key}")
        if persistent_result:
            self._cache[typed_key] = (persistent_result, time.time())
            return persistent_result.get("context", "")
        return None

    def _load_from_persistent_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Load from disk cache if exists and not expired"""
        try:
            cache_file = self._persistent_cache_dir / f"{cache_key}.json"
            
            if not cache_file.exists():
                return None
            
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
            
            # Check if expired
            cached_time = cached_data.get('cached_at', 0)
            age = time.time() - cached_time
            
            if age > self._persistent_cache_ttl:
                self.logger.debug(f"Persistent cache expired (age: {age:.0f}s)")
                cache_file.unlink()  # Delete expired cache
                return None
            
            self.logger.info(f"Loaded from persistent cache (age: {age:.0f}s)")
            return cached_data.get('result')
            
        except Exception as e:
            self.logger.warning(f"Failed to load persistent cache: {e}")
            return None
    
    def _save_to_persistent_cache(self, cache_key: str, result: Dict[str, Any]):
        """Save to disk cache"""
        try:
            cache_file = self._persistent_cache_dir / f"{cache_key}.json"
            
            cache_data = {
                'cached_at': time.time(),
                'result': result
            }
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2)
            
            self.logger.debug(f"Saved to persistent cache: {cache_file.name}")
            
        except Exception as e:
            self.logger.warning(f"Failed to save persistent cache: {e}")
    

    def _find_python_312(self) -> Optional[str]:
        """Find Python 3.12 installation"""
        # Try common locations for Python 3.12
        possible_paths = [
            r"C:\Users\saiyam268728\OneDrive - EXLService.com (I) Pvt. Ltd\Documents\MIDAS-Saiyam\KnowledgeRepo_To_KG\venv\Scripts\python.exe",
            r"C:\Python312\python.exe",
            r"C:\Users\{username}\AppData\Local\Programs\Python\Python312\python.exe",
            "python3.12",  # Unix-like systems
            "python3.12.10",
        ]
        
        import os
        username = os.getenv('USERNAME', '')
        
        for path in possible_paths:
            path = path.format(username=username)
            try:
                result = subprocess.run(
                    [path, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=1200
                )
                if "3.12" in result.stdout:
                    self.logger.info(f"Found Python 3.12 at: {path}")
                    return path
            except (subprocess.SubprocessError, FileNotFoundError):
                continue
        
        self.logger.warning("Python 3.12 not found. GraphRAG queries will not work.")
        return None
    
    def is_available(self) -> bool:
        """Check if GraphRAG service is available"""
        return (
            self.python_312_path is not None and
            self.graphrag_root.exists() and
            (self.graphrag_root / "output").exists() and
            self.query_script_path.exists()
        )
    
    def _log_query_response(
        self, 
        query: str, 
        response: Dict[str, Any], 
        query_type: str,
        agent_name: str = "Unknown",
        execution_time: float = 0.0,
        cache_used: bool = False,  # ✅ New parameter
        cache_type: str = None
    ):
        """Log GraphRAG query and response to kg_logs folder"""
        try:
            # Create kg_logs directory if it doesn't exist
            kg_logs_dir = Path(__file__).parent.parent.parent / "kg_logs"
            kg_logs_dir.mkdir(exist_ok=True)
            
            # Create timestamp for filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            log_file = kg_logs_dir / f"graphrag_query_{timestamp}.json"
            
            # Prepare log data with enhanced metadata
            log_data = {
                "timestamp": datetime.now().isoformat(),
                "agent": agent_name,
                "query_type": query_type,
                "execution_time_seconds": round(execution_time, 3),
                "cache_used": cache_used,  # ✅ New field
                "cache_type": cache_type,  # ✅ New field (in-memory, persistent, or null)
                "query": query,
                "response": {
                    "success": response.get("success", False),
                    "context": response.get("context", ""),
                    "error": response.get("error")
                },
                "context_length": len(response.get("context", "")),
                "metadata": {
                    "query_length": len(query),
                    "status": "success" if response.get("success") else "failed"
                }
            }
            
            # Write to file
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, indent=2, ensure_ascii=False)
            
            self.logger.debug(f"GraphRAG query logged to: {log_file}")
            
        except Exception as e:
            self.logger.warning(f"Failed to log GraphRAG query: {e}")

    def query_knowledge_graph(
        self, 
        user_query: str, 
        query_type: str = "local",
        max_tokens: int = 3500,
        agent_name: str = "Unknown",  # New parameter
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Query the GraphRAG knowledge graph
        
        Args:
            user_query: The user's question
            query_type: Type of query ("local" or "global")
            max_tokens: Maximum tokens for response
            agent_name: Name of the agent/method calling this function
            
        Returns:
            Dictionary with 'context', 'success', and 'error' keys
        """
        # Start timing
        import time
        start_time = time.time()
        
        if use_cache:
            cache_key = self._get_cache_key(user_query, query_type)
            
            # 1. Check in-memory cache first (fastest)
            if cache_key in self._cache:
                cached_data, cached_time = self._cache[cache_key]
                age = time.time() - cached_time
                if age < self._cache_ttl:
                    execution_time = time.time() - start_time
                    self.logger.info(f"Using in-memory cache (age: {age:.1f}s)")
                    
                    # ✅ Log cache hit
                    self._log_query_response(
                        user_query, 
                        cached_data, 
                        query_type, 
                        agent_name, 
                        execution_time,
                        cache_used=True,
                        cache_type="in-memory"
                    )
                    
                    return cached_data
            
            # 2. Check persistent disk cache (survives restarts)
            persistent_result = self._load_from_persistent_cache(cache_key)
            if persistent_result:
                execution_time = time.time() - start_time
                self.logger.info(f"Using persistent cache")
                
                # Also populate in-memory cache for next time
                self._cache[cache_key] = (persistent_result, time.time())
                
                # ✅ Log persistent cache hit
                self._log_query_response(
                    user_query, 
                    persistent_result, 
                    query_type, 
                    agent_name, 
                    execution_time,
                    cache_used=True,
                    cache_type="persistent"
                )
                
                return persistent_result
        
        if not self.is_available():
            self.logger.warning("GraphRAG service not available")
            result = {
                "success": False,
                "context": "",
                "error": "GraphRAG service not configured"
            }
            # Log even if not available
            self._log_query_response(user_query, result, query_type, agent_name, time.time() - start_time)
            return result
        
        try:
            # Run the GraphRAG query - pass user query directly
            cmd = [
                str(self.python_312_path),
                str(self.query_script_path),
                "--root", str(self.graphrag_root),
                "--query", user_query,
                "--method", query_type,
                "--max-tokens", str(max_tokens)
            ]
            
            self.logger.info(f"Running GraphRAG {query_type} query for agent: {agent_name}")
            self.logger.debug(f"Query: {user_query[:100]}...")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=1200,
                cwd=str(self.graphrag_root)
            )
            
            # Calculate execution time
            execution_time = time.time() - start_time
            
            self.logger.debug(f"GraphRAG return code: {result.returncode}")
            
            if result.returncode != 0:
                error_msg = result.stderr if result.stderr else result.stdout
                if not error_msg:
                    error_msg = f"Process exited with code {result.returncode}"
                self.logger.error(f"GraphRAG query failed: {error_msg[:500]}")
                
                error_result = {
                    "success": False,
                    "context": "",
                    "error": error_msg[:500]
                }
                
                # Log with timing
                self._log_query_response(user_query, error_result, query_type, agent_name, execution_time)
                return error_result
            
            # Check if stdout is empty
            if not result.stdout or not result.stdout.strip():
                self.logger.error("GraphRAG query returned empty output")
                empty_result = {
                    "success": False,
                    "context": "",
                    "error": "GraphRAG returned empty output"
                }
                self._log_query_response(user_query, empty_result, query_type, agent_name, execution_time)
                return empty_result
            
            # Parse the JSON response
            try:
                response_data = json.loads(result.stdout)
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse GraphRAG response as JSON: {e}")
                self.logger.error(f"Raw output (first 500 chars): {result.stdout[:500]}")
                json_error_result = {
                    "success": False,
                    "context": "",
                    "error": f"Invalid JSON response: {str(e)}"
                }
                self._log_query_response(user_query, json_error_result, query_type, agent_name, execution_time)
                return json_error_result
            
            # Validate response structure
            if not isinstance(response_data, dict):
                self.logger.error(f"GraphRAG response is not a dictionary: {type(response_data)}")
                invalid_result = {
                    "success": False,
                    "context": "",
                    "error": "Invalid response format"
                }
                self._log_query_response(user_query, invalid_result, query_type, agent_name, execution_time)
                return invalid_result
            
            context = response_data.get("context", "")
            self.logger.info(f"GraphRAG query successful in {execution_time:.2f}s, context length: {len(context)}")
            
            success_result = {
                "success": True,
                "context": context,
                "error": None
            }
            
            # Log successful query with timing
            self._log_query_response(
                user_query, 
                success_result, 
                query_type, 
                agent_name, 
                execution_time,
                cache_used=False,  # ✅ Not from cache
                cache_type=None     # ✅ No cache
            )
            
            # Save to caches...
            if use_cache and success_result.get("success"):
                base_key = self._get_cache_key(user_query, query_type)
                typed_key = f"{base_key}:{agent_name}"
                self._cache[typed_key] = (success_result, time.time())
                self._save_to_persistent_cache(typed_key, success_result)

                # (Optional) keep backward-compatible entry if you still need the untyped key elsewhere:
                self._cache[base_key] = (success_result, time.time())
            
            return success_result
            
        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            self.logger.error("GraphRAG query timed out")
            timeout_result = {
                "success": False,
                "context": "",
                "error": "Query timeout"
            }
            
            self._log_query_response(
                user_query, 
                timeout_result, 
                query_type, 
                agent_name, 
                execution_time,
                cache_used=False,  # ✅ Add this
                cache_type=None    # ✅ Add this
            )

            return timeout_result
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error(f"GraphRAG query error: {str(e)}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            exception_result = {
                "success": False,
                "context": "",
                "error": str(e)
            }
            self._log_query_response(user_query, exception_result, query_type, agent_name, execution_time)
            return exception_result
    
    def get_relevant_context_for_plan(
        self, 
        user_query: str, 
        dataset_summary: str = "",
        context_type: str = "planning",
        agent_name: str = "Unknown Agent"  # New parameter
    ) -> str:
        """
        Get relevant context from GraphRAG for planning
        
        Args:
            user_query: The user's question
            dataset_summary: Optional dataset summary for more context
            context_type: Type of context needed (planning, transformation, insights)
            agent_name: Name of the calling agent for logging
            
        Returns:
            Context string from knowledge graph
        """
        # Different prefixes for different use cases
        prefixes = {
            "planning": (
                "Search my knowledge repository and get me relevant modelling and analytical "
                "techniques which can serve user query in the most accurate ways.\n"
                "What I expect are specific named suggestions, algorithms, methods and techniques for specific scenarios.\n"
            ),
            "transformation": (
                "Search my knowledge repository for best practices in data transformation, "
                "code generation, and data quality handling techniques.\n"
                "What I expect are specific named suggestions, algorithms, methods and techniques for specific scenarios.\n"
            ),
            "insights": (
                "Search my knowledge repository for advanced analytical techniques, "
                "insight generation methods, and statistical interpretation best practices.\n"
                "What I expect are specific named suggestions, algorithms, methods and techniques for specific scenarios.\n"
            )
        }
        
        prefix = prefixes.get(context_type, prefixes["planning"])
        enhanced_query = f"{prefix}User Query: {user_query}"
        
        # Pass enhanced query to GraphRAG with agent name
        result = self.query_knowledge_graph(
            user_query=enhanced_query,
            query_type="local",
            max_tokens=3500,
            agent_name=agent_name  # Pass agent name for logging
        )
        
        # Safe access with None checking
        if result is None:
            self.logger.warning("GraphRAG query returned None")
            return ""
        
        if not isinstance(result, dict):
            self.logger.warning(f"GraphRAG query returned unexpected type: {type(result)}")
            return ""
        
        if result.get("success"):
            context = result.get("context", "")
            if context:
                self.logger.info(f"Retrieved GraphRAG context for {agent_name}: {len(context)} characters")
            return context
        else:
            self.logger.warning(f"GraphRAG query failed for {agent_name}: {result.get('error', 'Unknown error')}")
            return ""
# Global GraphRAG service instance
graphrag_service = GraphRAGService()