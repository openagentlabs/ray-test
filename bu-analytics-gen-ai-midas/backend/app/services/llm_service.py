import re
import os
import json
from typing import List, Dict, Any, Optional, Union, Literal, Tuple
from litellm import completion, embedding
from pydantic import BaseModel, Field
from app.core.config import (
    LitellmUsageConfig,
    settings,
    env_override_present,
    gateway_enabled,
    DEFAULT_CHAT_MODEL,
    DEFAULT_KG_MODEL,
    DEFAULT_EMBEDDING_MODEL,
    _normalize_bedrock_model,
)
from app.core.llm_registry import get_model_config
from app.core.llm_routing import candidates_for
from app.core.logging_config import get_logger, hash_for_log

import logging as _logging
_router_logger = _logging.getLogger("midas.llm.router")
import time
import concurrent.futures
from threading import Thread
import csv
from io import StringIO
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed

MAX_PARALLEL_BATCHES = int(os.getenv("KG_PARALLEL_BATCHES", 5))
MAX_BATCH_RETRIES = int(os.getenv("KG_BATCH_RETRIES", 5))
BATCH_RETRY_SLEEP_SECONDS = int(os.getenv("KG_RETRY_SLEEP_SECONDS", 10))


def _build_litellm_kwargs(config: LitellmUsageConfig, overrides: Dict[str, Any]) -> Dict[str, Any]:
    merged = config.build_request_kwargs()
    merged.update(overrides)
    return {k: v for k, v in merged.items() if v is not None}


def _safe_content_char_count(content: Any) -> int:
    if content is None:
        return 0
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        return sum(_safe_content_char_count(part) for part in content)
    if isinstance(content, dict):
        t = content.get("text") or content.get("content")
        if t is not None:
            return _safe_content_char_count(t)
        return 0
    return 0


def _safe_message_char_count(messages: Optional[List[Any]]) -> int:
    if not messages:
        return 0
    total = 0
    for m in messages:
        if isinstance(m, dict):
            total += _safe_content_char_count(m.get("content"))
    return total


def _finish_reason_from_response(response: Any) -> Optional[str]:
    try:
        if response is not None and getattr(response, "choices", None):
            return getattr(response.choices[0], "finish_reason", None)
    except (IndexError, AttributeError, TypeError):
        pass
    return None


def _response_content_chars(response: Any) -> Optional[int]:
    try:
        if not response or not getattr(response, "choices", None):
            return None
        msg = response.choices[0].message
        c = getattr(msg, "content", None)
        if isinstance(c, str):
            return len(c)
        return _safe_content_char_count(c)
    except (IndexError, AttributeError, TypeError):
        return None


def _usage_tokens_from_response(response: Any) -> Dict[str, int]:
    out: Dict[str, int] = {}
    if response is None:
        return out
    u = getattr(response, "usage", None)
    if u is None:
        return out
    if isinstance(u, dict):
        pt = u.get("prompt_tokens")
        ct = u.get("completion_tokens")
        tt = u.get("total_tokens")
    else:
        pt = getattr(u, "prompt_tokens", None)
        ct = getattr(u, "completion_tokens", None)
        tt = getattr(u, "total_tokens", None)
    if pt is not None:
        out["prompt_tokens"] = int(pt)
    if ct is not None:
        out["completion_tokens"] = int(ct)
    if tt is not None:
        out["total_tokens"] = int(tt)
    return out


class resp(BaseModel):
    variable: str
    detection: str
    treatment: str

class MissingValue(BaseModel):
    missing_value: list[resp]

class Outliers(BaseModel):
    outliers: list[resp]

class ClassImbalance(BaseModel):
    class_imbalance: list[resp]

class Correlation(BaseModel):
    correlation: list[resp]

class EDA(BaseModel):
    eda: list[resp]
class Duplicates(BaseModel):
    duplicates: list[resp]

class Plan(BaseModel):    
    missing_values: Optional[list[resp]] = None
    outliers: Optional[list[resp]] = None
    #class_imbalance: Optional[list[resp]] = None
    #correlation: Optional[list[resp]] = None
    duplicates: Optional[list[resp]] = None
    #EDA: Optional[list[resp]] = None

class DataResponse(BaseModel):
    response: str
    code: str
    suggestion: List[str]

class VariableInfo(BaseModel):
    name: str
    category: str 
    type: str  # 'Numerical', 'Categorical', 'DateTime', 'Boolean', 'Text'
    subtype: Optional[str] = None  # 'Continuous', 'Discrete', 'Ordinal', 'Nominal', etc.
    description: str
    role: str  # 'Target', 'Feature', 'Identifier', 'Drop'
    confidence: float  # 0.0 to 1.0

class VariableClassificationResponse(BaseModel):
    dataset_summary: str
    variables: List[VariableInfo]
    recommendations: List[str]
    quality_score: float

class CategoryInfo(BaseModel):
    name: str
    color: str

class GraphNode(BaseModel):
    id: str
    group: str  # 'category' for category nodes, or the category name for variable nodes
    size: int
    color: str

class GraphLink(BaseModel):
    source: str
    target: str
    strength: float  # 0.0 to 1.0

class KnowledgeGraphJSONResponse(BaseModel):
    nodes: List[GraphNode]
    links: List[GraphLink]
    categories: List[CategoryInfo]  # Changed from Dict[str, str] to List[CategoryInfo]
    algorithm_explanation: str
    relationship_mapping: str
    usage_instructions: str

class DatasetTypeClassificationLLMResponse(BaseModel):
    dataset_type: str  # "classification", "regression", "time_series", "others"
    confidence: float  # 0.0 to 1.0
    reasoning: str
    characteristics: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)

class CategoryDefinition(BaseModel):
    name: str
    description: str
    color: str
    keywords: List[str]  # Keywords to help identify which columns belong to this category

class CategoryPlanResponse(BaseModel):
    categories: List[CategoryDefinition]
    reasoning: str
# ================================
# Standard Data Insights Schemas
# ================================

class GenericInsightResponse(BaseModel):
    """Generic response model for all insight types"""
    insights: List[str]

# Insight type mapping for backward compatibility
INSIGHT_TYPE_MAPPING = {
    'bivariate': 'llm_bivariate_insight',
    'correlation': 'llm_correlation_insight', 
    'vif': 'llm_vif_insight',
    'iv': 'llm_iv_insight',
    'correlation_matrix': 'llm_correlation_matrix_insight',
    'correlation_ratio': 'llm_correlation_ratio_insight',
    'duplicates': 'llm_duplicates_insight',
    'deduplication': 'llm_duplicates_insight'  # Backward compatibility
}

# Cache for progressive knowledge graph updates
_kg_progressive_cache = {}

def _kg_cache_key(dataset_id: Optional[str], model_id: Optional[str]) -> str:
    if dataset_id is None:
        return f"kg_{model_id or 'default'}"
    if model_id:
        return f"{dataset_id}::{model_id}"
    return dataset_id

def get_kg_cache(dataset_id: str) -> Optional[Dict]:
    """Get cached progressive KG result"""
    return _kg_progressive_cache.get(dataset_id)

def set_kg_cache(cache_key: str, data: Dict):
    """Cache progressive KG result"""
    _kg_progressive_cache[cache_key] = data
    
def clear_kg_cache(dataset_id: str):
    """Clear cached KG result"""
    _kg_progressive_cache.pop(dataset_id, None)

def generate_knowledge_graph_html(
    nodes: List[Dict], 
    links: List[Dict], 
    categories: List[Dict],
    status: str = "Completed",
    progress: str = ""
) -> str:
    """
    Convert knowledge graph JSON data to interactive HTML visualization.
    
    Args:
        nodes: List of node dictionaries with id, group, size, color
        links: List of link dictionaries with source, target, strength
        categories: List of category dictionaries with name and color
        status: Current generation status ("Updating" or "Completed")
        progress: Progress information (e.g., "2/5 batches")
        
    Returns:
        Complete HTML string with embedded D3.js visualization
    """
    
    # Convert Python data to JavaScript
    nodes_js = json.dumps(nodes)
    links_js = json.dumps(links)
    
    # Generate legend items HTML
    legend_items_html = "\n".join([
        f'<div class="legend-item"><div class="legend-color" style="background-color: {cat["color"]};"></div><span>{cat["name"]}</span></div>'
        for cat in categories
    ])
    
    # Generate filter options
    filter_options_html = "\n".join([
        f'<option value="{cat["name"]}">{cat["name"]}</option>'
        for cat in categories
    ])
    
    # Status indicator styling
    status_color = "#4CAF50" if status == "Completed" else "#FF9800"
    status_icon = "✓" if status == "Completed" else "⟳"
    
    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Knowledge Graph - Feature Relationships</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>
<style>
  :root {{
    --kg-bg: #0b0d12;
    --kg-bg-accent: #11141b;
    --kg-surface: rgba(18, 21, 29, 0.92);
    --kg-surface-strong: rgba(22, 26, 34, 0.96);
    --kg-border: rgba(255, 255, 255, 0.08);
    --kg-text: #f4f5f7;
    --kg-text-muted: #a7abb4;
    --kg-shadow: 0 18px 40px rgba(0, 0, 0, 0.55);
  }}
  body {{
    margin: 0; padding: 20px;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    color: var(--kg-text);
    background:
      radial-gradient(circle at 15% 15%, rgba(255, 255, 255, 0.04), transparent 45%),
      radial-gradient(circle at 85% 10%, rgba(255, 255, 255, 0.03), transparent 40%),
      linear-gradient(145deg, var(--kg-bg) 0%, var(--kg-bg-accent) 55%, #0a0c10 100%);
    height: 100vh;
    overflow: hidden;
  }}
  #graph {{
    position: relative;
    width: 100%;
    height: 90vh;
    border-radius: 16px;
    background:
      radial-gradient(circle at 20% 20%, rgba(255, 255, 255, 0.05), rgba(10, 12, 16, 0.88) 35%, rgba(8, 10, 14, 0.95) 70%),
      linear-gradient(180deg, #0c0f14 0%, #12151c 100%);
    border: 1px solid var(--kg-border);
    box-shadow: var(--kg-shadow);
    overflow: hidden;
  }}
  #graph::before {{
    content: '';
    position: absolute;
    inset: 0;
    background-image:
      linear-gradient(rgba(255, 255, 255, 0.06) 1px, transparent 1px),
      linear-gradient(90deg, rgba(255, 255, 255, 0.06) 1px, transparent 1px);
    background-size: 36px 36px;
    opacity: 0.5;
    pointer-events: none;
  }}
  .node {{
    cursor: pointer;
    stroke: none;
    stroke-width: 0;
    transition: none;
  }}
  .node:hover {{
    filter: none;
  }}
  .node-category {{
    stroke: none;
    stroke-width: 0;
  }}
  .label {{
    font-size: 12px;
    font-weight: 600;
    fill: #f5f5f5;
    pointer-events: none;
    text-shadow: 0 1px 2px rgba(0,0,0,0.55);
  }}
  .label-category {{
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.2px;
  }}
  .link {{
    stroke: rgba(220, 220, 220, 0.85);
    stroke-opacity: 0.9;
    transition: stroke-opacity 0.3s ease, stroke-width 0.3s ease;
  }}
  .link-strong {{
    stroke: rgba(235, 235, 235, 0.95);
  }}
  .link-soft {{
    stroke: rgba(200, 200, 200, 0.6);
  }}
  .link.highlighted {{
    stroke: #e5e7eb;
    stroke-opacity: 1;
    stroke-width: 3px;
    filter: drop-shadow(0 0 6px rgba(0, 0, 0, 0.45));
  }}
  .tooltip {{
    position: absolute;
    pointer-events: none;
    background: rgba(20, 22, 28, 0.95);
    color: white;
    padding: 8px 12px;
    border-radius: 10px;
    font-size: 12px;
    line-height: 1.4;
    max-width: 280px;
    box-shadow: 0 8px 18px rgba(0, 0, 0, 0.4);
    opacity: 0;
    transition: opacity 0.2s ease;
  }}
  .controls {{
    position: absolute;
    top: 18px;
    left: 18px;
    background: transparent;
    padding: 0;
    border-radius: 0;
    border: none;
    box-shadow: none;
    z-index: 100;
    min-width: 200px;
    max-width: 280px;
    color: #111827;
  }}
  .controls select {{
    width: 100%;
    padding: 8px 10px;
    margin-bottom: 0;
    border: 1px solid var(--kg-border);
    border-radius: 8px;
    font-size: 14px;
    background: #12151c;
    color: #f3f4f6;
  }}
  .controls select option {{
    background: #12151c;
    color: #f3f4f6;
  }}
</style>
</head>
<body>
<div id="graph"></div>

<div class="controls">
  <select id="category-filter" aria-label="Filter by Category">
    <option value="">All Categories</option>
    {filter_options_html}
  </select>
</div>

<div class="tooltip" id="tooltip"></div>

<script>
  // Data from Python
  const nodesData = {nodes_js};
  const linksData = {links_js};
  
  console.log('Graph initialized with', nodesData.length, 'nodes and', linksData.length, 'links');
  
  const width = document.getElementById('graph').clientWidth;
  const height = document.getElementById('graph').clientHeight;
  
  const svg = d3.select('#graph').append('svg')
    .attr('width', width)
    .attr('height', height)
    .call(d3.zoom().scaleExtent([0.1, 4]).on('zoom', (event) => {{
      g.attr('transform', event.transform);
    }}));
  
  const g = svg.append('g');

  // Tooltip
  const tooltip = d3.select('#tooltip');
  
  // Simulation setup
  const simulation = d3.forceSimulation(nodesData)
    .force('link', d3.forceLink(linksData).id(d => d.id).distance(d => 100 - (d.strength * 50)))
    .force('charge', d3.forceManyBody().strength(d => d.group === 'category' ? -800 : -300))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collision', d3.forceCollide().radius(d => d.size + 8))
    .on('tick', ticked);
  
  // Draw links
  let link = g.append('g')
    .attr('class', 'links')
    .selectAll('line')
    .data(linksData)
    .join('line')
    .attr('class', d => `link ${{d.strength >= 0.6 ? 'link-strong' : 'link-soft'}}`)
    .attr('stroke', d => d.color || '#d1d5db')
    .attr('stroke-opacity', d => typeof d.opacity === 'number' ? d.opacity : 0.6)
    .attr('stroke-width', d => 1.5 + (d.strength || 0.4) * 2);
  
  // Draw nodes
  let node = g.append('g')
    .selectAll('circle')
    .data(nodesData)
    .join('circle')
    .attr('class', d => `node ${{d.group === 'category' ? 'node-category' : 'node-variable'}}`)
    .attr('r', d => d.size)
    .attr('fill', d => d.color)
    .call(drag(simulation));
  
  // Labels
  let label = g.append('g')
    .selectAll('text')
    .data(nodesData)
    .join('text')
    .attr('class', d => `label ${{d.group === 'category' ? 'label-category' : ''}}`)
    .attr('text-anchor', 'middle')
    .attr('dy', d => d.size + (d.group === 'category' ? 10 : 8))
    .text(d => d.id);
  
  // Filter functionality
  document.getElementById('category-filter').addEventListener('change', (e) => {{
    const selectedCategory = e.target.value;
    
    if (selectedCategory === '') {{
      // Show all
      node.style('opacity', 1);
      label.style('opacity', 1);
      link.style('opacity', 0.6);
    }} else {{
      // Filter by category
      node.style('opacity', d => {{
        if (d.group === 'category') {{
          return d.id === selectedCategory ? 1 : 0.1;
        }} else {{
          return d.group === selectedCategory ? 1 : 0.1;
        }}
      }});
      
      label.style('opacity', d => {{
        if (d.group === 'category') {{
          return d.id === selectedCategory ? 1 : 0.1;
        }} else {{
          return d.group === selectedCategory ? 1 : 0.1;
        }}
      }});
      
      link.style('opacity', l => {{
        const sourceCat = nodesData.find(n => (n.id === l.source.id || n.id === l.source));
        const targetCat = nodesData.find(n => (n.id === l.target.id || n.id === l.target));
        if (sourceCat && targetCat) {{
          const sourceMatch = sourceCat.group === selectedCategory || sourceCat.id === selectedCategory;
          const targetMatch = targetCat.group === selectedCategory || targetCat.id === selectedCategory;
          return (sourceMatch && targetMatch) ? 0.6 : 0.05;
        }}
        return 0.05;
      }});
    }}
  }});
  
  // Reset button functionality
  
  // Hover interactions
  node.on('mouseover', (event, d) => {{
    // Highlight connected nodes and links
    const connectedNodes = new Set();
    linksData.forEach(l => {{
      if (l.source.id === d.id || l.source === d.id) connectedNodes.add(l.target.id || l.target);
      if (l.target.id === d.id || l.target === d.id) connectedNodes.add(l.source.id || l.source);
    }});
    connectedNodes.add(d.id);
  
    node.style('opacity', n => connectedNodes.has(n.id) ? 1 : 0.2);
    label.style('opacity', n => connectedNodes.has(n.id) ? 1 : 0.2);
    link.style('stroke-opacity', l => 
      l.source.id === d.id || l.source === d.id || l.target.id === d.id || l.target === d.id ? 1 : 0.1);
    link.classed('highlighted', l =>
      l.source.id === d.id || l.source === d.id || l.target.id === d.id || l.target === d.id);
  
    // Show tooltip
    tooltip.style('opacity', 1)
      .html(`<strong>${{d.id}}</strong><br>Group: ${{d.group}}`)
      .style('left', (event.pageX + 15) + 'px')
      .style('top', (event.pageY - 28) + 'px');
  }})
  .on('mouseout', () => {{
    node.style('opacity', 1);
    label.style('opacity', 1);
    link.style('stroke-opacity', 0.6);
    link.classed('highlighted', false);
    tooltip.style('opacity', 0);
  }});
  
  // Drag functions
  function drag(simulation) {{
    function dragstarted(event, d) {{
      if (!event.active) simulation.alphaTarget(0.3).restart();
      d.fx = d.x;
      d.fy = d.y;
    }}
    function dragged(event, d) {{
      d.fx = event.x;
      d.fy = event.y;
    }}
    function dragended(event, d) {{
      if (!event.active) simulation.alphaTarget(0);
      // Keep category nodes fixed after drag, others free
      if (d.group !== 'category') {{
        d.fx = null;
        d.fy = null;
      }}
    }}
    return d3.drag()
      .on('start', dragstarted)
      .on('drag', dragged)
      .on('end', dragended);
  }}
  
  // Simulation tick update
  function ticked() {{
    link
      .attr('x1', d => d.source.x)
      .attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x)
      .attr('y2', d => d.target.y);
  
    node
      .attr('cx', d => d.x)
      .attr('cy', d => d.y);
  
    label
      .attr('x', d => d.x)
      .attr('y', d => d.y + d.size + (d.group === 'category' ? 10 : 8));
  }}
  
  // Responsive resize
  window.addEventListener('resize', () => {{
    const w = document.getElementById('graph').clientWidth;
    const h = document.getElementById('graph').clientHeight;
    svg.attr('width', w).attr('height', h);
    simulation.force('center', d3.forceCenter(w / 2, h / 2));
    simulation.alpha(1).restart();
  }});
</script>
</body>
</html>"""
    
    return html_template

class LLMService:
    def __init__(self):
        self.logger = get_logger(__name__)

        self.chat_config = settings.CHAT_LLM_CONFIG
        self.embedding_config = settings.EMBEDDING_LLM_CONFIG
        self.kg_config = settings.KG_LLM_CONFIG
        
        self.chat_ready = self.chat_config.is_ready()
        self.kg_ready = self.kg_config.is_ready()
        self.embedding_ready = self.embedding_config.is_ready()

        if self.chat_ready:
            chat_reasoning = self.chat_config.defaults.get("reasoning_effort")
            self.logger.info(
                "Chat LLM configured for provider=%s model=%s reasoning_effort=%s",
                self.chat_config.provider,
                self.chat_config.model,
                chat_reasoning,
            )
        else:
            self.logger.warning(
                "Chat LLM configuration missing. Set LLM_CHAT_MODEL or LLM_MODEL to enable chat completions."
            )

        if self.kg_ready:
            kg_reasoning = self.kg_config.defaults.get("reasoning_effort")
            self.logger.info(
                "Knowledge graph LLM configured for provider=%s model=%s reasoning_effort=%s",
                self.kg_config.provider,
                self.kg_config.model,
                kg_reasoning,
            )
        else:
            self.logger.warning(
                "Knowledge graph LLM configuration missing. Set KG_MODEL or KG_PROVIDER to enable KG generation."
            )

        if self.embedding_ready:
            self.logger.info(
                "Embedding LLM configured for provider=%s model=%s",
                self.embedding_config.provider,
                self.embedding_config.model,
            )

        self.logger.info("LLMService initialized using litellm")

    def _resolve_usage_config(
        self,
        usage_key: str,
        env_config: LitellmUsageConfig,
        default_model_id: str,
        model_id_override: Optional[str] = None,
    ) -> Tuple[LitellmUsageConfig, str, str]:
        if env_override_present(usage_key):
            return env_config, "env", env_config.model

        def _has_gateway_id(mapping_entry: Optional[Dict[str, Any]]) -> bool:
            return bool(mapping_entry and mapping_entry.get("gateway_model_id"))

        gateway_on = gateway_enabled()

        if model_id_override:
            mapping = get_model_config(usage_key, model_id_override)
            if mapping and gateway_on and not _has_gateway_id(mapping):
                self.logger.warning(
                    "Gateway mode is on but model '%s' (%s) has no gateway_model_id; "
                    "falling back to default '%s'.",
                    model_id_override, usage_key, default_model_id,
                )
                mapping = None
            if mapping:
                config = LitellmUsageConfig.from_mapping(
                    name=usage_key,
                    usage_type=usage_key,
                    model_id=model_id_override,
                    mapping=mapping,
                    model_normalizer=_normalize_bedrock_model,
                )
                return config, "selection", model_id_override

        # Legacy header-based selection has been removed; routing now happens
        # via tag-based contexts (see app.core.llm_routing). This resolver is
        # only used for embeddings and as a safety net for env fallbacks.
        selection: Dict[str, str] = {}
        selected_model_id = selection.get(usage_key) or default_model_id

        mapping = get_model_config(usage_key, selected_model_id)
        if gateway_on and mapping and not _has_gateway_id(mapping):
            self.logger.warning(
                "Gateway mode is on but selected model '%s' (%s) has no gateway_model_id; "
                "falling back to default '%s'.",
                selected_model_id, usage_key, default_model_id,
            )
            mapping = None
        if mapping is None and selected_model_id != default_model_id:
            selected_model_id = default_model_id
            mapping = get_model_config(usage_key, selected_model_id)
            if gateway_on and mapping and not _has_gateway_id(mapping):
                self.logger.warning(
                    "Default model '%s' for %s has no gateway_model_id; request will fail "
                    "unless LLM_USE_GATEWAY is unset or the mapping is updated.",
                    selected_model_id, usage_key,
                )

        if mapping is None:
            return env_config, "env", env_config.model

        source = "selection" if selection.get(usage_key) else "default"
        config = LitellmUsageConfig.from_mapping(
            name=usage_key,
            usage_type=usage_key,
            model_id=selected_model_id,
            mapping=mapping,
            model_normalizer=_normalize_bedrock_model,
        )
        return config, source, selected_model_id

    def _resolve_chat_config(self) -> Tuple[LitellmUsageConfig, str, str]:
        config, source, model_id = self._resolve_usage_config(
            "chat",
            settings.CHAT_LLM_CONFIG,
            DEFAULT_CHAT_MODEL,
        )
        self.chat_config = config
        self.chat_ready = config.is_ready()
        return config, source, model_id

    def _resolve_kg_config(
        self,
        model_id_override: Optional[str] = None,
    ) -> Tuple[LitellmUsageConfig, str, str]:
        config, source, model_id = self._resolve_usage_config(
            "knowledge_graph",
            settings.KG_LLM_CONFIG,
            DEFAULT_KG_MODEL,
            model_id_override=model_id_override,
        )
        self.kg_config = config
        self.kg_ready = config.is_ready()
        return config, source, model_id

    def _resolve_embedding_config(self) -> Tuple[LitellmUsageConfig, str, str]:
        config, source, model_id = self._resolve_usage_config(
            "embedding",
            settings.EMBEDDING_LLM_CONFIG,
            DEFAULT_EMBEDDING_MODEL,
        )
        self.embedding_config = config
        self.embedding_ready = config.is_ready()
        return config, source, model_id

    def get_resolved_config_summary(self) -> Dict[str, Dict[str, Any]]:
        chat_cfg, chat_source, _ = self._resolve_chat_config()
        kg_cfg, kg_source, _ = self._resolve_kg_config()
        emb_cfg, emb_source, _ = self._resolve_embedding_config()
        return {
            "chat": {
                "provider": chat_cfg.provider,
                "model": chat_cfg.model,
                "source": chat_source,
            },
            "knowledge_graph": {
                "provider": kg_cfg.provider,
                "model": kg_cfg.model,
                "source": kg_source,
            },
            "embedding": {
                "provider": emb_cfg.provider,
                "model": emb_cfg.model,
                "source": emb_source,
            },
        }

    def is_embedding_ready(self) -> bool:
        _, _, _ = self._resolve_embedding_config()
        return bool(self.embedding_ready)

    def get_kg_cache_key(self, dataset_id: Optional[str], model_id_override: Optional[str] = None) -> str:
        _, _, model_id = self._resolve_kg_config(model_id_override=model_id_override)
        return _kg_cache_key(dataset_id, model_id)

    def _emit_llm_call_log(
        self,
        *,
        usage: str,
        config: LitellmUsageConfig,
        duration_ms: float,
        success: bool,
        error_type: Optional[str],
        request_kwargs: Optional[Dict[str, Any]] = None,
        response: Any = None,
        embedding_inputs: Optional[List[str]] = None,
        context: Optional[str] = None,
        model_id: Optional[str] = None,
        attempts: Optional[int] = None,
    ) -> None:
        extra: Dict[str, Any] = {
            "event": "llm_call",
            "log_category": "llm",
            "integration": "litellm",
            "usage": usage,
            "model": model_id or config.model,
            "provider": config.provider,
            "duration_ms": duration_ms,
            "success": success,
            "outcome": "success" if success else "failure",
        }
        if context is not None:
            extra["context"] = context
        if attempts is not None:
            extra["attempts"] = attempts
        if error_type:
            extra["error_type"] = error_type

        if usage == "embedding":
            if embedding_inputs is not None:
                extra["embedding_count"] = len(embedding_inputs)
                extra["input_chars"] = sum(len(s) for s in embedding_inputs)
            if settings.LOG_PROMPT_HASH and embedding_inputs:
                try:
                    extra["input_hash_sha256"] = hash_for_log(json.dumps(embedding_inputs, default=str))
                except Exception:
                    pass
            uemb = _usage_tokens_from_response(response)
            extra.update(uemb)
        else:
            msgs = (request_kwargs or {}).get("messages")
            if msgs is not None and isinstance(msgs, list):
                extra["message_count"] = len(msgs)
                extra["prompt_chars"] = _safe_message_char_count(msgs)
            elif msgs is not None:
                extra["message_count"] = 0
                extra["prompt_chars"] = 0
            if settings.LOG_PROMPT_HASH and msgs:
                try:
                    extra["prompt_hash_sha256"] = hash_for_log(json.dumps(msgs, default=str, sort_keys=True))
                except Exception:
                    pass
            if response is not None:
                fr = _finish_reason_from_response(response)
                if fr is not None:
                    extra["finish_reason"] = fr
                rc = _response_content_chars(response)
                if rc is not None:
                    extra["response_chars"] = rc
            extra.update(_usage_tokens_from_response(response))

        self.logger.info("llm_call", extra=extra)

    # ------------------------------------------------------------------
    # Tag-based routing with fallback
    # ------------------------------------------------------------------

    @staticmethod
    def _response_is_empty(response: Any) -> bool:
        """Treat a response as unusable when it yields no content and no
        tool calls. Downstream parsers take it from here, any parse error
        will also naturally bubble into ``execute_with_fallback``.
        """
        if response is None:
            return True
        choices = getattr(response, "choices", None) or []
        if not choices:
            return True
        for choice in choices:
            msg = getattr(choice, "message", None)
            if msg is None and isinstance(choice, dict):
                msg = choice.get("message")
            if msg is None:
                continue
            content = getattr(msg, "content", None)
            if content is None and isinstance(msg, dict):
                content = msg.get("content")
            tool_calls = getattr(msg, "tool_calls", None)
            if tool_calls is None and isinstance(msg, dict):
                tool_calls = msg.get("tool_calls")
            if tool_calls:
                return False
            if content and str(content).strip():
                return False
        return True

    def _build_config_for(self, usage_key: str, model_id: str) -> Optional[LitellmUsageConfig]:
        mapping = get_model_config(usage_key, model_id)
        if not mapping:
            return None
        return LitellmUsageConfig.from_mapping(
            name=usage_key,
            usage_type=usage_key,
            model_id=model_id,
            mapping=mapping,
            model_normalizer=_normalize_bedrock_model,
        )

    def _execute_with_fallback(
        self,
        context: str,
        usage_key: str,
        overrides: Dict[str, Any],
    ) -> Tuple[Any, str]:
        """Iterate the tag-based candidate list for ``context`` and call
        litellm.completion until one returns a usable response.

        - On exception: log WARN on ``midas.llm.router``, move to the next.
        - On empty/unparseable response: same.
        - On success: log INFO with ``status=success`` and return
          ``(response, model_id)``.

        If every candidate fails a ``RuntimeError`` is raised (preserves the
        last exception as ``__cause__``).
        """
        gw_on = bool(gateway_enabled())
        candidates = candidates_for(context)
        t0 = time.perf_counter()
        if not candidates:
            # Extremely defensive: if no candidates resolved, fall back to the
            # existing env-based config so the call can still attempt once.
            config = (
                settings.KG_LLM_CONFIG if usage_key == "knowledge_graph"
                else settings.CHAT_LLM_CONFIG
            )
            if not config.is_ready():
                raise RuntimeError(
                    f"No routable candidates for context={context} and no env fallback configured"
                )
            settings.apply_provider_environment(config.provider)
            request_kwargs = _build_litellm_kwargs(config, overrides)
            self._sanitize_sampling_params(request_kwargs)
            env_response: Any = None
            env_err_type: Optional[str] = None
            try:
                env_response = completion(**request_kwargs)
                _router_logger.info(
                    "context=%s attempt=env model=%s gateway=%s status=success source=env-fallback",
                    context, config.model, gw_on,
                )
                return env_response, config.model
            except Exception as exc:
                env_err_type = type(exc).__name__
                raise
            finally:
                self._emit_llm_call_log(
                    usage=usage_key,
                    config=config,
                    duration_ms=round((time.perf_counter() - t0) * 1000, 2),
                    success=env_err_type is None,
                    error_type=env_err_type,
                    request_kwargs=request_kwargs,
                    response=env_response,
                    context=context,
                    model_id=config.model,
                    attempts=1,
                )

        last_exc: Optional[BaseException] = None
        last_cfg: Optional[LitellmUsageConfig] = None
        last_model_id: Optional[str] = None
        last_request_kwargs: Optional[Dict[str, Any]] = None
        attempts_made = 0
        for attempt, model_id in enumerate(candidates, start=1):
            cfg = self._build_config_for(usage_key, model_id)
            if cfg is None:
                _router_logger.warning(
                    "context=%s attempt=%d model=%s status=skipped reason=missing_mapping",
                    context, attempt, model_id,
                )
                continue
            attempts_made += 1
            last_cfg = cfg
            last_model_id = model_id
            try:
                settings.apply_provider_environment(cfg.provider)
                request_kwargs = _build_litellm_kwargs(cfg, overrides)
                last_request_kwargs = request_kwargs
                self._sanitize_sampling_params(request_kwargs)
                response = completion(**request_kwargs)
                if self._response_is_empty(response):
                    raise RuntimeError("empty response (no content, no tool calls)")
                _router_logger.info(
                    "context=%s attempt=%d model=%s gateway=%s status=success",
                    context, attempt, model_id, gw_on,
                )
                if usage_key == "chat":
                    self.chat_config = cfg
                    self.chat_ready = cfg.is_ready()
                elif usage_key == "knowledge_graph":
                    self.kg_config = cfg
                    self.kg_ready = cfg.is_ready()
                self._emit_llm_call_log(
                    usage=usage_key,
                    config=cfg,
                    duration_ms=round((time.perf_counter() - t0) * 1000, 2),
                    success=True,
                    error_type=None,
                    request_kwargs=request_kwargs,
                    response=response,
                    context=context,
                    model_id=model_id,
                    attempts=attempts_made,
                )
                return response, model_id
            except Exception as exc:
                last_exc = exc
                err_msg = str(exc)
                if len(err_msg) > 400:
                    err_msg = err_msg[:400] + "..."
                _router_logger.warning(
                    "context=%s attempt=%d model=%s status=failed error=%s:%s; trying next",
                    context, attempt, model_id, type(exc).__name__, err_msg,
                )
                continue

        if last_cfg is not None:
            self._emit_llm_call_log(
                usage=usage_key,
                config=last_cfg,
                duration_ms=round((time.perf_counter() - t0) * 1000, 2),
                success=False,
                error_type=type(last_exc).__name__ if last_exc else "NoCandidateMapping",
                request_kwargs=last_request_kwargs,
                response=None,
                context=context,
                model_id=last_model_id,
                attempts=attempts_made,
            )
        raise RuntimeError(
            f"All {len(candidates)} candidate models failed for context={context}"
        ) from last_exc

    def _call_chat_completion(self, *, context: str = "default_chat", **overrides) -> Any:
        response, _ = self._execute_with_fallback(context, "chat", overrides)
        return response

    def _call_kg_completion(self, *, context: str = "knowledge_graph", **overrides) -> Any:
        response, _ = self._execute_with_fallback(context, "knowledge_graph", overrides)
        return response

    def _format_message_content(self, content: Any) -> str:
        if isinstance(content, (dict, list)):
            try:
                content = json.dumps(content)
            except Exception:
                content = str(content)
        elif isinstance(content, BaseModel):
            try:
                content = content.json()
            except Exception:
                try:
                    content = json.dumps(content.dict(), default=str)
                except Exception:
                    content = str(content)
        if content is None:
            return ""
        return str(content).strip()

    def _strip_code_fences(self, text: str) -> str:
        """Remove markdown code fences such as ```json``` that can wrap Bedrock output."""
        if not text:
            return ""

        def _unwrap(match: re.Match[str]) -> str:
            inner = match.group(1) or ""
            return inner.strip()

        cleaned = re.sub(
            r"```(?:json)?\s*(.*?)\s*```",
            _unwrap,
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        return cleaned.strip()

    def _extract_response_text(self, response: Any) -> str:
        """Return a normalized string from a litellm completion response."""
        try:
            message = response.choices[0].message
            raw_content = getattr(message, "content", "")
        except Exception:
            return ""

        formatted = self._format_message_content(raw_content)
        return self._strip_code_fences(formatted)

    def _sanitize_history_for_new_user(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Keep alternating roles and drop trailing user before appending a new user prompt."""
        sanitized: List[Dict[str, Any]] = []
        for message in messages:
            if not isinstance(message, dict):
                continue
            role = message.get("role", "")
            if not isinstance(role, str) or not role.strip():
                continue
            normalized_role = role.strip().lower()
            if normalized_role not in {"user", "assistant"}:
                continue
            if sanitized and sanitized[-1].get("role", "").strip().lower() == normalized_role:
                continue
            sanitized.append(message)

        while sanitized and sanitized[-1].get("role", "").strip().lower() == "user":
            sanitized.pop()

        return sanitized

    def _normalize_structured_response(self, response: Any) -> Any:
        """Return structured data (dict/list) when the message contains it."""
        try:
            message = response.choices[0].message
            raw_content = getattr(message, "content", "")
        except Exception:
            return self._extract_response_text(response)

        if isinstance(raw_content, BaseModel):
            return raw_content.dict()

        if isinstance(raw_content, (dict, list)):
            return raw_content

        text = self._extract_response_text(response)
        if text:
            try:
                return json.loads(text)
            except Exception:
                return text

        return raw_content

    def _safe_json_load(self, content: str) -> Any:
        """Load JSON text, raising a clear error when there is nothing to parse."""
        trimmed = (content or "").strip()
        if not trimmed:
            raise ValueError("Response content is empty")
        return json.loads(trimmed)

    def _guess_dataset_type_from_text(self, text: str) -> str:
        normalized = (text or "").lower()
        if not normalized:
            return "others"

        heuristics = [
            ("classification", ["classification", "categorical", "classify", "label"]),
            ("regression", ["regression", "continuous", "predict number", "predict amount"]),
            ("time_series", ["time_series", "time series", "temporal", "forecast", "timestamp"]),
        ]
        for dataset_type, keywords in heuristics:
            if any(keyword in normalized for keyword in keywords):
                return dataset_type
        return "others"

    def _build_dataset_type_fallback(self, content: str) -> Dict[str, Any]:
        text = (content or "").strip()
        dataset_type = self._guess_dataset_type_from_text(text)
        confidence = 0.65 if dataset_type != "others" else 0.45
        return {
            "dataset_type": dataset_type,
            "confidence": confidence,
            "reasoning": text or "Unable to parse structured response; returned raw text instead.",
            "characteristics": [],
            "recommendations": []
        }

    def _build_variable_classification_fallback(self, content: str) -> Dict[str, Any]:
        text = (content or "").strip()
        return {
            "dataset_summary": text or "No structured response received.",
            "variables": [],
            "recommendations": [text or "Unable to parse structured response."],
            "quality_score": 0.0
        }

    def _build_kg_fallback(self, columns: List[str], reason: str) -> Dict[str, Any]:
        fallback_category = "Automated Fallback"
        nodes = [
            {
                "id": fallback_category,
                "group": "category",
                "size": 25,
                "color": "#4E79A7"
            }
        ]
        links = []
        for column in columns:
            node = {
                "id": column,
                "group": fallback_category,
                "size": 8,
                "color": "#B0C4DE"
            }
            nodes.append(node)
            links.append({
                "source": column,
                "target": fallback_category,
                "strength": 1.0
            })
        categories = [{
            "name": fallback_category,
            "color": "#4E79A7"
        }]
        return {
            "nodes": nodes,
            "links": links,
            "categories": categories,
            "algorithm_explanation": reason or "LLM did not return structured JSON; falling back to placeholder graph.",
            "relationship_mapping": "Fallback connections between variables and a placeholder category.",
            "usage_instructions": "Graph nodes are placeholders because the model output was incomplete."
        }

    def _check_credentials(self) -> bool:
        """Ensure chat LLM configuration is present"""
        config, _, _ = self._resolve_chat_config()
        if not config.is_ready():
            self.logger.warning("Chat LLM configuration is missing or incomplete")
            return False
        return True

    def _sanitize_sampling_params(self, kwargs: Dict[str, Any]) -> None:
        """
        Drop one of 'temperature' or 'top_p' if both are set to avoid provider errors
        for models that do not allow both simultaneously.
        """
        if "temperature" in kwargs and "top_p" in kwargs:
            self.logger.warning(
                "Both 'temperature' and 'top_p' are set; dropping 'top_p' to avoid invalid_request_error"
            )
            kwargs.pop("top_p", None)

    def get_response(self, sys_prompt: str, prompt: str, messages: List[Dict[str, Any]], context: str = "default_chat") -> str:
        """Get structured response from the configured LLM"""
        if not self._check_credentials():
            return "LLM chat configuration is missing. Please configure LLM_MODEL and provider credentials."
        self.logger.debug(f"Getting structured response with {len(messages)} messages")

        try:
            history = self._sanitize_history_for_new_user(messages)
            formatted_messages = [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "text",
                            "text": sys_prompt
                        }
                    ]
                }
            ] + history + [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt}
                    ]
                }
            ]

            response = self._call_chat_completion(
                context=context,
                messages=formatted_messages,
                temperature=0.0,
                response_format=Plan,
                max_tokens=10000
            )

            content = self._extract_response_text(response)
            self.logger.debug("Structured response generated successfully")
            return content

        except Exception as e:
            self.logger.error(f"Failed to get structured response: {str(e)}")
            raise
    
    def get_response_route(self, prompt: str, messages: List[Dict[str, Any]], context: str = "model_training") -> str:
        """Get routing response from the configured LLM"""
        if not self._check_credentials():
            return "LLM chat configuration is missing. Please configure provider credentials."
        self.logger.debug("Getting routing response")

        try:
            history = self._sanitize_history_for_new_user(messages)
            formatted_messages = history + [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt}
                    ]
                }
            ]

            response = self._call_chat_completion(
                context=context,
                messages=formatted_messages,
                temperature=0.1
            )

            content = self._extract_response_text(response)
            self.logger.debug("Routing response generated successfully")
            return content

        except Exception as e:
            self.logger.error(f"Failed to get routing response: {str(e)}")
            raise
    
    # Providers that do not support Pydantic/structured response_format.
    # For these we fall back to a JSON-in-prompt approach instead.
    _UNSTRUCTURED_PROVIDERS = {"bedrock", "azure_ai", "azure/responses"}

    def _supports_response_format(self, context: str | None = None) -> bool:
        """Return True only when the first routable candidate for the given
        ``context`` is served by a provider that supports structured output.
        Falls back to the env-configured chat provider when no context is
        supplied or no candidates resolve.
        """
        provider = None
        if context:
            cands = candidates_for(context)
            for model_id in cands:
                cfg = self._build_config_for(
                    "knowledge_graph" if context == "knowledge_graph" else "chat",
                    model_id,
                )
                if cfg is not None:
                    provider = cfg.provider
                    break
        if provider is None:
            config, _, _ = self._resolve_chat_config()
            provider = config.provider
        return provider not in self._UNSTRUCTURED_PROVIDERS

    def get_guardrail_response(self, prompt: str) -> str:
        """
        Lightweight LLM call used exclusively by the guardrail layer.
        Returns raw plain text (expected to be YES or NO).
        Never passes response_format so it works on every provider.
        """
        if not self._check_credentials():
            return "NO"
        try:
            formatted_messages = [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": prompt}]
                }
            ]
            response = self._call_chat_completion(
                context="guardrail",
                messages=formatted_messages,
                temperature=0.0,
            )
            return self._extract_response_text(response)
        except Exception as e:
            self.logger.warning(f"get_guardrail_response failed: {e}")
            raise

    def get_data_response(self, prompt: str, messages: List[Dict[str, Any]], context: str = "default_chat") -> str:
        """Get data analysis response from the configured LLM"""
        if not self._check_credentials():
            return "LLM chat configuration is missing. Please configure provider credentials."
        self.logger.debug(f"Getting data response with {len(messages)} messages")

        try:
            history = self._sanitize_history_for_new_user(messages)
            formatted_messages = history + [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ]

            if self._supports_response_format(context):
                response = self._call_chat_completion(
                    context=context,
                    messages=formatted_messages,
                    temperature=0.1,
                    response_format=DataResponse
                )
            else:
                # Providers that don't support structured output: ask the model
                # to return the JSON schema inline via the prompt instead.
                json_instruction = (
                    "\n\nIMPORTANT: You MUST respond with ONLY a valid JSON object "
                    "matching this exact schema - no markdown fences, no extra text:\n"
                    '{"response": "<explanation text>", '
                    '"code": "<python code string>", '
                    '"suggestion": ["<tip 1>", "<tip 2>", "<tip 3>"]}'
                )
                formatted_messages[-1]["content"][0]["text"] += json_instruction
                response = self._call_chat_completion(
                    context=context,
                    messages=formatted_messages,
                    temperature=0.1,
                )

            content = self._extract_response_text(response)
            self.logger.debug("Data response generated successfully")
            return content

        except Exception as e:
            self.logger.error(f"Failed to get data response: {str(e)}")
            raise

    # ---------- Unified Insight Generation ----------
    def get_insight(self, insight_type: str, sys_prompt: str, prompt: str, messages: List[Dict[str, Any]], context: str = "data_insights") -> List[str]:
        """
        Unified method for generating insights of any type.

        Args:
            insight_type: Type of insight ('bivariate', 'correlation', 'vif', 'iv', 'correlation_matrix', 'correlation_ratio')
            sys_prompt: System prompt for the LLM
            prompt: User prompt with analysis data
            messages: Chat history for context

        Returns:
            List of insight strings
        """
        if not self._check_credentials():
            return ["LLM chat configuration is missing. Please configure provider credentials."]
        try:
            history = self._sanitize_history_for_new_user(messages)
            if self.chat_config.provider == "bedrock":
                history = [
                    msg for msg in history
                    if msg.get("role", "").strip().lower() in {"user", "assistant"}
                ]
                while history and history[0].get("role", "").strip().lower() == "assistant":
                    history.pop(0)
                if history:
                    last_role = history[-1].get("role", "").strip().lower()
                else:
                    last_role = ""
                if history and last_role != "assistant":
                    history = history + [{
                        "role": "assistant",
                        "content": [{"type": "text", "text": "Context acknowledged."}]
                    }]
            formatted_messages = [
                {"role": "system", "content": [{"type": "text", "text": sys_prompt}]}
            ] + history + [
                {"role": "user", "content": [{"type": "text", "text": prompt}]}
            ]

            response = self._call_chat_completion(
                context=context,
                messages=formatted_messages,
                temperature=0.1,
                response_format=GenericInsightResponse
            )

            content = self._extract_response_text(response)
            try:
                parsed = json.loads(content)
                insights = parsed.get("insights", [])
                if isinstance(insights, list) and insights:
                    return [str(x) for x in insights if str(x).strip()]

                specific_key = INSIGHT_TYPE_MAPPING.get(insight_type)
                if specific_key:
                    insights = parsed.get(specific_key, [])
                    if isinstance(insights, list):
                        return [str(x) for x in insights if str(x).strip()]
            except Exception:
                pass
            return []

        except Exception as e:
            self.logger.warning(f"get_insight({insight_type}) failed: {e}")
            return []

    def get_column_distribution_insights(
        self, 
        column_name: str,
        column_type: str,
        distribution: Dict[str, int],
        statistics: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """
        Generate AI-based insights for a column's distribution.
        
        Args:
            column_name: Name of the column
            column_type: Type of column (Numerical/Categorical)
            distribution: Distribution data {value: count}
            statistics: Statistics including total_count, valid_count, missing_count, unique_count
            
        Returns:
            List of insight dictionaries with title, description, and type
        """
        if not self._check_credentials():
            return [{"title": "Configuration Error", "description": "LLM configuration is missing.", "type": "warning"}]
        
        try:
            # Calculate additional statistics for context
            total_count = statistics.get('valid_count', sum(distribution.values()))
            missing_count = statistics.get('missing_count', 0)
            unique_count = len(distribution)
            
            # Sort distribution
            sorted_dist = sorted(distribution.items(), key=lambda x: x[1], reverse=True)
            top_5 = sorted_dist[:5]
            bottom_3 = sorted_dist[-3:] if len(sorted_dist) > 3 else sorted_dist
            
            # Calculate percentages for top categories
            top_5_with_pct = [(k, v, (v/total_count*100) if total_count > 0 else 0) for k, v in top_5]
            
            # Build context string
            distribution_summary = "\n".join([f"  - '{k}': {v:,} records ({pct:.1f}%)" for k, v, pct in top_5_with_pct])
            if len(sorted_dist) > 5:
                distribution_summary += f"\n  ... and {len(sorted_dist) - 5} more categories"
            
            sys_prompt = """You are an expert data scientist analyzing column distributions for credit risk modeling and data analysis.
Generate exactly 7-10 meaningful, actionable insights about the column distribution.

Each insight must be a JSON object with:
- "title": Short title (3-6 words)
- "description": Detailed description (1-2 sentences, be specific with numbers)
- "type": One of "info", "warning", or "success"

Types guidance:
- "warning": Data quality issues, imbalances, potential problems for modeling
- "success": Good patterns, well-distributed data, positive indicators
- "info": Neutral observations, statistical facts, recommendations

Focus on:
1. Distribution patterns (skewness, uniformity, concentration)
2. Data quality implications (missing values, rare categories, outliers)
3. Modeling recommendations (encoding strategies, transformations needed)
4. Business/domain interpretation based on column name
5. Statistical observations (quartiles for numerical, cardinality for categorical)
6. Potential issues for machine learning models
7. Actionable recommendations

Be specific with numbers and percentages. Avoid generic statements."""

            prompt = f"""Analyze this column distribution and generate 7-10 insights:

COLUMN INFORMATION:
- Name: {column_name}
- Type: {column_type}
- Total Records: {total_count:,}
- Missing Values: {missing_count:,} ({(missing_count/(total_count+missing_count)*100) if (total_count+missing_count) > 0 else 0:.1f}%)
- Unique Values/Bins: {unique_count}

TOP DISTRIBUTION:
{distribution_summary}

BOTTOM CATEGORIES (least frequent):
{chr(10).join([f"  - '{k}': {v:,} records" for k, v in bottom_3])}

Generate insights as a JSON array. Focus on actionable, data-science relevant observations."""

            formatted_messages = [
                {"role": "system", "content": [{"type": "text", "text": sys_prompt}]},
                {"role": "user", "content": [{"type": "text", "text": prompt}]}
            ]

            response = self._call_chat_completion(
                context="data_insights",
                messages=formatted_messages,
                temperature=0.3
            )

            content = self._extract_response_text(response)
            
            # Parse JSON response
            try:
                # Try to extract JSON array from response
                import re
                json_match = re.search(r'\[[\s\S]*\]', content)
                if json_match:
                    insights = json.loads(json_match.group())
                    # Validate and clean insights
                    valid_insights = []
                    for insight in insights:
                        if isinstance(insight, dict) and 'title' in insight and 'description' in insight:
                            valid_insights.append({
                                "title": str(insight.get('title', '')),
                                "description": str(insight.get('description', '')),
                                "type": insight.get('type', 'info') if insight.get('type') in ['info', 'warning', 'success'] else 'info'
                            })
                    if valid_insights:
                        return valid_insights[:10]  # Limit to 10
            except json.JSONDecodeError:
                self.logger.warning("Failed to parse LLM response as JSON")
            
            # Fallback: return basic insights if LLM fails
            return self._get_fallback_column_insights(column_name, column_type, distribution, statistics)
            
        except Exception as e:
            self.logger.error(f"get_column_distribution_insights failed: {e}")
            return self._get_fallback_column_insights(column_name, column_type, distribution, statistics)
    
    def _get_fallback_column_insights(
        self,
        column_name: str,
        column_type: str,
        distribution: Dict[str, int],
        statistics: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """Generate comprehensive statistical insights as fallback when LLM fails."""
        insights = []
        total_count = statistics.get('valid_count', sum(distribution.values()))
        missing_count = statistics.get('missing_count', 0)
        unique_count = len(distribution)
        
        sorted_dist = sorted(distribution.items(), key=lambda x: x[1], reverse=True)
        top_category = sorted_dist[0] if sorted_dist else (None, 0)
        top_pct = (top_category[1] / total_count * 100) if total_count > 0 else 0
        bottom_category = sorted_dist[-1] if sorted_dist else (None, 0)
        bottom_pct = (bottom_category[1] / total_count * 100) if total_count > 0 else 0
        
        # Calculate top 3 concentration
        top_3_count = sum([v for _, v in sorted_dist[:3]]) if len(sorted_dist) >= 3 else sum([v for _, v in sorted_dist])
        top_3_pct = (top_3_count / total_count * 100) if total_count > 0 else 0
        
        # Insight 1: Distribution pattern
        if top_pct > 50:
            insights.append({
                "title": "Highly Skewed Distribution",
                "description": f"'{top_category[0]}' dominates with {top_pct:.1f}% of records. Consider rebalancing techniques like SMOTE or class weights for modeling.",
                "type": "warning"
            })
        elif top_pct < 15 and unique_count > 5:
            insights.append({
                "title": "Well-Balanced Distribution",
                "description": f"No single value exceeds {top_pct:.1f}%. Data is evenly distributed across {unique_count} categories, ideal for modeling.",
                "type": "success"
            })
        else:
            insights.append({
                "title": "Moderate Distribution",
                "description": f"Top value '{top_category[0]}' represents {top_pct:.1f}% of {total_count:,} records. Distribution is moderately balanced.",
                "type": "info"
            })
        
        # Insight 2: Missing data
        if missing_count > 0:
            missing_pct = (missing_count / (total_count + missing_count) * 100)
            if missing_pct > 20:
                insights.append({
                    "title": "High Missing Rate",
                    "description": f"{missing_count:,} records ({missing_pct:.1f}%) have missing values. Consider imputation or investigate data collection issues.",
                    "type": "warning"
                })
            else:
                insights.append({
                    "title": "Missing Values Present",
                    "description": f"{missing_count:,} records ({missing_pct:.1f}%) have missing values. Standard imputation techniques should suffice.",
                    "type": "info"
                })
        else:
            insights.append({
                "title": "Complete Data",
                "description": f"All {total_count:,} records have valid values. No missing data handling required.",
                "type": "success"
            })
        
        # Insight 3: Cardinality analysis
        if column_type == 'Categorical':
            if unique_count > 50:
                insights.append({
                    "title": "High Cardinality Warning",
                    "description": f"{unique_count} unique categories detected. Use target encoding, frequency encoding, or group rare categories to avoid dimensionality explosion.",
                    "type": "warning"
                })
            elif unique_count <= 2:
                insights.append({
                    "title": "Binary Variable",
                    "description": f"Column has {unique_count} unique values. Ideal for binary encoding or direct use in logistic regression.",
                    "type": "success"
                })
            elif unique_count <= 10:
                insights.append({
                    "title": "Low Cardinality",
                    "description": f"Only {unique_count} categories present. One-hot encoding is suitable without dimensionality concerns.",
                    "type": "success"
                })
            else:
                insights.append({
                    "title": "Moderate Cardinality",
                    "description": f"{unique_count} categories detected. Consider one-hot encoding or target encoding based on model requirements.",
                    "type": "info"
                })
        else:
            # Numerical column
            insights.append({
                "title": "Numerical Distribution",
                "description": f"Data spans {unique_count} bins/ranges. Consider normalization or standardization for distance-based models.",
                "type": "info"
            })
        
        # Insight 4: Concentration analysis
        if top_3_pct > 80:
            insights.append({
                "title": "Concentrated Distribution",
                "description": f"Top 3 values account for {top_3_pct:.1f}% of data. Remaining {unique_count - 3} categories are rare and may need special handling.",
                "type": "warning"
            })
        elif top_3_pct < 50 and unique_count > 5:
            insights.append({
                "title": "Diverse Distribution",
                "description": f"Top 3 values represent only {top_3_pct:.1f}% of data. Values are well-spread across {unique_count} categories.",
                "type": "success"
            })
        
        # Insight 5: Rare categories
        rare_categories = [k for k, v in sorted_dist if (v / total_count * 100) < 1] if total_count > 0 else []
        if len(rare_categories) > 0:
            insights.append({
                "title": "Rare Categories Detected",
                "description": f"{len(rare_categories)} categories appear in less than 1% of records. Consider grouping into 'Other' category for stable modeling.",
                "type": "warning"
            })
        
        # Insight 6: Potential outlier/data quality
        if bottom_category and bottom_category[1] == 1:
            insights.append({
                "title": "Singleton Values Found",
                "description": f"Category '{bottom_category[0]}' appears only once. Verify if this is valid data or a potential entry error.",
                "type": "warning"
            })
        
        # Insight 7: Encoding recommendation
        if column_type == 'Categorical':
            if unique_count == 2:
                insights.append({
                    "title": "Encoding Recommendation",
                    "description": "Use label encoding (0/1) for this binary variable. No need for one-hot encoding.",
                    "type": "info"
                })
            elif unique_count <= 10:
                insights.append({
                    "title": "Encoding Recommendation",
                    "description": f"One-hot encoding recommended for {unique_count} categories. Will create {unique_count} new features.",
                    "type": "info"
                })
            else:
                insights.append({
                    "title": "Encoding Recommendation",
                    "description": f"Target encoding or frequency encoding recommended for {unique_count} categories to avoid high dimensionality.",
                    "type": "info"
                })
        
        # Insight 8: Data volume
        insights.append({
            "title": "Data Volume Summary",
            "description": f"Column '{column_name}' contains {total_count:,} valid records distributed across {unique_count} unique values.",
            "type": "info"
        })
        
        # Insight 9: Second most common category
        if len(sorted_dist) >= 2:
            second_category = sorted_dist[1]
            second_pct = (second_category[1] / total_count * 100) if total_count > 0 else 0
            insights.append({
                "title": "Runner-up Category",
                "description": f"Second most common value is '{second_category[0]}' with {second_pct:.1f}% ({second_category[1]:,} records).",
                "type": "info"
            })
        
        # Insight 10: Feature importance hint
        if top_pct > 90:
            insights.append({
                "title": "Low Predictive Value",
                "description": f"With {top_pct:.1f}% concentration in one value, this feature may have limited predictive power. Consider excluding from model.",
                "type": "warning"
            })
        elif unique_count >= 5 and top_pct < 40:
            insights.append({
                "title": "Good Feature Candidate",
                "description": "Balanced distribution suggests this feature could provide good discriminatory power for classification tasks.",
                "type": "success"
            })
        
        return insights[:10]  # Ensure max 10 insights

    def get_dqs_recommendations(
        self,
        system_prompt: str,
        user_prompt: str
    ) -> List[Dict[str, str]]:
        """
        Generate AI-based recommendations for improving data quality based on DQS results.
        
        Args:
            system_prompt: System prompt with context and format instructions
            user_prompt: User prompt with DQS data details
            
        Returns:
            List of recommendation dictionaries with title, description, type, and priority
        """
        if not self._check_credentials():
            self.logger.warning("LLM credentials not configured, using fallback recommendations")
            return []
        
        try:
            formatted_messages = [
                {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
                {"role": "user", "content": [{"type": "text", "text": user_prompt}]}
            ]

            response = self._call_chat_completion(
                context="data_insights",
                messages=formatted_messages,
                temperature=0.4
            )

            content = self._extract_response_text(response)
            
            # Parse JSON response
            try:
                import re
                json_match = re.search(r'\[[\s\S]*\]', content)
                if json_match:
                    recommendations = json.loads(json_match.group())
                    
                    # Validate and sanitize each recommendation
                    valid_recommendations = []
                    for rec in recommendations:
                        if isinstance(rec, dict) and 'title' in rec and 'description' in rec:
                            valid_rec = {
                                "title": str(rec.get('title', 'Recommendation'))[:100],
                                "description": str(rec.get('description', ''))[:500],
                                "type": rec.get('type', 'info') if rec.get('type') in ['info', 'warning', 'success'] else 'info',
                                "priority": rec.get('priority', 'medium') if rec.get('priority') in ['high', 'medium', 'low'] else 'medium'
                            }
                            valid_recommendations.append(valid_rec)
                    
                    if valid_recommendations:
                        self.logger.info(f"Generated {len(valid_recommendations)} DQS recommendations via LLM")
                        return valid_recommendations[:3]  # Top 3 recommendations only
                    
            except json.JSONDecodeError as e:
                self.logger.warning(f"Failed to parse DQS recommendations JSON: {e}")
            
            # If JSON parsing fails, return empty list (fallback will be used)
            return []
            
        except Exception as e:
            self.logger.error(f"DQS recommendations generation failed: {e}")
            return []

    def get_variable_classification(self, dataset_summary: str) -> Dict[str, Any]:
        """Get variable classification response from the configured LLM"""
        if not self._check_credentials():
            return "LLM chat configuration is missing. Please configure provider credentials."
        self.logger.debug("Getting variable classification response")

        sys_prompt = """You are an expert data scientist specializing in variable classification and data type analysis. 
        Analyze the provided dataset summary and classify each variable in different categories and provide recommendations.
        
        Consider:
        1. Data distribution and patterns
        2. Missing value patterns
        3. Cardinality (number of unique values)
        4. Business context and naming conventions
        5. Statistical properties
        
        Provide actionable recommendations for data preprocessing and modeling. Also keep the recommendations short and concise."""
        
        prompt = f"""Analyze this dataset and classify all variables:

{dataset_summary}

For category, overview the variables and classify them into different categories as given below:
Borrower Credit History
Borrower Demographics
Borrower Financial Ratios
Credit Inquiries & Account Openings
Credit Utilization & Balances
Identification & Metadata
Loan Details
Loan Listing & Application Info
Loan Performance Metrics

Also provide:
- Key recommendations for data preprocessing
- Insights about the dataset structure"""
        
        try:
            formatted_messages = [
                {
                    "role": "system",
                    "content": [{"type": "text", "text": sys_prompt}]
                },
                {
                    "role": "user", 
                    "content": [{"type": "text", "text": prompt}]
                }
            ]
            
            response = self._call_chat_completion(
                context="variable_classification",
                messages=formatted_messages,
                temperature=0.1,
                response_format=VariableClassificationResponse
            )

            structured = self._normalize_structured_response(response)
            if isinstance(structured, dict):
                self.logger.debug("Variable classification response generated successfully")
                return structured

            text = structured if isinstance(structured, str) else self._extract_response_text(response)
            if not text:
                raise ValueError("Variable classification response is empty")

            try:
                parsed = self._safe_json_load(text)
                if isinstance(parsed, dict):
                    self.logger.debug("Variable classification response generated successfully")
                    return parsed
            except ValueError:
                self.logger.info("Falling back to text-based variable classification response")

            return self._build_variable_classification_fallback(text)
            
        except Exception as e:
            self.logger.error(f"Failed to get variable classification: {str(e)}")
            raise

    def _determine_categories_from_columns(self, column_names: List[str]) -> Dict[str, Any]:
        """
        Determine optimal categories for all columns before processing.
        This ensures category consistency across batches.
        """
        self.logger.info(f"Determining categories for {len(column_names)} columns")
        
        num_columns = len(column_names)
        
        # Determine target number of categories based on dataset size
        if num_columns <= 100:
            target_categories = "8-12"
        elif num_columns <= 500:
            target_categories = "15-25"
        else:
            target_categories = "25-50"
        
        sys_prompt = """You are an expert data architect specializing in organizing data features into meaningful business categories.

        Your task is to analyze a list of column names and determine the optimal set of categories that will organize them logically.

        Guidelines:
        - Create categories that reflect business domains and data relationships
        - Each category should have a clear, descriptive name
        - Provide keywords that help identify which columns belong to each category
        - Assign distinct colors to each category for visualization
        - Categories should be mutually exclusive but collectively exhaustive

        Return a well-organized category structure that will make the knowledge graph intuitive and useful."""

        columns_text = "\n".join([f"- {col}" for col in column_names])
        
        prompt = f"""Analyze these {len(column_names)} column names and determine {target_categories} optimal categories to organize them:

        COLUMN NAMES:
        {columns_text}

        Requirements:
        1. Create {target_categories} categories that best organize these columns
        2. Each category should have:
        - A clear, descriptive name (e.g., "Borrower Demographics", "Loan Performance")
        - A description explaining what types of columns belong there
        - A hex color code for visualization
        - 3-5 keywords that help identify which columns belong to this category
        3. Ensure categories cover all major themes present in the column list
        4. Use business-domain language, not technical jargon
        5. Make categories meaningful for analysis and decision-making

        Focus on creating a logical, hierarchical organization that someone analyzing this data would find intuitive."""

        try:
            formatted_messages = [
                {"role": "system", "content": [{"type": "text", "text": sys_prompt}]},
                {"role": "user", "content": [{"type": "text", "text": prompt}]}
            ]
            
            response = self._call_kg_completion(
                messages=formatted_messages,
                temperature=0.3,
                top_p=1,
                response_format=CategoryPlanResponse
            )
            
            content = self._extract_response_text(response)
            category_plan = self._safe_json_load(content)
            
            self.logger.info(f"Determined {len(category_plan['categories'])} categories: {[c['name'] for c in category_plan['categories']]}")
            
            return category_plan
            
        except Exception as e:
            self.logger.error(f"Failed to determine categories: {str(e)}")
            # Fallback to generic categories
            return {
                "categories": [
                    {"name": "Identifiers", "description": "ID and key columns", "color": "#4E79A7", "keywords": ["id", "key", "identifier", "code"]},
                    {"name": "Temporal", "description": "Date and time columns", "color": "#F28E2B", "keywords": ["date", "time", "timestamp", "year", "month"]},
                    {"name": "Quantitative", "description": "Numerical measurements", "color": "#E15759", "keywords": ["amount", "value", "count", "rate", "score"]},
                    {"name": "Categorical", "description": "Category and classification columns", "color": "#76B7B2", "keywords": ["type", "status", "category", "group", "class"]},
                    {"name": "Others", "description": "Miscellaneous columns", "color": "#999999", "keywords": []}
                ],
                "reasoning": "Fallback generic categories"
            }

    def _run_batch_with_retry(
        self,
        batch_number: int,
        column_batch: List[str],
        predefined_categories: List[Dict],
        total_batches: int,
        column_description_map: List[str],
        problem_statement: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Call _process_column_batch with retry/backoff."""
        for attempt in range(1, MAX_PARALLEL_BATCHES + 1):
            try:
                return self._process_column_batch(
                    column_batch=column_batch,
                    predefined_categories=predefined_categories,
                    column_description_map=column_description_map,
                    batch_number=batch_number,
                    total_batches=total_batches,
                    problem_statement=problem_statement,
                )
            except Exception as exc:
                self.logger.warning(
                    "Batch %s failed on attempt %s/%s: %s",
                    batch_number,
                    attempt,
                    MAX_BATCH_RETRIES,
                    exc,
                )
                if attempt == MAX_BATCH_RETRIES:
                    raise
                time.sleep(BATCH_RETRY_SLEEP_SECONDS)

    def _process_column_batch(
        self, 
        column_batch: List[str], 
        predefined_categories: List[Dict], 
        column_description_map: Dict[str, str],
        batch_number: int,
        total_batches: int,
        problem_statement: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process a batch of columns and assign them to predefined categories.
        Returns nodes and links for this batch only.
        """
        self.logger.info(f"Processing batch {batch_number}/{total_batches} with {len(column_batch)} columns")
        problem_context = self._normalize_problem_statement(problem_statement)
        
        # Format categories for the prompt
        categories_text = "\n".join([
            f"- {cat['name']}: {cat['description']} (Keywords: {', '.join(cat['keywords'])})"
            for cat in predefined_categories
        ])
        
        columns_text = []
        for column_name in column_batch:
            description = column_description_map.get(column_name, "")
            if description:
                columns_text.append(f"- {column_name}: {description}")
            else:
                columns_text.append(f"- {column_name}")
        columns_text = "\n".join(columns_text)
        
        sys_prompt = f"""You are creating nodes and links for a knowledge graph visualization.

        BUSINESS & MODELLING PURPOSE: {problem_context}

        You have been given a predefined set of categories. Your task is to:
        1. Assign each column to the most appropriate category
        2. Create variable nodes for each column
        3. Create links connecting each variable to its category
        4. Do NOT create new categories - use only the predefined ones

        
        
        PREDEFINED CATEGORIES:
        {categories_text}

        Return a JSON with nodes (variable nodes only, NOT category nodes) and links."""

        prompt = f"""Assign these columns to the appropriate predefined categories and create the graph structure:

        COLUMNS TO PROCESS:
        {columns_text}

        Requirements:
        1. Create a variable node for each column with:
        - id: exact column name
        - group: the category name it belongs to (must match one of the predefined categories)
        - size: 10
        - color: a lighter shade matching the category color
        2. Create a link for each variable to its category with strength 1.0
        3. If columns are related, add relationship links between them (strength 0.3-0.9)
        4. Use ONLY the predefined category names - do not create new categories

        Return JSON format:
        {{
        "nodes": [list of variable nodes],
        "links": [list of links],
        "batch_info": "Brief summary of this batch"
        }}"""

        try:
            formatted_messages = [
                {"role": "system", "content": [{"type": "text", "text": sys_prompt}]},
                {"role": "user", "content": [{"type": "text", "text": prompt}]}
            ]
            
            # Use a simple response model for batch processing
            response = self._call_kg_completion(
                messages=formatted_messages,
                temperature=0.1,
                top_p=1,
                response_format={"type": "json_object"}
            )
            
            content = self._extract_response_text(response)
            batch_data = self._safe_json_load(content)
            
            # Validate batch data structure
            if not isinstance(batch_data, dict):
                raise ValueError(f"Batch {batch_number}: Expected dict, got {type(batch_data)}")
            
            if 'nodes' not in batch_data:
                self.logger.warning(f"Batch {batch_number}: Missing 'nodes' field, using empty list")
                batch_data['nodes'] = []
            
            if 'links' not in batch_data:
                self.logger.warning(f"Batch {batch_number}: Missing 'links' field, using empty list")
                batch_data['links'] = []
            
            # Validate nodes structure
            if not isinstance(batch_data['nodes'], list):
                raise ValueError(f"Batch {batch_number}: 'nodes' must be a list")
            
            # Validate each node has required fields
            for idx, node in enumerate(batch_data['nodes']):
                if not isinstance(node, dict):
                    raise ValueError(f"Batch {batch_number}: Node {idx} is not a dict")
                if 'id' not in node:
                    raise ValueError(f"Batch {batch_number}: Node {idx} missing 'id' field")
                if 'group' not in node:
                    raise ValueError(f"Batch {batch_number}: Node {idx} missing 'group' field")
            
            # Validate links structure
            if not isinstance(batch_data['links'], list):
                raise ValueError(f"Batch {batch_number}: 'links' must be a list")
            
            # Validate each link has required fields
            for idx, link in enumerate(batch_data['links']):
                if not isinstance(link, dict):
                    raise ValueError(f"Batch {batch_number}: Link {idx} is not a dict")
                if 'source' not in link or 'target' not in link:
                    raise ValueError(f"Batch {batch_number}: Link {idx} missing 'source' or 'target' field")
            
            self.logger.info(f"Batch {batch_number} processed: {len(batch_data.get('nodes', []))} nodes, {len(batch_data.get('links', []))} links")
            
            return batch_data
            
        except Exception as e:
            self.logger.error(f"Failed to process batch {batch_number}: {str(e)}")
            return {"nodes": [], "links": [], "batch_info": f"Error processing batch {batch_number}"}

    def _aggregate_batch_results(
        self, 
        batch_results: List[Dict], 
        predefined_categories: List[Dict],
        total_columns: int
    ) -> Dict[str, Any]:
        """
        Aggregate results from multiple batches and add category nodes.
        """
        self.logger.info(f"Aggregating {len(batch_results)} batches")
        
        all_nodes = []
        all_links = []
        seen_node_ids = set()
        seen_links = set()
        
        # Add category nodes first
        for cat in predefined_categories:
            all_nodes.append({
                'id': cat['name'],
                'group': 'category',
                'size': 25,
                'color': cat['color']
            })
            seen_node_ids.add(cat['name'])
        
        # Aggregate variable nodes and links from all batches
        for batch in batch_results:
            for node in batch.get('nodes', []):
                node_id = node.get('id')
                if node_id and node_id not in seen_node_ids:
                    all_nodes.append(node)
                    seen_node_ids.add(node_id)
            
            for link in batch.get('links', []):
                link_key = (link.get('source'), link.get('target'))
                if link_key not in seen_links:
                    all_links.append(link)
                    seen_links.add(link_key)
        
        # Add inter-category links for better visualization
        category_names = [cat['name'] for cat in predefined_categories]
        for i in range(len(category_names) - 1):
            link_key = (category_names[i], category_names[i + 1])
            if link_key not in seen_links:
                all_links.append({
                    'source': category_names[i],
                    'target': category_names[i + 1],
                    'strength': 0.4
                })
        
        # Prepare categories list
        categories_list = [
            {'name': cat['name'], 'color': cat['color']}
            for cat in predefined_categories
        ]
        
        # Validation
        variable_nodes = [n for n in all_nodes if n.get('group') != 'category']
        category_nodes = [n for n in all_nodes if n.get('group') == 'category']
        
        self.logger.info(f"Aggregation complete: {len(variable_nodes)} variables, {len(category_nodes)} categories, {len(all_links)} links")
        self.logger.info(f"Expected {total_columns} variables, got {len(variable_nodes)}")
        
        # Prepare the result dictionary
        aggregated_result = {
            'nodes': all_nodes,
            'links': all_links,
            'categories': categories_list,
            'algorithm_explanation': f"Knowledge graph generated from {total_columns} columns across {len(batch_results)} batches, organized into {len(category_nodes)} categories.",
            'relationship_mapping': f"Variables are connected to {len(category_nodes)} domain categories with relationship links based on semantic similarity.",
            'usage_instructions': "Hover over nodes to explore relationships. Use category filter to focus on specific domains."
        }
        
        # Validate the aggregated result before returning
        try:
            validated_result = self._validate_graph_data(aggregated_result)
            return validated_result
        except Exception as e:
            self.logger.error(f"Aggregation validation failed: {str(e)}")
            # Return a minimal valid structure to prevent complete failure
            if len(all_nodes) == 0:
                raise ValueError("No valid nodes after aggregation and validation")
            # If validation fails but we have nodes, return the aggregated result anyway
            # (validation might have fixed some issues)
            return aggregated_result
        
    
    def get_knowledge_graph(
        self,
        data_dictionary: str,
        dataset_id: Optional[str] = None,
        problem_statement: Optional[str] = None,
        model_id_override: Optional[str] = None,
    ) -> str:
        """Get knowledge graph visualization from the configured LLM"""
        config, _, model_id = self._resolve_kg_config(model_id_override=model_id_override)
        if not config.is_ready():
            return json.dumps({
                "html_content": self._get_fallback_html("Knowledge graph LLM not configured"),
                "algorithm_explanation": "Service unavailable",
                "relationship_mapping": "",
                "usage_instructions": "Please configure KG_PROVIDER and KG_MODEL"
            })
        self.logger.debug("Getting knowledge graph response")
        
        try:
            # Parse columns from data dictionary
            parsed_dictionary = self._extract_columns_from_dictionary(data_dictionary)
            columns = parsed_dictionary['column_names']
            structured_dictionary_text = parsed_dictionary['structured_text']
            column_description_map = parsed_dictionary['column_description_map']

            num_columns = len(columns)
            
            self.logger.info(f"Generating knowledge graph for {num_columns} columns")
            
            # Decide on processing strategy
            BATCH_SIZE = 200
            
            if num_columns <= BATCH_SIZE:
                # Small dataset - use original single-call approach
                result_json = self._generate_knowledge_graph_single_call(
                    structured_dictionary_text,
                    columns,
                    problem_statement=problem_statement,
                )
                result = json.loads(result_json)
                # Cache the result if dataset_id is provided
                if dataset_id:
                    cache_key = _kg_cache_key(dataset_id, model_id)
                    result["model_id"] = model_id
                    set_kg_cache(cache_key, result)
                    self.logger.info(f"Cached single-call knowledge graph for {cache_key}")
                
                return result_json
            else:
                # Large dataset - use batched approach with progress updates
                return self._generate_knowledge_graph_batched(
                    columns,
                    structured_dictionary_text,
                    column_description_map,
                    dataset_id,
                    cache_key=_kg_cache_key(dataset_id, model_id),
                    model_id=model_id,
                    problem_statement=problem_statement
                )
                
        except Exception as e:
            self.logger.error(f"Knowledge graph generation failed: {str(e)}", exc_info=True)
            return self._create_error_response("Knowledge graph generation failed", str(e))

    async def generate_async_knowledge_graph(
        self,
        dataset_id: str,
        data_dictionary: str,
        problem_statement: Optional[str] = None,
        model_id_override: Optional[str] = None,
    ) -> None:
        """Generate knowledge graph in background and cache immediately."""
        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None, self.get_knowledge_graph, data_dictionary, dataset_id, problem_statement, model_id_override
            )
            # Result is already cached inside get_knowledge_graph
            self.logger.info(f"Pre-generated knowledge graph for {dataset_id}")
        except Exception as e:
            self.logger.exception(f"Background KG generation failed for {dataset_id}: {e}")

    def get_validated_graph_json(self, dataset_id: str, data_dictionary: str) -> str:
        return self.get_knowledge_graph(data_dictionary, dataset_id, None)

    def _darken_color(self, hex_color: str, factor: float = 0.6) -> str:
        """
        Darken a hex color by a factor (0.0 = black, 1.0 = original).
        factor=0.6 means 60% of original brightness (40% darker).
        """
        try:
            hex_color = hex_color.lstrip('#')
            
            # Convert to RGB
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            
            # Darken by factor
            r = int(r * factor)
            g = int(g * factor)
            b = int(b * factor)
            
            return f'#{r:02x}{g:02x}{b:02x}'
        except:
            return '#666666'
                
    def _lighten_color(self, hex_color: str, factor: float = 1.25) -> str:
        """Return a lighter version of the colour (factor > 1 = lighter)."""
        try:
            base = hex_color.lstrip('#')
            r, g, b = int(base[0:2], 16), int(base[2:4], 16), int(base[4:6], 16)
            r = min(int(r * factor), 255)
            g = min(int(g * factor), 255)
            b = min(int(b * factor), 255)
            return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            self.logger.warning(f"Unable to lighten colour '{hex_color}', using fallback.")
            return '#cccccc'

    def _pastel_color(self, hex_color: str, mix: float = 0.45, desaturate: float = 0.08) -> str:
        """Return a pastel version of the color by mixing with white and desaturating slightly."""
        try:
            base = hex_color.lstrip('#')
            r, g, b = int(base[0:2], 16), int(base[2:4], 16), int(base[4:6], 16)
            # Mix with white
            r = r + (255 - r) * mix
            g = g + (255 - g) * mix
            b = b + (255 - b) * mix
            # Slight desaturation toward the average
            avg = (r + g + b) / 3
            r = r * (1 - desaturate) + avg * desaturate
            g = g * (1 - desaturate) + avg * desaturate
            b = b * (1 - desaturate) + avg * desaturate
            return f"#{int(min(max(r, 0), 255)):02x}{int(min(max(g, 0), 255)):02x}{int(min(max(b, 0), 255)):02x}"
        except Exception:
            self.logger.warning(f"Unable to pastelize colour '{hex_color}', using fallback.")
            return '#d1d5db'

    def _extract_columns_from_dictionary(self, data_dictionary: str) -> Dict[str, Any]:
        """Parse data dictionary into names + descriptions for prompt/context."""
        header_keywords = {
            'column', 'columns', 'column name', 'feature', 'features',
            'variable', 'variables', 'field', 'fields'
        }
        rows = []
        reader = csv.reader(StringIO(data_dictionary))
        for row in reader:
            cleaned = [cell.strip() for cell in row]
            if any(cleaned):
                rows.append(cleaned)

        if not rows:
            # fallback: treat each non-empty line as "column_name, description"
            column_entries = []
            for line in data_dictionary.splitlines():
                line = line.strip()
                if not line:
                    continue
                if ',' in line:
                    name, desc = line.split(',', 1)
                else:
                    name, desc = line, ''
                name = name.strip()
                if name:
                    column_entries.append({"name": name, "description": desc.strip()})
            column_names = [entry["name"] for entry in column_entries]
        else:
            header_row = rows[0]
            name_idx = None
            for idx, value in enumerate(header_row):
                if value and value.strip().lower() in header_keywords:
                    name_idx = idx
                    break

            if name_idx is None:
                name_idx = 0
                data_rows = rows
                has_header = False
            else:
                data_rows = rows[1:]
                has_header = True

            column_entries = []
            for row in data_rows:
                if len(row) <= name_idx:
                    continue
                col_name = row[name_idx].strip()
                if not col_name:
                    continue

                descriptions = []
                for idx, cell in enumerate(row):
                    if idx == name_idx:
                        continue
                    value = cell.strip()
                    if not value:
                        continue
                    if has_header and idx < len(header_row):
                        header_label = header_row[idx].strip()
                        if header_label:
                            descriptions.append(f"{header_label}: {value}")
                        else:
                            descriptions.append(value)
                    else:
                        descriptions.append(value)

                column_entries.append({
                    "name": col_name,
                    "description": "; ".join(descriptions)
                })

            column_names = [entry["name"] for entry in column_entries]

        column_description_map = {entry["name"]: entry["description"] for entry in column_entries}
        structured_lines = [
            f"- {entry['name']}: {entry['description']}" if entry['description'] else f"- {entry['name']}"
            for entry in column_entries
        ]
        structured_text = "\n".join(structured_lines) if structured_lines else data_dictionary

        self.logger.info(f"Extracted {len(column_names)} columns from data dictionary")
        return {
            "column_names": column_names,
            "column_details": column_entries,
            "column_description_map": column_description_map,
            "structured_text": structured_text
        }   

    def _generate_knowledge_graph_single_call(
        self,
        structured_dictionary_text: str,
        columns: List[str],
        problem_statement: Optional[str] = None,
    ) -> str:
        """Original implementation for datasets <= 200 columns."""
        # Your existing implementation goes here (the full sys_prompt and prompt code)
        # I'll provide a condensed version - use your existing one
        problem_context = self._normalize_problem_statement(problem_statement)
        
        sys_prompt = """You are an expert visualizer and architect for feature graphs, specializing in building domain-driven feature graphs from Data_Description as an input.

        Your task is to create a comprehensive feature graph where nodes represent column/feature names as it is organized and connected by business/domain concepts.

        ═══════════════════════════════════════════════════════════════════════════════
        INSTRUCTIONS
        ═══════════════════════════════════════════════════════════════════════════════

        Create an interactive, visually appealing knowledge graph that represents semantic metadata variables and their inferred relationships. The graph should have the following features and appearance:

        Nodes:
        - Category Nodes: Larger, distinctively colored circular nodes representing inferred categories of metadata variables (e.g., Identifiers, Temporal, Locational, Quantitative, Categorical, System etc).
        - Variable Nodes: Smaller circular nodes representing individual metadata/column variables, colored to match their assigned category.
        - Each node should display a label with the variable or category name in a clean, readable font.
        - For datasets with up to 100 columns: aim for 8-12 meaningful & distinct categories
        - For datasets with 100-500 columns: aim for 12-20 meaningful & distinct categories, although these numbers are just suggestive and not compulsory.
        - For datasets with 500+ columns: aim for 20-25 meaningful & distinct categories, although these numbers are just suggestive and not compulsory.
        - Maximum limit: 25 categories (system will handle consolidation if needed)
        - ALL VARIABLES/COLUMNS MUST BE PRESENT AS VARIABLE NODES, NONE OF THEM SHOULD BE MISSED.

        Edges (Links):
        - Category Links: Light, subtle lines connecting variable nodes to their category node.
        - Relationship Links: Stronger, more prominent lines connecting variable nodes that share a semantic or structural relationship based on similarity analysis and business/domain knowledge.
        - Relationship Links should be visually distinct with thicker stroke and color highlight (e.g., coral or orange) on hover or when connected to the hovered node.

        Legend Display:
        - Include a legend key-value pair that lists all categories which are there in generated feature graph.
        - Each category in the legend should display a colored circle matching the category's node color, followed by the category name.
        - Make sure that all categories are present in the legend.

        ═══════════════════════════════════════════════════════════════════════════════
        CORE PRINCIPLES
        ═══════════════════════════════════════════════════════════════════════════════
        ALL VARIABLES/COLUMNS MUST BE PRESENT AS VARIABLE NODES, NONE OF THEM SHOULD BE MISSED.
        ALL NODES MUST BE CONNECTED THROUGH RELATIONSHIPS, THERE CAN BE HIERARCHY BUT THERE CAN'T BE DISJOINT CLUSTERS.

        1. Nodes:
            - No nodes for possible values (e.g., if a column has values like "RENT", "OWN" - ignore these)
            - No sample data, no inferred values, no made-up entities
            - Nodes can be named as categories, which are made basis domain/business knowledge and variable nodes which are to be made basis column names/metadata
            - Build deep, multi-level structures reflecting business domain
            - NO orphan nodes - every node must connect to the graph
            - ALL VARIABLES/COLUMNS MUST BE PRESENT AS VARIABLE NODES, NONE OF THEM SHOULD BE MISSED.

        2. Edges (Links):
        - Use business-meaningful relationship types for category links and relationship links
        - All the nodes must be connected to their respective category nodes, and also there must be some relationship between these category nodes too.
        - Edges must be between source and target nodes, which should be named as per column names/category names

        3. Colors:
        - Use distinct, professional colors for each category
        - Category nodes should have bold, saturated colors
        - Variable nodes should have lighter shades of their category color
        - Recommended color palette: #4E79A7 (blue), #F28E2B (orange), #E15759 (red), #76B7B2 (teal), #59A14F (green), #EDC948 (yellow), #B07AA1 (purple), #FF9DA7 (pink), #8C564B (brown), #17BECF (cyan)

        4. Size Guidelines:
        - Category nodes: size = 25
        - Variable nodes: size = 10

        ═══════════════════════════════════════════════════════════════════════════════
        OUTPUT FORMAT SPECIFICATION
        ═══════════════════════════════════════════════════════════════════════════════

        ALL NODES MUST BE CONNECTED THROUGH RELATIONSHIPS, THERE CAN BE HIERARCHY BUT THERE CAN'T BE DISJOINT CLUSTERS.
        ALL VARIABLES/COLUMNS MUST BE PRESENT AS VARIABLE NODES, NONE OF THEM SHOULD BE MISSED.

        You MUST return a valid JSON object with this EXACT structure:

        {
        "nodes": [
            {
            "id": "Category Name",
            "group": "category",
            "size": 25,
            "color": "#4E79A7"
            },
            {
            "id": "variable_name",
            "group": "Category Name",
            "size": 10,
            "color": "#A0CBE8"
            }
        ],
        "links": [
            {
            "source": "variable_name",
            "target": "Category Name",
            "strength": 1.0
            }
        ],
        "categories": [
            {
            "name": "Category Name",
            "color": "#4E79A7"
            },
            {
            "name": "Another Category",
            "color": "#F28E2B"
            }
        ],
        "algorithm_explanation": "Brief explanation of how the graph is structured and organized",
        "relationship_mapping": "Description of the types of relationships represented in the graph",
        "usage_instructions": "Instructions for interpreting and using the knowledge graph"
        }

        CRITICAL RULES:
        1. Every variable node MUST have group = its category name
        2. Every category node MUST have group = "category"
        3. Every variable node MUST be connected to its category node via a link with strength = 1.0
        4. Related variables should be connected with links having strength between 0.3 to 0.9
        5. Related categories should be connected with links having strength between 0.3 to 0.7
        6. Variable node colors should be lighter shades of their category color
        7. All node IDs in links must exactly match node IDs in the nodes array
        8. Aim for appropriate number of categories based on dataset size (see guidelines above)
        9. All categories in nodes must be present in the categories dictionary
        10. NO orphan nodes - every node must have at least one connection
        11. Make sure all variables/columns are present as variable nodes, none of them should be missed

        ═══════════════════════════════════════════════════════════════════════════════
        VALIDATION CHECKLIST
        ═══════════════════════════════════════════════════════════════════════════════

        Before returning, verify:
        ✓ All node IDs used in links exist in the nodes array
        ✓ All variable nodes are connected to their category node
        ✓ No orphan nodes (every node has at least one link)
        ✓ Number of categories is appropriate for dataset size
        ✓ All categories are meaningful & distinct
        ✓ All categories in nodes are in the categories dictionary
        ✓ Category nodes have group = "category"
        ✓ Variable nodes have group = their category name
        ✓ Colors are valid hex codes
        ✓ Strength values are between 0.0 and 1.0
        ✓ Make sure all variables/columns are present as variable nodes, none of them should be missed
        """
        
        prompt = f"""Generate a comprehensive knowledge graph in JSON format focused on provided data domain for business analysis and decision-making. The graph should include multiple categories that capture different dimensions.

        BUSINESS & MODELLING PURPOSE: {problem_context}

        **STRICTLY look for the relationship amongst the categories - if they are related then connect them**

        Example categories (THESE ARE JUST REFERENCES, NOT SOMETHING YOU HAVE TO FOLLOW, MAKE CATEGORIES AS PER DATA PROVIDED ONLY):
        - Borrower Credit History
        - Borrower Demographics
        - Borrower Financial Ratios
        - Credit Inquiries & Account Openings
        - Credit Utilization & Balances
        - Identification & Metadata
        - Loan Details
        - Loan Listing & Application Info
        - Loan Performance Metrics

        <DATA DESCRIPTION>
        {structured_dictionary_text}
        </DATA DESCRIPTION>

        <Additional Instructions>
        1. **Check for any error in the node mapping**
        2. **Check if all nodes mentioned in links are defined in nodes array**
        3. **Ensure all variable nodes are connected to their category nodes**
        4. **Ensure related categories are connected to each other**
        5. **Use appropriate colors - category nodes should have bold colors, variable nodes lighter shades**
        6. **Apply business logic to determine relationships between variables**
        7. **Appropriate number of categories based on dataset size - group similar concepts together**
        8. **NO orphan nodes - every node must be connected**
        9. **Strength values: 1.0 for category links, 0.3-0.9 for variable relationships, 0.3-0.7 for category relationships**
        10. **Make sure all variables/columns are present as variable nodes, none of them should be missed** 
        </Additional Instructions>
        """

        self.logger.info(f"The model used for generating KG is: {self.kg_config.model}")
        try:
            formatted_messages = [
                {
                    "role": "system",
                    "content": [{"type": "text", "text": sys_prompt}]
                },
                {
                    "role": "user", 
                    "content": [{"type": "text", "text": prompt}]
                }
            ]
            
            # Use the new JSON response format
            response_format = KnowledgeGraphJSONResponse
            if self.kg_config.provider == "bedrock":
                response_format = {"type": "json_object"}

            continuation_prompt = {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "The previous response was cut off before the JSON payload finished. Please continue by returning only the JSON object with nodes, links, categories, algorithm_explanation, relationship_mapping, and usage_instructions."
                    }
                ]
            }

            attempt_messages = formatted_messages
            graph_data = None
            last_text = ""

            for attempt in range(2):
                response = self._call_kg_completion(
                    messages=attempt_messages,
                    temperature=0.0,
                    top_p=1,
                    response_format=response_format
                )

                structured = self._normalize_structured_response(response)
                if isinstance(structured, dict):
                    graph_data = structured
                else:
                    content = self._extract_response_text(response)
                    last_text = content
                    if not content:
                        raise ValueError("LLM returned empty content")
                    try:
                        graph_data = self._safe_json_load(content)
                    except ValueError as e:
                        self.logger.error(
                            "JSON decode error: %s. response_chars=%s",
                            e,
                            len(content) if content else 0,
                        )
                        json_match = re.search(r'\{.*\}', content, re.DOTALL)
                        if json_match:
                            try:
                                graph_data = json.loads(json_match.group(0))
                                self.logger.info("Successfully extracted JSON from response")
                            except json.JSONDecodeError:
                                graph_data = None

                if graph_data and graph_data.get("nodes"):
                    break

                if attempt == 0 and self.kg_config.provider == "bedrock":
                    self.logger.warning("Knowledge graph response missing nodes; retrying with continuation prompt")
                    attempt_messages = formatted_messages + [continuation_prompt]
                    graph_data = None
                    continue

                if not graph_data:
                    break

            if not graph_data or not graph_data.get("nodes"):
                fallback_reason = last_text or "LLM response missing JSON payload"
                self.logger.warning("Knowledge graph JSON missing nodes; returning constructed fallback graph.")
                graph_data = self._build_kg_fallback(columns, fallback_reason)

            # Validate and sanitize the graph data
            validated_data = self._validate_graph_data(graph_data)
            html_content = generate_knowledge_graph_html(
                nodes=validated_data['nodes'],
                links=validated_data['links'],
                categories=validated_data['categories']
            )
            
            # Return in the expected format
            result = {
                "html_content": html_content,
                "algorithm_explanation": validated_data.get('algorithm_explanation', 'Knowledge graph generated successfully'),
                "relationship_mapping": validated_data.get('relationship_mapping', 'Relationships based on domain knowledge'),
                "usage_instructions": validated_data.get('usage_instructions', 'Hover over nodes to explore relationships'),
                "nodes": validated_data.get('nodes', []),
                "categories": validated_data.get('categories', []),
                "processing_info": {  # Add processing_info for consistency
                    "status": "complete",
                    "total_batches": 1,
                    "completed_batches": 1
                }
            }
            
            self.logger.info(f"Knowledge graph generated successfully with {len(validated_data['nodes'])} nodes and {len(validated_data['links'])} links")
            return json.dumps(result)
            
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parsing failed: {str(e)}")
            return self._create_error_response("Invalid JSON format from AI model", str(e))
        
        except KeyError as e:
            self.logger.error(f"Missing required field in graph data: {str(e)}")
            return self._create_error_response("Incomplete graph data", f"Missing field: {str(e)}")
        
        except ValueError as e:
            self.logger.error(f"Validation error: {str(e)}")
            return self._create_error_response("Data validation failed", str(e))
        
        except Exception as e:
            self.logger.error(f"Failed to get knowledge graph response: {str(e)}", exc_info=True)
            return self._create_error_response("Knowledge graph generation failed", str(e))

    def _generate_knowledge_graph_batched(
        self,
        columns: List[str],
        structured_dictionary_text: str,
        column_description_map: Dict[str, str],
        dataset_id: str = None,
        cache_key: Optional[str] = None,
        model_id: Optional[str] = None,
        problem_statement: Optional[str] = None,
    ) -> str:
        """Generate knowledge graph by processing columns in batches."""
        try:
            # Step 1: Determine categories upfront for consistency
            self.logger.info("Step 1: Determining categories for all columns")
            category_plan = self._determine_categories_from_columns(columns)
            predefined_categories = category_plan.get('categories', [])
            
            if not predefined_categories:
                self.logger.error("Failed to determine categories, falling back to single call")
                return self._generate_knowledge_graph_single_call(
                    structured_dictionary_text,
                    columns,
                    problem_statement=problem_statement,
                )
            
            self.logger.info(f"Determined {len(predefined_categories)} categories: {[c['name'] for c in predefined_categories]}")
            
            # Step 2: Process in batches
            batch_size = 200
            total_batches = (len(columns) + batch_size - 1) // batch_size
            self.logger.info(f"Step 2: Processing {len(columns)} columns in {total_batches} batches")
            
            batch_results = []
            
            # Process first batch synchronously
            self.logger.info(f"Processing batch 1/{total_batches} (synchronous)")
            first_batch = columns[:batch_size]
            first_result = self._process_column_batch(
                first_batch, 
                predefined_categories, 
                column_description_map,
                1, 
                total_batches,
                problem_statement=problem_statement,
            )
            batch_results.append(first_result)
            
            # Generate HTML for first batch and return immediately
            first_batch_aggregated = self._aggregate_batch_results(
                [first_result], 
                predefined_categories,
                len(columns)
            )
            
             # Validate the aggregated data before generating HTML
            try:
                validated_first_batch = self._validate_graph_data(first_batch_aggregated)
            except Exception as e:
                self.logger.error(f"Validation failed for first batch: {str(e)}")
                return self._create_error_response("First batch validation failed", str(e))
            

            first_batch_html = generate_knowledge_graph_html(
                validated_first_batch['nodes'],
                validated_first_batch['links'],
                validated_first_batch['categories'],
                status="Updating" if total_batches > 1 else "Completed",
                progress=f"1/{total_batches} batches" if total_batches > 1 else ""
            )
            
            result = {
                "html_content": first_batch_html,
                "algorithm_explanation": validated_first_batch.get('algorithm_explanation', ''),
                "relationship_mapping": validated_first_batch.get('relationship_mapping', ''),
                "usage_instructions": validated_first_batch.get('usage_instructions', ''),
                "nodes": validated_first_batch.get('nodes', []),
                "categories": validated_first_batch.get('categories', []),
                "model_id": model_id,
                "processing_info": {  # Add this section
                    "total_columns": len(columns),
                    "processed_columns": len(first_batch),
                    "total_batches": total_batches,
                    "completed_batches": 1,
                    "status": "partial" if total_batches > 1 else "complete"
                }
            }
            
            # Cache the first batch result
            # Store dataset_id as instance variable for caching
            cache_key = cache_key or _kg_cache_key(dataset_id, model_id)
            set_kg_cache(cache_key, result)
            self.logger.info(f"Cached first batch result for {cache_key}: {len(first_result.get('nodes', []))} variables, status={result['processing_info']['status']}")
            
            self.logger.info(f"Batch 1 complete: {len(first_result.get('nodes', []))} variables, returning to frontend")
            
            # Process remaining batches synchronously (in this implementation)
            # Note: For true background processing, you'd need to use asyncio or threading
            if total_batches > 1:
                remaining_columns = columns[batch_size:]
                self.logger.info(f"{len(remaining_columns)} columns remain across {total_batches - 1} batches")

                # If we have a dataset_id we can cache updates for the polling endpoint
                if dataset_id:
                    remaining_batches = [
                        remaining_columns[i:i + batch_size]
                        for i in range(0, len(remaining_columns), batch_size)
                    ]
                    
                    categories_list = validated_first_batch['categories']
                    cumulative_nodes = validated_first_batch['nodes'].copy()
                    cumulative_links = validated_first_batch['links'].copy()
                    seen_node_ids =  {n['id'] for n in validated_first_batch['nodes']}
                    seen_links = {(link.get('source'), link.get('target')) for link in validated_first_batch['links']}

                    self.logger.info(f"Spawning background thread for {len(remaining_batches)} remaining batches")
                    Thread(
                        target=self._process_remaining_batches_background,
                        args=(
                            remaining_batches,
                            predefined_categories,
                            categories_list,
                            cumulative_nodes,
                            cumulative_links,
                            seen_node_ids,
                            seen_links,
                            cache_key,
                            total_batches,
                            len(columns),
                            column_description_map,
                            problem_statement
                        ),
                        daemon=True,
                    ).start()
                else:
                    self.logger.warning("dataset_id missing; cannot cache progressive updates for polling")

            return json.dumps(result)
            
        except Exception as e:
            self.logger.error(f"Error in batched knowledge graph generation: {str(e)}")
            return self._create_error_response("Batched knowledge graph generation failed", str(e))
            
    def _process_remaining_batches_background(
        self,
        remaining_batches: List[List[str]],
        predefined_categories: List[Dict],
        categories_list: List[Dict],
        cumulative_nodes: List[Dict],
        cumulative_links: List[Dict],
        seen_node_ids: set,
        seen_links: set,
        cache_key: str,
        total_batches: int,
        total_columns: int,
        column_description_map: Dict[str, str],
        problem_statement: Optional[str] = None,
    ):
        """
        Background thread that processes remaining batches and caches results.
        Updates cache after each batch completion.
        """
        try:
            self.logger.info(f"Background processing started for {len(remaining_batches)} batches")

            # Track which batches have completed (set of batch indices)
            completed_batch_indices = set()
            # Map batch index to its column count for accurate progress tracking
            batch_column_counts = {idx + 2: len(batch) for idx, batch in enumerate(remaining_batches)}
            # Batch 1 is already done
            completed_batch_indices.add(1)

            with ThreadPoolExecutor(max_workers=MAX_PARALLEL_BATCHES) as executor:
                future_map: Dict[concurrent.futures.Future, Tuple[int, List[str]]] = {}

                for batch_idx, batch in enumerate(remaining_batches, start=2):
                    future = executor.submit(
                        self._run_batch_with_retry,
                        batch_idx,
                        batch,
                        predefined_categories,
                        total_batches,
                        column_description_map,
                        problem_statement,
                    )
                    future_map[future] = (batch_idx, batch)

                for future in as_completed(future_map):
                    batch_idx, batch = future_map[future]
                    try:
                        self.logger.info(
                        f"Processing batch {batch_idx}/{total_batches} (background)"
                        f"Current cumulative: {len(cumulative_nodes)} nodes, {len(cumulative_links)} links"                       
                        )

                        batch_result = future.result()
                        
                        # Validate batch_result structure before processing
                        if not isinstance(batch_result, dict):
                            self.logger.error(
                                f"Batch {batch_idx} returned invalid result type: {type(batch_result)}"
                            )
                            continue
                        
                        # Ensure batch_result has required fields
                        if 'nodes' not in batch_result:
                            self.logger.warning(f"Batch {batch_idx} missing 'nodes', using empty list")
                            batch_result['nodes'] = []
                        if 'links' not in batch_result:
                            self.logger.warning(f"Batch {batch_idx} missing 'links', using empty list")
                            batch_result['links'] = []
                        
                        # Validate nodes and links are lists
                        if not isinstance(batch_result.get('nodes', []), list):
                            self.logger.error(f"Batch {batch_idx} 'nodes' is not a list")
                            continue
                        if not isinstance(batch_result.get('links', []), list):
                            self.logger.error(f"Batch {batch_idx} 'links' is not a list")
                            continue
                        

                        # Store batch nodes/links temporarily - don't add to cumulative yet
                        batch_nodes = []
                        batch_links = []
                        
                        for node in batch_result.get("nodes", []):
                            node_id = node.get("id")
                            if node_id and node_id not in seen_node_ids:
                                # Validate node structure before adding
                                if not isinstance(node, dict):
                                    self.logger.warning(f"Batch {batch_idx}: Skipping invalid node (not a dict)")
                                    continue
                                if 'id' not in node or 'group' not in node:
                                    self.logger.warning(f"Batch {batch_idx}: Skipping node missing id/group: {node}")
                                    continue
                                batch_nodes.append(node)

                        for link in batch_result.get("links", []):
                            if not isinstance(link, dict):
                                self.logger.warning(f"Batch {batch_idx}: Skipping invalid link (not a dict)")
                                continue
                            if 'source' not in link or 'target' not in link:
                                self.logger.warning(f"Batch {batch_idx}: Skipping link missing source/target: {link}")
                                continue
                            link_key = (link.get("source"), link.get("target"))
                            if link_key not in seen_links:
                                batch_links.append(link)

                        # Create temporary cumulative data with batch results
                        temp_cumulative_nodes = cumulative_nodes.copy()
                        temp_cumulative_links = cumulative_links.copy()
                        temp_seen_node_ids = seen_node_ids.copy()
                        temp_seen_links = seen_links.copy()
                        
                        # Add batch nodes/links to temporary data
                        for node in batch_nodes:
                            node_id = node.get("id")
                            if node_id not in temp_seen_node_ids:
                                temp_cumulative_nodes.append(node)
                                temp_seen_node_ids.add(node_id)
                        
                        for link in batch_links:
                            link_key = (link.get("source"), link.get("target"))
                            if link_key not in temp_seen_links:
                                temp_cumulative_links.append(link)
                                temp_seen_links.add(link_key)

                        # Mark this batch as completed (temporarily)
                        temp_completed_batch_indices = completed_batch_indices.copy()
                        temp_completed_batch_indices.add(batch_idx)
                        temp_num_completed = len(temp_completed_batch_indices)
                        
                        # Calculate actual processed columns based on completed batches
                        temp_processed_columns = sum(batch_column_counts.get(idx, 0) for idx in temp_completed_batch_indices)

                        current_data = {
                            "nodes": temp_cumulative_nodes,
                            "links": temp_cumulative_links,
                            "categories": categories_list,
                            "algorithm_explanation": (
                                "The graph is structured with category nodes representing key business domains "
                                "related to borrower and loan data. Each variable node is assigned to a category "
                                "based on its semantic meaning and business context. Variable nodes connect to their "
                                "category node with strong links (strength=1.0). Related variables across categories "
                                "are connected with relationship links of varying strengths (0.3-0.9) to reflect "
                                "semantic and business relationships. Categories themselves are interconnected to "
                                "represent domain interdependencies, ensuring a fully connected graph without orphan nodes."
                                f" Knowledge graph: {temp_num_completed}/{total_batches} batches complete"
                            ),
                            "relationship_mapping": (
                                "Category links connect variables to their respective categories. Relationship links "
                                "between variables represent semantic or business relationships such as credit history "
                                "influencing risk assessment, loan details relating to repayment behavior, and borrower "
                                "demographics impacting risk models. Category-to-category links represent broader domain "
                                "relationships, e.g., Borrower Credit History relates to Risk Assessment and Credit "
                                "Inquiries. This mapping supports understanding of how different data dimensions interact "
                                f"in loan and borrower analysis. Variables organized into {len(predefined_categories)} categories."
                            ),
                            "usage_instructions": (
                                "Use the graph to explore data dimensions by category. Hover over nodes to highlight "
                                "relationships. Category nodes provide a high-level view of data domains, while variable "
                                "nodes show specific features. Relationship links reveal how variables and categories "
                                "influence each other, aiding in business analysis, feature engineering, and decision-making. "
                                "The legend helps identify categories by color for easy navigation."
                            ),
                        }

                        # Validate the data with error handling
                        try:
                            validated_data = self._validate_graph_data(current_data)
                        except Exception as validation_error:
                            self.logger.error(
                                f"Validation failed for batch {batch_idx}: {validation_error}",
                                exc_info=True
                            )
                            # Skip this batch update - don't modify cumulative data
                            # Keep the previous valid state
                            continue

                        # Only mark as complete when ALL batches are done
                        is_complete = temp_num_completed >= total_batches
                        status = "Completed" if is_complete else "Updating"
                        
                        try:
                            html_content = generate_knowledge_graph_html(
                                nodes=validated_data["nodes"],
                                links=validated_data["links"],
                                categories=validated_data["categories"],
                                status=status,
                                progress=f"{temp_num_completed}/{total_batches} batches",
                            )
                        except Exception as html_error:
                            self.logger.error(
                                f"HTML generation failed for batch {batch_idx}: {html_error}",
                                exc_info=True
                            )
                            # Skip this batch update - don't modify cumulative data
                            continue

                        # Only update cumulative data if everything succeeded
                        cumulative_nodes = temp_cumulative_nodes
                        cumulative_links = temp_cumulative_links
                        seen_node_ids = temp_seen_node_ids
                        seen_links = temp_seen_links
                        completed_batch_indices = temp_completed_batch_indices
                        num_completed = temp_num_completed
                        processed_columns = temp_processed_columns

                        cached_result = {
                            "html_content": html_content,
                            "algorithm_explanation": validated_data.get("algorithm_explanation", ""),
                            "relationship_mapping": validated_data.get("relationship_mapping", ""),
                            "usage_instructions": validated_data.get("usage_instructions", ""),
                            "nodes": validated_data.get("nodes", []),
                            "categories": validated_data.get("categories", []),
                            "model_id": model_id,
                            "processing_info": {
                                "total_columns": total_columns,
                                "processed_columns": processed_columns,
                                "total_batches": total_batches,
                                "completed_batches": num_completed,
                                "status": "complete" if is_complete else "partial",
                            },
                        }

                                                # Validate HTML content and data before caching
                        if not html_content or len(html_content.strip()) < 100:
                            self.logger.error(
                                f"Batch {batch_idx}: Generated HTML is empty or too short ({len(html_content) if html_content else 0} chars), skipping cache update"
                            )
                            continue
                        
                        if len(validated_data.get("nodes", [])) == 0:
                            self.logger.error(
                                f"Batch {batch_idx}: No nodes in validated data, skipping cache update"
                            )
                            continue
                        
                        # Count variable nodes (excluding category nodes)
                        variable_nodes = [
                            n for n in validated_data["nodes"] if n.get("group") != "category"
                        ]
                        
                        if len(variable_nodes) == 0:
                            self.logger.error(
                                f"Batch {batch_idx}: No variable nodes in validated data, skipping cache update"
                            )
                            continue

                        cached_result = {
                            "html_content": html_content,
                            "algorithm_explanation": validated_data.get("algorithm_explanation", ""),
                            "relationship_mapping": validated_data.get("relationship_mapping", ""),
                            "usage_instructions": validated_data.get("usage_instructions", ""),
                            "nodes": validated_data.get("nodes", []),
                            "categories": validated_data.get("categories", []),
                            "model_id": model_id,
                            "processing_info": {
                                "total_columns": total_columns,
                                "processed_columns": processed_columns,
                                "total_batches": total_batches,
                                "completed_batches": num_completed,
                                "status": "complete" if is_complete else "partial",
                            },
                        }

                        set_kg_cache(cache_key, cached_result)
                        
                        self.logger.info(
                            f"Batch {batch_idx} complete: {len(variable_nodes)} total variables, {num_completed}/{total_batches} batches done, cached for dataset {cache_key}"
                        )

                    except Exception as exc:
                        self.logger.error(f"Background batch {batch_idx} failed: {exc}", exc_info=True)
                        continue

            self.logger.info(f"Background processing complete for dataset {cache_key}")

        except Exception as exc:
            self.logger.error(f"Background processing thread failed: {exc}", exc_info=True)

    def _validate_graph_data(self, graph_data: Dict) -> Dict:
        """
        Validate and sanitize knowledge graph data.
        
        Ensures:
        - Required fields are present
        - Data structures are valid
        - Node references are consistent
        - No orphan nodes
        - Valid colors and values
        """
        # Check required top-level fields
        required_fields = ['nodes', 'links', 'categories']
        for field in required_fields:
            if field not in graph_data:
                raise ValueError(f"Missing required field: {field}")
        
        nodes = graph_data['nodes']
        links = graph_data['links']
        categories = graph_data['categories']
        
        # Validate nodes is a list
        if not isinstance(nodes, list) or len(nodes) == 0:
            raise ValueError("Nodes must be a non-empty list")
        
        if not isinstance(links, list):
            raise ValueError("Links must be a list")
        
        if not isinstance(categories, list) or len(categories) == 0:
            raise ValueError("Categories must be a non-empty list")
        
        # Validate and sanitize nodes
        node_ids = set()
        category_names = set()
        validated_nodes = []
        
        for idx, node in enumerate(nodes):
            if not isinstance(node, dict):
                self.logger.warning(f"Skipping invalid node at index {idx}: not a dict")
                continue
            
            # Required node fields
            if 'id' not in node or 'group' not in node:
                self.logger.warning(f"Skipping node at index {idx}: missing id or group")
                continue
            
            node_id = str(node['id'])
            node_ids.add(node_id)
            
            # Track category nodes
            if node.get('group') == 'category':
                category_names.add(node_id)
            
            # Sanitize node
            validated_node = {
                'id': node_id,
                'group': str(node['group']),
                'size': int(node.get('size', 10)),
                'color': self._validate_color(node.get('color', '#999'))
            }
            validated_nodes.append(validated_node)

        # NEW: auto-create missing category nodes instead of skipping them later
        missing_category_nodes = [
            cat for cat in categories
            if isinstance(cat, dict) and 'name' in cat and cat['name'] not in category_names
        ]

        for cat in missing_category_nodes:
            cat_name = str(cat['name'])
            cat_color = self._validate_color(cat.get('color', '#4E79A7'))
            self.logger.warning(
                "Category '%s' referenced in categories list but missing in nodes; auto-injecting node",
                cat_name,
            )
            category_node = {
                'id': cat_name,
                'group': 'category',
                'size': 25,
                'color': cat_color,
            }
            validated_nodes.append(category_node)
            node_ids.add(cat_name)
            category_names.add(cat_name)
             
        if len(validated_nodes) == 0:
            raise ValueError("No valid nodes after validation")
        
        # Validate and sanitize links
        validated_links = []
        for idx, link in enumerate(links):
            if not isinstance(link, dict):
                self.logger.warning(f"Skipping invalid link at index {idx}: not a dict")
                continue
            
            source = str(link.get('source', ''))
            target = str(link.get('target', ''))
            
            # Check if both source and target exist in nodes
            if source not in node_ids:
                self.logger.warning(f"Skipping link at index {idx}: source '{source}' not found in nodes")
                continue
            
            if target not in node_ids:
                self.logger.warning(f"Skipping link at index {idx}: target '{target}' not found in nodes")
                continue
            
            # Sanitize link
            strength = float(link.get('strength', 0.5))
            strength = max(0.0, min(1.0, strength))  # Clamp between 0 and 1
            
            validated_link = {
                'source': source,
                'target': target,
                'strength': strength
            }
            validated_links.append(validated_link)
        
        # Ensure we have at least some links
        if len(validated_links) == 0:
            self.logger.warning("No valid links found, creating default links")
            # Create basic category connections if no links exist
            category_list = list(category_names)
            for i in range(len(category_list) - 1):
                validated_links.append({
                    'source': category_list[i],
                    'target': category_list[i + 1],
                    'strength': 0.5
                })
        
        # Make sure every variable has a category edge
        for node in validated_nodes:
            if node.get('group') == 'category':
                continue
            has_category_link = any(
                link['source'] == node['id'] and link['target'] == node['group']
                for link in validated_links
            )
            if not has_category_link:
                self.logger.warning(
                    f"Node '{node['id']}' missing category link; auto-linking to '{node['group']}'"
                )
                validated_links.append({
                    'source': node['id'],
                    'target': node['group'],
                    'strength': 1.0
                })

        # Validate and sanitize categories
        validated_categories = []
        for idx, cat in enumerate(categories):
            if not isinstance(cat, dict):
                self.logger.warning(f"Skipping invalid category at index {idx}: not a dict")
                continue
            
            if 'name' not in cat:
                self.logger.warning(f"Skipping category at index {idx}: missing name")
                continue
            
            cat_name = str(cat['name'])
            
            # Only include categories that exist as nodes
            if cat_name not in category_names:
                self.logger.warning(f"Skipping category '{cat_name}': not found in nodes")
                continue
            
            validated_cat = {
                'name': cat_name,
                'color': self._validate_color(cat.get('color', '#999'))
            }
            validated_categories.append(validated_cat)
        
        # Ensure we have at least one category
        if len(validated_categories) == 0:
            # Create default categories from category nodes
            for cat_name in category_names:
                validated_categories.append({
                    'name': cat_name,
                    'color': '#4E79A7'
                })
        
        # Build lookup tables so variable/link colours can inherit from categories
        # Pastel palette (reds/blues/oranges/greens/etc) for consistent, vivid categories
        pastel_palette = [
            '#f28b82',  # red
            '#aecbfa',  # blue
            '#fbbc04',  # orange
            '#ccff90',  # green
            '#fdcfe8',  # pink
            '#d7aefb',  # purple
            '#a7ffeb',  # teal
            '#e6c9a8',  # tan
            '#d0b7ff',  # lavender
            '#ffccbc',  # peach
            '#b3e5fc',  # light blue
            '#c8e6c9',  # light green
        ]

        # Assign pastel palette to categories in order (stable + vibrant)
        for idx, cat in enumerate(validated_categories):
            cat['color'] = pastel_palette[idx % len(pastel_palette)]

        category_color_map = {cat['name']: cat['color'] for cat in validated_categories}
        node_color_map = {}
        for node in validated_nodes:
            if node.get('group') == 'category':
                base = category_color_map.get(node['id'], node.get('color'))
                if base:
                    node['color'] = base
                    category_color_map[node['id']] = node['color']
            else:
                base = category_color_map.get(node['group'])
                if base:
                    node['color'] = self._pastel_color(base, mix=0.55, desaturate=0.1)
                else:
                    node['color'] = self._pastel_color(node.get('color', '#4E79A7'), mix=0.55, desaturate=0.1)
            node_color_map[node['id']] = node['color']

        # Recolour links so they’re never “washed out”
        for link in validated_links:
            src_colour = node_color_map.get(link['source'])
            tgt_colour = node_color_map.get(link['target'])
            colour = tgt_colour or src_colour or '#888888'
            # darken a touch so it contrasts against the light node
            link['color'] = self._darken_color(colour, 0.85)
            link['opacity'] = max(0.35, min(0.95, link.get('strength', 0.5) + 0.15))

        # Limit to 100 categories with "Others" consolidation if needed
        MAX_CATEGORIES = 25

        if len(validated_categories) > MAX_CATEGORIES:
            self.logger.warning(f"Too many categories ({len(validated_categories)}), consolidating to {MAX_CATEGORIES}")
            
            # Keep first 99 categories
            kept_categories = validated_categories[:MAX_CATEGORIES - 1]
            dropped_categories = validated_categories[MAX_CATEGORIES - 1:]
            
            # Get the names of dropped categories
            dropped_category_names = set(cat['name'] for cat in dropped_categories)
            
            # Create "Others" category
            others_category = {
                'name': 'Others',
                'color': '#999999'  # Gray color for Others
            }
            
            # Add "Others" category node if it doesn't exist
            others_node_exists = any(n['id'] == 'Others' and n.get('group') == 'category' for n in validated_nodes)
            if not others_node_exists:
                validated_nodes.append({
                    'id': 'Others',
                    'group': 'category',
                    'size': 25,
                    'color': '#999999'
                })
            
            # Reassign variable nodes from dropped categories to "Others"
            for node in validated_nodes:
                if node.get('group') in dropped_category_names and node.get('group') != 'category':
                    self.logger.info(f"Moving variable '{node['id']}' from '{node['group']}' to 'Others'")
                    node['group'] = 'Others'
                    # Update color to match Others category
                    node['color'] = '#CCCCCC'  # Light gray for Others variables
            
            # Update links: change links pointing to dropped categories to point to "Others"
            for link in validated_links:
                if link['target'] in dropped_category_names:
                    self.logger.info(f"Updating link target from '{link['target']}' to 'Others'")
                    link['target'] = 'Others'
            
            # Remove category nodes for dropped categories
            validated_nodes = [
                n for n in validated_nodes 
                if not (n.get('id') in dropped_category_names and n.get('group') == 'category')
            ]
            
            # Update final categories list
            validated_categories = kept_categories + [others_category]
            
            self.logger.info(f"Consolidated {len(dropped_category_names)} categories into 'Others'")
        
        return {
            'nodes': validated_nodes,
            'links': validated_links,
            'categories': validated_categories,
            'algorithm_explanation': graph_data.get('algorithm_explanation', 'Knowledge graph generated successfully'),
            'relationship_mapping': graph_data.get('relationship_mapping', 'Relationships based on domain knowledge and data analysis'),
            'usage_instructions': graph_data.get('usage_instructions', 'Hover over nodes to explore relationships. Use filters to focus on specific categories.')
        }


    def _validate_color(self, color: str) -> str:
        """Validate and return a hex color code, with fallback to default."""
        if not isinstance(color, str):
            return '#999999'
        
        # Remove whitespace
        color = color.strip()
        
        # Check if valid hex color
        if re.match(r'^#[0-9A-Fa-f]{6}$', color):
            return color
        
        # Try to convert CSS color names to hex
        css_colors = {
            'lightblue': '#ADD8E6',
            'lightcoral': '#F08080',
            'lightgreen': '#90EE90',
            'lightgray': '#D3D3D3',
            'lightgrey': '#D3D3D3',
            'lightpink': '#FFB6C1',
            'lightyellow': '#FFFFE0',
            'lightcyan': '#E0FFFF',
            'lightsteelblue': '#B0C4DE',
            'lightsalmon': '#FFA07A',
            'lightseagreen': '#20B2AA',
            'lightskyblue': '#87CEFA',
            'lightslategray': '#778899',
            'lightslategrey': '#778899',
            'lightgoldenrodyellow': '#FAFAD2',
            'lightseagreen': '#20B2AA',
        }
        
        color_lower = color.lower()
        if color_lower in css_colors:
            return css_colors[color_lower]
        
        # Fallback to gray
        self.logger.warning(f"Invalid color '{color}', using fallback")
        return '#999999'


    def _normalize_problem_statement(self, problem_statement: Optional[str]) -> str:
        """Return a normalized problem statement or 'NA' when not provided."""
        normalized = (problem_statement or "").strip()
        return normalized if normalized else "NA"


    def _create_error_response(self, error_title: str, error_detail: str) -> str:
        """Create a user-friendly error response with fallback HTML."""
        error_html = self._get_fallback_html(error_title, error_detail)
        
        result = {
            "html_content": error_html,
            "algorithm_explanation": error_title,
            "relationship_mapping": error_detail,
            "usage_instructions": "An error occurred while generating the knowledge graph. Please try again."
        }
        
        return json.dumps(result)


    def _get_fallback_html(self, title: str, message: str = "") -> str:
        """Generate fallback HTML for error cases."""
        return f"""<!DOCTYPE html>
    <html lang="en">
    <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Knowledge Graph - Error</title>
    <style>
    body {{
        margin: 0;
        padding: 20px;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        background: linear-gradient(135deg, #f0f4f8 0%, #d9e2ec 100%);
        height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
    }}
    .error-container {{
        background: white;
        padding: 40px;
        border-radius: 10px;
        box-shadow: 0 8px 20px rgba(0,0,0,0.1);
        max-width: 600px;
        text-align: center;
    }}
    .error-title {{
        color: #E15759;
        font-size: 24px;
        font-weight: bold;
        margin-bottom: 20px;
    }}
    .error-message {{
        color: #666;
        font-size: 16px;
        line-height: 1.6;
    }}
    .retry-button {{
        margin-top: 20px;
        padding: 12px 24px;
        background: #4E79A7;
        color: white;
        border: none;
        border-radius: 5px;
        font-size: 16px;
        cursor: pointer;
    }}
    .retry-button:hover {{
        background: #3a5a7a;
    }}
    </style>
    </head>
    <body>
    <div class="error-container">
    <div class="error-title">{title}</div>
    <div class="error-message">{message if message else 'Please try again or contact support if the issue persists.'}</div>
    <button class="retry-button" onclick="window.location.reload()">Retry</button>
    </div>
    </body>
    </html>"""

    def get_dataset_type_classification(self, dataset_summary: str) -> Dict[str, Any]:
        """Get dataset type classification from the configured LLM"""
        if not self._check_credentials():
            return "LLM chat configuration is missing. Please configure provider credentials."
        self.logger.debug("Getting dataset type classification response")
        
        sys_prompt = """You are an expert data scientist specializing in dataset type classification for machine learning problems. Your task is to analyze a dataset summary and determine the primary machine learning problem type.

Dataset types to classify:
1. **classification**: Datasets suitable for classification problems (predicting discrete categories/classes)
2. **regression**: Datasets suitable for regression problems (predicting continuous numerical values)
3. **time_series**: Datasets with temporal components requiring time series analysis or forecasting
4. **others**: Datasets that don't fit the above categories (clustering, anomaly detection, etc.)

Classification criteria:
- **Classification**: Target variable is categorical/discrete, binary outcomes, class labels, categorical prediction tasks
- **Regression**: Target variable is continuous/numerical, predicting quantities, amounts, scores, or measurements
- **Time Series**: Contains date/time columns, temporal patterns, sequential data, forecasting requirements
- **Others**: Unsupervised learning tasks, anomaly detection, clustering, or mixed/unclear problem types

Analysis approach:
1. Examine the target variable type and nature
2. Look for temporal patterns and date/time columns
3. Consider the business problem context
4. Assess data structure and variable relationships

Provide:
1. Primary dataset classification based on ML problem type
2. Confidence score (0.0 to 1.0) based on how clearly the dataset fits the type
3. Clear reasoning explaining the classification decision
4. Key characteristics that support the classification
5. Specific recommendations for ML approaches based on the dataset type

Be precise and focus on the machine learning problem type rather than just data characteristics."""
        
        prompt = f"""Analyze this dataset summary and classify its primary machine learning problem type:

{dataset_summary}

Classify the dataset as one of: classification, regression, time_series, or others.

Consider:
- Target variable type and nature (if specified)
- Presence of temporal/date columns
- Business problem context
- Data structure and variable relationships
- Typical machine learning use cases

Focus on determining the most appropriate machine learning approach for this dataset.
Provide detailed analysis with confidence scoring and actionable ML recommendations."""
        
        try:
            formatted_messages = [
                {
                    "role": "system",
                    "content": [{"type": "text", "text": sys_prompt}]
                },
                {
                    "role": "user", 
                    "content": [{"type": "text", "text": prompt}]
                }
            ]
            start_time = time.time()
            self.logger.info(f"start time: {start_time}")   
            response = self._call_chat_completion(
                context="objectives_classification",
                messages=formatted_messages,
                temperature=0.1,
                response_format=DatasetTypeClassificationLLMResponse
            )
            end_time = time.time()
            self.logger.info(f"end time: {time.time()}")
            self.logger.info(f"time taken: {end_time - start_time}")
            structured = self._normalize_structured_response(response)

            if isinstance(structured, dict):
                self.logger.debug("Dataset type classification response generated successfully")
                return structured

            text = structured if isinstance(structured, str) else self._extract_response_text(response)
            if not text:
                raise ValueError("Dataset type classification response is empty")

            try:
                parsed = self._safe_json_load(text)
                if not isinstance(parsed, dict):
                    raise ValueError("Parsed response is not a dictionary")
                self.logger.debug("Dataset type classification response generated successfully")
                return parsed
            except ValueError as exc:
                self.logger.info("Falling back to text-based dataset classification response (%s)", exc)
                return self._build_dataset_type_fallback(text)
            
        except Exception as e:
            self.logger.error(f"Failed to get dataset type classification: {str(e)}")
            raise
    
    async def generate_text(self, prompt: str, max_tokens: int = 500, temperature: float = 0.3, context: str = "model_documentation") -> str:
        """Generate text response from the configured LLM"""
        if not self._check_credentials():
            return "LLM chat configuration is missing. Please configure provider credentials."

        self.logger.debug(f"Generating text with prompt length: {len(prompt)}")

        try:
            formatted_messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ]

            response = self._call_chat_completion(
                context=context,
                messages=formatted_messages,
                temperature=temperature,
                max_tokens=max_tokens
            )

            content = self._extract_response_text(response)
            self.logger.debug("Text generated successfully")
            return content

        except Exception as e:
            self.logger.error(f"Failed to generate text: {str(e)}")
            raise

    def get_embeddings(self, inputs: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of strings using the configured embedding provider"""
        config, _, _ = self._resolve_embedding_config()
        if not config.is_ready():
            raise ValueError("Embedding LLM configuration is missing.")

        settings.apply_provider_environment(config.provider)
        req = _build_litellm_kwargs(config, {"input": inputs})
        t0 = time.perf_counter()
        response: Any = None
        err_type: Optional[str] = None
        embeddings: List[List[float]] = []
        try:
            response = embedding(**req)
            for entry in response.data:
                vector = getattr(entry, "embedding", None)
                if vector is None and isinstance(entry, dict):
                    vector = entry.get("embedding")
                if vector is not None:
                    embeddings.append(vector)
            return embeddings
        except Exception as e:
            err_type = type(e).__name__
            raise
        finally:
            duration_ms = round((time.perf_counter() - t0) * 1000, 2)
            self._emit_llm_call_log(
                usage="embedding",
                config=config,
                duration_ms=duration_ms,
                success=err_type is None,
                error_type=err_type,
                request_kwargs=req,
                response=response,
                embedding_inputs=inputs,
            )

# Global LLM service instance
llm_service = LLMService()
