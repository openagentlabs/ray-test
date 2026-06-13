"""
GraphRAG HTTP Client - Replaces graphrag_service.py
Communicates with GraphRAG microservice via HTTP
"""
import os
import httpx
import time
import json
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
from app.core.logging_config import get_logger
from app.services.context_router import context_router
from app.services.graphrag_process_manager import graphrag_process_manager
from app.services.llm_service import llm_service
from datetime import datetime
import threading
import re
import numpy as np

class GraphRAGClient:
    """HTTP client for GraphRAG microservice"""
    
    def __init__(self, service_url: Optional[str] = None):
        self.logger = get_logger(__name__)
        self.service_url = service_url or os.getenv("GRAPHRAG_SERVICE_URL", "http://localhost:8001")
        self._cache = {}
        self._cache_ttl = 300  # 5 minutes
        self._persistent_cache_dir = Path(__file__).parent.parent.parent / "kg_cache"
        self._persistent_cache_dir.mkdir(exist_ok=True)
        self._persistent_cache_ttl = 864000  # 24 hours
        self._prefetch_cache = {}
        self._prefetch_threads = {}
        self._prefetch_key_map = {}
        self._semantic_threshold = 0.84
        self._semantic_top_n = 2
        self._client = None  # Lazy initialization
        self._last_health_check = 0
        self._health_check_interval = 30  # Recheck every 30 seconds
        self._is_healthy = None
    
    def _get_client(self) -> httpx.Client:
        """Get or create HTTP client"""
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.service_url,
                timeout=httpx.Timeout(10.0, connect=5.0),  # 10s total, 5s connect
                follow_redirects=True
            )
        return self._client
    
    def _reset_client(self):
        """Reset the HTTP client (useful if connection goes stale)"""
        if self._client:
            try:
                self._client.close()
            except:
                pass
        self._client = None
        self._is_healthy = None
    
    def is_available(self, force_check: bool = False) -> bool:
        """Check if GraphRAG service is available with caching"""
        current_time = time.time()
        
        # Use cached result if recent and not forcing check
        if not force_check and self._is_healthy is not None:
            if current_time - self._last_health_check < self._health_check_interval:
                return self._is_healthy
        
        graphrag_process_manager.ensure_running()

        # Perform health check with retries
        for attempt in range(2):  # Try twice
            try:
                client = self._get_client()
                response = client.get("/health", timeout=5.0)
                if response.status_code == 200:
                    data = response.json()
                    self._is_healthy = data.get("graphrag_available", False)
                    self._last_health_check = current_time
                    if self._is_healthy:
                        self.logger.info("GraphRAG service is available")
                    return self._is_healthy
            except Exception as e:
                self.logger.debug(f"Health check attempt {attempt + 1} failed: {e}")
                if attempt == 0:
                    # Reset client and retry
                    self._reset_client()
                    continue
                self.logger.warning(f"GraphRAG service not available: {e}")
        
        self._is_healthy = False
        self._last_health_check = current_time
        return False
    
    def query_knowledge_graph(
        self,
        user_query: str,
        query_type: str = "local",
        max_tokens: int = 3500,
        agent_name: str = "Unknown",
        use_cache: bool = True,
        context_type: Optional[str] = None  # ADD THIS
    ) -> Dict[str, Any]:
        """Query GraphRAG service via HTTP"""
        start_time = time.time()
        
        # If context_type not provided, try to infer from agent_name or use query_type
        if context_type is None:
            # Try to infer from agent_name
            if "planning" in agent_name.lower() or "planner" in agent_name.lower():
                context_type = "planning"
            elif "transformation" in agent_name.lower() or "transform" in agent_name.lower():
                context_type = "transformation"
            elif "insight" in agent_name.lower():
                context_type = "insights"
            else:
                context_type = query_type  # Fallback to query_type

        # Check cache first
        if use_cache:
            cache_key = self._get_cache_key(user_query, query_type)
            cached = self.get_cached_context(cache_key, context_type)  # FIX: Use context_type
            if cached:
                execution_time = time.time() - start_time
                self._log_query_response(
                    user_query, {"success": True, "context": cached, "error": None},
                    query_type, agent_name, execution_time, cache_used=True, cache_type="in-memory"
                )
                return {"success": True, "context": cached, "error": None}
        
        
        # Check if service is available first
        if not self.is_available():
            return {"success": False, "context": "", "error": "GraphRAG service not available"}
        
        # Query service with retry
        last_error = None
        for attempt in range(2):
            try:
                client = self._get_client()
                self.logger.info(f"Querying GraphRAG service (attempt {attempt + 1})")
                response = client.post(
                    "/query",
                    json={
                        "query": user_query,
                        "query_type": query_type,
                        "max_tokens": max_tokens,
                        "agent_name": agent_name
                    },
                    timeout=300.0  # 5 minutes for queries
                )
                
                execution_time = time.time() - start_time
                
                if response.status_code == 200:
                    result = response.json()
                    success_result = {
                        "success": result.get("success", False),
                        "context": result.get("context", ""),
                        "error": result.get("error")
                    }
                    
                    # Log and cache successful queries
                    if success_result.get("success"):
                        self._log_query_response(
                            user_query, success_result, query_type, agent_name,
                            execution_time, cache_used=False
                        )
                        # Cache the result
                        if use_cache:
                            cache_key = self._get_cache_key(user_query, query_type)
                            typed_key = f"{cache_key}:{context_type}"  # FIX: Use context_type, not query_type
                            cached_result = self._with_cache_meta(
                                success_result,
                                original_query=user_query,
                                normalized_query=self._normalize_query(user_query),
                                tasks=self._extract_task_items(user_query),
                                dataset_summary="",
                            )
                            self._cache[typed_key] = (cached_result, time.time())
                            # Also save to persistent cache
                            self._save_to_persistent_cache(typed_key, cached_result)
                    
                    return success_result
                else:
                    last_error = f"Service returned status {response.status_code}"
                    
            except httpx.TimeoutException as e:
                last_error = f"Request timeout: {e}"
                self.logger.warning(f"Query attempt {attempt + 1} timed out")
            except Exception as e:
                last_error = str(e)
                self.logger.warning(f"Query attempt {attempt + 1} failed: {e}")
            
            # Reset client before retry
            if attempt == 0:
                self._reset_client()
        
        execution_time = time.time() - start_time
        result = {"success": False, "context": "", "error": last_error}
        self._log_query_response(user_query, result, query_type, agent_name, execution_time)
        return result
    
    # Update get_relevant_context_for_plan to pass context_type
    def get_relevant_context_for_plan(
        self,
        user_query: str,
        dataset_summary: str = "",
        context_type: str = "planning",
        agent_name: str = "Unknown Agent"
    ) -> str:
        """Get relevant context - cache is shared across all context types"""
        summary_block = self._summary_block(dataset_summary)
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
        
        # Task-list aware cache (multi-task query)
        tasks = self._extract_task_items(user_query)
        if tasks:
            contexts = []
            for task in tasks:
                task_query = self._task_query(task)
                task_cache_key = self._get_cache_key(task_query, dataset_summary=dataset_summary)
                cached_task = self.get_cached_context(task_cache_key)
                if cached_task:
                    contexts.append(cached_task)
                    continue

                # Not cached: use router + GraphRAG for this task only
                router_result = context_router.evaluate(task_query, dataset_summary=dataset_summary)
                vector_context = router_result.get("vector_context", "")
                status = router_result.get("status")
                self.logger.info(
                    "Context router outcome for task=%s: status=%s top_score=%.3f coverage=%.2f", 
                    task[:40], status, router_result.get("top_score", 0.0), router_result.get("coverage", 0.0)
                )

                if status == "vector_only" and vector_context:
                    self._log_vector_router_context(
                        task_query,
                        router_result,
                        vector_context,
                        top_k=context_router.top_k,
                        candidate_k=max(context_router.top_k * 4, 10),
                    )
                    contexts.append(vector_context)
                    self._store_shared_context(
                        task_cache_key,
                        vector_context,
                        agent_name,
                        original_query=task_query,
                        tasks=[task],
                        dataset_summary=dataset_summary,
                    )
                    continue

                if not self.is_available():
                    if vector_context:
                        self.logger.warning("GraphRAG unavailable; returning router-led vector context as fallback")
                        contexts.append(vector_context)
                        self._store_shared_context(
                            task_cache_key,
                            vector_context,
                            agent_name,
                            original_query=task_query,
                            tasks=[task],
                            dataset_summary=dataset_summary,
                        )
                    continue

                vector_hint = f"\n\nVector context:\n{vector_context}\n" if vector_context else ""
                prefix = prefixes.get(context_type, prefixes["planning"])
                enhanced_query = f"{prefix}User Query: {task_query}{summary_block}{vector_hint}"

                result = self.query_knowledge_graph(
                    user_query=enhanced_query,
                    query_type="local",
                    max_tokens=3500,
                    agent_name=agent_name,
                    use_cache=False,
                    context_type=context_type
                )
                if result.get("success"):
                    context = result.get("context", "")
                    if context:
                        contexts.append(context)
                        self._store_shared_context(
                            task_cache_key,
                            context,
                            agent_name,
                            original_query=task_query,
                            tasks=[task],
                            dataset_summary=dataset_summary,
                        )
            return "\n\n".join([ctx for ctx in contexts if ctx])

        # Generate cache key from ORIGINAL query only (shared across all agents)
        cache_key = self._get_cache_key(user_query, dataset_summary=dataset_summary)
        
        # Check cache first (no context_type suffix - shared!)
        cached = self.get_cached_context(cache_key)
        if cached:
            self.logger.info(f"Using shared cached context for {context_type} ({len(cached)} chars)")
            return cached

        # Semantic cache fallback (non-task queries)
        semantic_hit = self._get_semantic_cache_hit(user_query, dataset_summary=dataset_summary)
        if semantic_hit:
            self.logger.info(f"Using semantic cached context for {context_type} ({len(semantic_hit)} chars)")
            return semantic_hit
        
        # Not in cache - run vector router first, then create enhanced query and query GraphRAG if needed
        router_result = context_router.evaluate(user_query, dataset_summary=dataset_summary)
        vector_context = router_result.get("vector_context", "")
        status = router_result.get("status")
        self.logger.info(
            "Context router outcome for %s: status=%s top_score=%.3f coverage=%.2f", 
            user_query[:60], status, router_result.get("top_score", 0.0), router_result.get("coverage", 0.0)
        )

        if status == "vector_only" and vector_context:
            self.logger.info("Vector-only context is confident; skipping GraphRAG")
            self._log_vector_router_context(
                user_query,
                router_result,
                vector_context,
                top_k=context_router.top_k,
                candidate_k=max(context_router.top_k * 4, 10),
            )
            return vector_context

        if not self.is_available():
            if vector_context:
                self.logger.warning("GraphRAG unavailable; returning router-led vector context as fallback")
                return vector_context
            return ""

        vector_hint = f"\n\nVector context:\n{vector_context}\n" if vector_context else ""
        prefix = prefixes.get(context_type, prefixes["planning"])
        enhanced_query = f"{prefix}User Query: {user_query}{summary_block}{vector_hint}"

        # Query the service
        result = self.query_knowledge_graph(
            user_query=enhanced_query,
            query_type="local",
            max_tokens=3500,
            agent_name=agent_name,
            use_cache=False,  # Don't cache internally with enhanced query
            context_type=context_type
        )
        
        # Cache the result using ORIGINAL query key (NO SUFFIX - shared)
        if result.get("success"):
            context = result.get("context", "")
            if context:
                # Store WITHOUT context_type suffix (shared cache) in background
                threading.Thread(
                    target=self._store_shared_context,
                    args=(cache_key, context, agent_name, user_query, tasks, dataset_summary),
                    daemon=True
                ).start()
            return context
        else:
            error_msg = result.get("error", "Unknown error")
            self.logger.warning(f"GraphRAG query failed for {agent_name}: {error_msg}")
            if vector_context:
                self.logger.info(
                    "Returning vector context after GraphRAG failure for %s (status=%s top_score=%.3f coverage=%.2f)",
                    agent_name,
                    status,
                    router_result.get("top_score", 0.0),
                    router_result.get("coverage", 0.0),
                )
                return vector_context
            return ""
    
    # Cache and prefetch methods
    def _get_cache_key(self, user_query: str, query_type: str = None, dataset_summary: str = "") -> str:
        """Generate cache key based on user query + dataset summary signature."""
        import hashlib
        base = user_query
        if dataset_summary:
            base = f"{user_query}||summary:{self._summary_signature(dataset_summary)}"
        return hashlib.md5(base.encode()).hexdigest()

    def _normalize_query(self, query: str, dataset_summary: str = "") -> str:
        normalized = (query or "").lower()
        normalized = normalized.replace("•", " ").replace("-", " ").replace(",", " ")
        normalized = re.sub(r"\s+", " ", normalized).strip()
        if dataset_summary:
            summary_norm = re.sub(r"\s+", " ", dataset_summary.lower()).strip()
            normalized = f"{normalized} || summary: {summary_norm}"
        return normalized

    def _summary_signature(self, dataset_summary: str) -> str:
        import hashlib
        if not dataset_summary:
            return ""
        summary_norm = re.sub(r"\s+", " ", dataset_summary.strip().lower())
        return hashlib.md5(summary_norm.encode()).hexdigest()

    def _truncate_summary(self, dataset_summary: str, limit: int = 1200) -> str:
        if not dataset_summary:
            return ""
        return dataset_summary.strip()[:limit]

    def _summary_block(self, dataset_summary: str) -> str:
        truncated = self._truncate_summary(dataset_summary)
        if not truncated:
            return ""
        return f"\n\nDataset Summary:\n{truncated}\n"

    def _extract_task_items(self, query: str) -> List[str]:
        if not query:
            return []
        lines = [line.strip() for line in query.splitlines() if line.strip()]
        tasks = []
        for line in lines:
            lower_line = line.lower()
            if ":" in line:
                # Handle inline list after a label (tasks/checks/etc.)
                label, parts = line.split(":", 1)
                if re.search(r"\btasks?\b", label.lower()) or re.search(r"\bchecks?\b", label.lower()):
                    for item in re.split(r"[•\-\*\n,]", parts):
                        item = item.strip().lower()
                        if item:
                            tasks.append(item)
                    continue
                # Generic fallback: if RHS looks like a list, parse it
                if re.search(r"[•\-\*,]", parts):
                    for item in re.split(r"[•\-\*\n,]", parts):
                        item = item.strip().lower()
                        if item:
                            tasks.append(item)
                    continue
            if line.startswith(("•", "-", "*")):
                item = line.lstrip("•-*").strip().lower()
                if item:
                    tasks.append(item)
            # Inline list without label (e.g., "missing_values, outliers")
            if not tasks and re.search(r"[a-z_]+,\s*[a-z_]+", lower_line):
                for item in re.split(r"[•\-\*\n,]", lower_line):
                    item = item.strip().lower()
                    if item:
                        tasks.append(item)
        # Deduplicate, preserve order
        seen = set()
        unique_tasks = []
        for task in tasks:
            task_norm = re.sub(r"[^a-z0-9_]+", " ", task).strip()
            if task_norm and task_norm not in seen:
                seen.add(task_norm)
                unique_tasks.append(task_norm)
        return unique_tasks

    def _task_query(self, task: str) -> str:
        base_context = "Performing Data Treatment on following tasks:"
        return f"{base_context} {task}"
    
    # Add this helper method after _get_cache_key (around line 213)
    def _sanitize_cache_key_for_filename(self, cache_key: str) -> str:
        """Sanitize cache key for use in filenames (Windows doesn't allow colons)"""
        return cache_key.replace(":", "_")

    def _store_shared_context(self, cache_key: str, context: str, agent_name: str,
                              original_query: str = "", tasks: List[str] = None,
                              dataset_summary: str = ""):
        """Store context in shared in-memory and persistent caches."""
        try:
            safe_key = self._sanitize_cache_key_for_filename(cache_key)
            cache_entry = self._with_cache_meta(
                {"context": context, "success": True},
                original_query=original_query,
                normalized_query=self._normalize_query(original_query, dataset_summary),
                tasks=tasks or [],
                dataset_summary=dataset_summary,
            )
            self._cache[cache_key] = (cache_entry, time.time())
            self._save_to_persistent_cache(safe_key, cache_entry)
            self.logger.info(f"Cached context (shared) for {agent_name}: {len(context)} characters")
        except Exception as e:
            self.logger.warning(f"Failed to store shared context for {agent_name}: {e}")

    # Update _load_from_persistent_cache (around line 225)
    def _load_from_persistent_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Load from disk cache if exists and not expired"""
        try:
            # Sanitize the cache key for filename
            safe_key = self._sanitize_cache_key_for_filename(cache_key)
            cache_file = self._persistent_cache_dir / f"{safe_key}.json"
            
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

    # Update _save_to_persistent_cache (around line 245)
    def _save_to_persistent_cache(self, cache_key: str, result: Dict[str, Any]):
        """Save to disk cache"""
        try:
            # Sanitize the cache key for filename
            safe_key = self._sanitize_cache_key_for_filename(cache_key)
            cache_file = self._persistent_cache_dir / f"{safe_key}.json"
            
            cache_data = {
                'cached_at': time.time(),
                'result': result
            }
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2)
            
            self.logger.debug(f"Saved to persistent cache: {cache_file.name}")
            
        except Exception as e:
            self.logger.warning(f"Failed to save persistent cache: {e}")

    def _find_prefetch_by_cache_key(self, cache_key: str) -> Optional[str]:
        """Return running prefetch_id for a cache key, if any"""
        return self._prefetch_key_map.get(cache_key)
    
    def get_cached_context(self, cache_key: str, context_type: str = "planning") -> Optional[str]:
        """Check both in-memory and persistent cache (shared - no context_type suffix)"""
        
        # 1. Check in-memory cache (no suffix)
        if cache_key in self._cache:
            result, cached_time = self._cache[cache_key]
            age = time.time() - cached_time
            if age < self._cache_ttl:
                self.logger.info(f"Cache hit (in-memory, age: {age:.1f}s) [shared]")
                if isinstance(result, dict):
                    return result.get("context", "")
                else:
                    return result if isinstance(result, str) else ""
            else:
                del self._cache[cache_key]
        
        # 2. Check persistent disk cache (no suffix)
        safe_key = self._sanitize_cache_key_for_filename(cache_key)
        persistent_result = self._load_from_persistent_cache(safe_key)
        if persistent_result:
            self._cache[cache_key] = (persistent_result, time.time())  # No suffix!
            if isinstance(persistent_result, dict):
                return persistent_result.get("context", "")
            else:
                return persistent_result if isinstance(persistent_result, str) else ""
        
        return None

    def _with_cache_meta(self, result: Dict[str, Any], original_query: str,
                         normalized_query: str, tasks: List[str],
                         dataset_summary: str) -> Dict[str, Any]:
        meta = {
            "original_query": original_query,
            "normalized_query": normalized_query,
            "tasks": tasks or [],
            "dataset_summary_signature": self._summary_signature(dataset_summary),
        }
        embedding = self._get_query_embedding(normalized_query)
        if embedding is not None:
            meta["embedding"] = embedding
        result_with_meta = dict(result)
        result_with_meta["meta"] = meta
        return result_with_meta

    def _get_query_embedding(self, normalized_query: str) -> Optional[List[float]]:
        if not normalized_query or not llm_service.embedding_ready:
            return None
        try:
            vectors = llm_service.get_embeddings([normalized_query])
            if not vectors:
                return None
            return [float(x) for x in vectors[0]]
        except Exception as exc:
            self.logger.debug(f"Embedding generation failed for semantic cache: {exc}")
            return None

    def _get_semantic_cache_hit(self, user_query: str, dataset_summary: str = "") -> str:
        normalized = self._normalize_query(user_query, dataset_summary)
        query_embedding = self._get_query_embedding(normalized)
        if query_embedding is None:
            return ""

        candidates = []
        for cache_key, (result, _) in self._cache.items():
            if not isinstance(result, dict):
                continue
            meta = result.get("meta", {})
            embedding = meta.get("embedding")
            if not embedding:
                continue
            sim = self._cosine_similarity(query_embedding, embedding)
            if sim >= self._semantic_threshold:
                candidates.append((sim, result.get("context", "")))

        if not candidates:
            return ""

        candidates.sort(key=lambda item: item[0], reverse=True)
        top_contexts = [ctx for _, ctx in candidates[: self._semantic_top_n] if ctx]
        return "\n\n".join(top_contexts)

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        vec_a = np.array(a, dtype=np.float32)
        vec_b = np.array(b, dtype=np.float32)
        denom = (np.linalg.norm(vec_a) * np.linalg.norm(vec_b))
        if denom == 0:
            return 0.0
        return float(np.dot(vec_a, vec_b) / denom)
    
    def warm_context_cache(
        self,
        user_query: str,
        context_types: List[str] = None,
        agent_name: str = "Prefetch-Warm",
        dataset_summary: str = ""
    ) -> Dict[str, Any]:
        """Warm the shared cache for a query and optionally return the prefetch_id"""
        if context_types is None:
            context_types = ["planning"]
        cache_key = self._get_cache_key(user_query, dataset_summary=dataset_summary)
        cached = self.get_cached_context(cache_key)
        if cached:
            return {"cache_key": cache_key, "prefetch_id": None, "cached": True}

        existing_prefetch = self._find_prefetch_by_cache_key(cache_key)
        if existing_prefetch:
            return {"cache_key": cache_key, "prefetch_id": existing_prefetch, "cached": False}

        prefetch_id = self.start_prefetch_query(
            user_query=user_query,
            query_types=context_types,
            cache_key=cache_key,
            dataset_summary=dataset_summary,
            agent_name=agent_name
        )
        return {"cache_key": cache_key, "prefetch_id": prefetch_id, "cached": False}
    
    # Fix the prefetch to store results correctly
    def start_prefetch_query(self, user_query: str, query_types: List[str] = None, 
                            prefetch_id: str = None, cache_key: str = None,
                            dataset_summary: str = "", agent_name: str = "PrefetchWorker") -> str:
        """Start prefetch queries in background - cache is shared"""
        import uuid
        if prefetch_id is None:
            prefetch_id = str(uuid.uuid4())
        if query_types is None:
            query_types = ["planning"]
        if cache_key is None:
            cache_key = self._get_cache_key(user_query, dataset_summary=dataset_summary)

        self._prefetch_key_map[cache_key] = prefetch_id
        self.logger.info(f"Starting prefetch for query types: {query_types}")
        
        def prefetch_worker():
            results = {}
            # Query once, share result across all types
            first_context_type = query_types[0] if query_types else "planning"
            
            try:
                # This will cache internally, so we don't need to cache again
                result = self.get_relevant_context_for_plan(
                    user_query=user_query,
                    dataset_summary=dataset_summary,
                    context_type=first_context_type,
                    agent_name=agent_name or f"Prefetch-{first_context_type.title()}"
                )
                
                # Store same result for ALL context types
                for context_type in query_types:
                    results[context_type] = result
                
                self.logger.info(f"Prefetch completed (shared cache, {len(result) if result else 0} chars)")
            except Exception as e:
                self.logger.warning(f"Prefetch failed: {e}")
                for context_type in query_types:
                    results[context_type] = ""
            finally:
                self._prefetch_cache[prefetch_id] = {
                    "results": results,
                    "completed_at": time.time(),
                    "cache_key": cache_key,
                }
                self._prefetch_key_map.pop(cache_key, None)
        
        thread = threading.Thread(target=prefetch_worker, daemon=True)
        thread.start()
        self._prefetch_threads[prefetch_id] = thread
        return prefetch_id
    
    def get_prefetch_result(self, prefetch_id: str, context_type: str, timeout: float = 30.0) -> str:
        """Get prefetch result, waiting if not ready"""
        start_time = time.time()
        while prefetch_id not in self._prefetch_cache:
            if time.time() - start_time > timeout:
                self.logger.warning(f"Prefetch timeout for {prefetch_id}")
                return ""
            thread = self._prefetch_threads.get(prefetch_id)
            if thread and not thread.is_alive():
                self.logger.warning(f"Prefetch thread died for {prefetch_id}")
                return ""
            time.sleep(0.1)
        
        cache_data = self._prefetch_cache.get(prefetch_id, {})
        cache_key = cache_data.get("cache_key")
        if cache_key:
            cached = self.get_cached_context(cache_key, context_type)
            if cached:
                self.logger.info(f"Retrieved cached context for {context_type} via shared cache (prefetch {prefetch_id})")
                results = cache_data.setdefault("results", {})
                results[context_type] = cached
                result = cached
            else:
                results = cache_data.get("results", {})
                result = results.get(context_type, "")
        else:
            results = cache_data.get("results", {})
            result = results.get(context_type, "")
        
        wait_time = time.time() - start_time
        if result:
            self.logger.info(f"Retrieved prefetch result for {context_type} (waited {wait_time:.2f}s)")
        
        return result
    
    def cleanup_prefetch(self, prefetch_id: str):
        """Clean up prefetch data after use"""
        cache_data = self._prefetch_cache.pop(prefetch_id, None)
        if cache_data:
            cache_key = cache_data.get("cache_key")
            if cache_key:
                self._prefetch_key_map.pop(cache_key, None)
        self._prefetch_threads.pop(prefetch_id, None)
    
    def _log_query_response(self, query: str, response: Dict[str, Any], query_type: str,
                           agent_name: str, execution_time: float, cache_used: bool = False,
                           cache_type: str = None):
        """Log query response (same as before)"""
        try:
            kg_logs_dir = Path(__file__).parent.parent.parent / "kg_logs"
            kg_logs_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            log_file = kg_logs_dir / f"graphrag_query_{timestamp}.json"
            
            log_data = {
                "timestamp": datetime.now().isoformat(),
                "agent": agent_name,
                "query_type": query_type,
                "execution_time_seconds": round(execution_time, 3),
                "cache_used": cache_used,
                "cache_type": cache_type,
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
            
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.warning(f"Failed to log GraphRAG query: {e}")

    def _log_vector_router_context(self, query: str, router_result: Dict[str, Any],
                                   context: str, top_k: int, candidate_k: int):
        try:
            kg_logs_dir = Path(__file__).parent.parent.parent / "kg_logs"
            kg_logs_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            log_file = kg_logs_dir / f"vector_router_{timestamp}.json"

            log_data = {
                "timestamp": datetime.now().isoformat(),
                "query": query,
                "status": router_result.get("status"),
                "top_score": router_result.get("top_score"),
                "avg_score": router_result.get("avg_score"),
                "coverage": router_result.get("coverage"),
                "context_length": len(context),
                "context": context,
                "metadata": {
                    "top_k": top_k,
                    "candidate_k": candidate_k
                }
            }

            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.warning(f"Failed to log vector router context: {e}")

# Global instance
graphrag_client = GraphRAGClient()
