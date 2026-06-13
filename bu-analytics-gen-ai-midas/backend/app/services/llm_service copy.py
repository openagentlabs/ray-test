import os
import json
from typing import List, Dict, Any, Optional, Union, Literal
from openai import AzureOpenAI
from pydantic import BaseModel, Field
from app.core.config import settings
from app.core.logging_config import get_logger
import time 

class resp(BaseModel):
    name: str
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

class Plan(BaseModel):    
    missing_values: Optional[list[resp]] = None
    outliers: Optional[list[resp]] = None
    class_imbalance: Optional[list[resp]] = None
    correlation: Optional[list[resp]] = None
    EDA: Optional[list[resp]] = None

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

class KnowledgeGraphResponse(BaseModel):
    html_content: str
    algorithm_explanation: str
    relationship_mapping: str
    usage_instructions: str

class DatasetTypeClassificationLLMResponse(BaseModel):
    dataset_type: str  # "classification", "regression", "time_series", "others"
    confidence: float  # 0.0 to 1.0
    reasoning: str
    characteristics: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)

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
    'correlation_matrix': 'llm_correlation_matrix_insight'
}

class LLMService:
    def __init__(self):
        self.logger = get_logger(__name__)
        self.llm = AzureOpenAI(
            azure_endpoint=settings.AZURE_ENDPOINT,
            api_key=settings.AZURE_API_KEY,
            api_version=settings.AZURE_API_VERSION,
        )
        self.logger.info("LLMService initialized")

        
        #KG
        self.llm_KG = AzureOpenAI(
            azure_endpoint=settings.AZURE_KG_ENDPOINT,
            api_key=settings.AZURE_API_KEY_EMBEDDING,
            api_version=settings.AZURE_KG_API_VERSION,  
        )
         
        self.logger.info("LLMService initialized for KG")
    
    def get_response(self, sys_prompt: str, prompt: str, messages: List[Dict[str, Any]]) -> str:
        """Get response from Azure OpenAI with structured output"""
        self.logger.debug(f"Getting structured response with {len(messages)} messages")
        
        try:
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
            ] + messages

            response = self.llm.chat.completions.parse(
                model=settings.AZURE_MODEL,
                messages=formatted_messages,
                temperature=0.1,
                stop=None,
                response_format=Plan
            )
            
            content = response.choices[0].message.content.strip()
            self.logger.debug("Structured response generated successfully")
            return content
            
        except Exception as e:
            self.logger.error(f"Failed to get structured response: {str(e)}")
            raise
    
    def get_response_route(self, prompt: str, messages: List[Dict[str, Any]]) -> str:
        """Get routing response from Azure OpenAI"""
        self.logger.debug("Getting routing response")
        
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

            response = self.llm.chat.completions.create(
                model=settings.AZURE_MODEL,
                messages=formatted_messages,
                temperature=0.1,
                stop=None,
                stream=False
            )
            
            content = response.choices[0].message.content.strip()
            self.logger.debug("Routing response generated successfully")
            return content
            
        except Exception as e:
            self.logger.error(f"Failed to get routing response: {str(e)}")
            raise
    
    def get_data_response(self, prompt: str, messages: List[Dict[str, Any]]) -> str:
        """Get data analysis response from Azure OpenAI with structured output"""
        self.logger.debug(f"Getting data response with {len(messages)} messages")
        
        try:
            # Add the current prompt to the messages
            formatted_messages = messages + [
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
            
            response = self.llm.chat.completions.parse(
                model=settings.AZURE_MODEL,
                messages=formatted_messages,
                temperature=0.1,
                stop=None,
                response_format=DataResponse
            )
            
            content = response.choices[0].message.content.strip()
            self.logger.debug("Data response generated successfully")
            return content
            
        except Exception as e:
            self.logger.error(f"Failed to get data response: {str(e)}")
            raise

    # ---------- Unified Insight Generation ----------
    def get_insight(self, insight_type: str, sys_prompt: str, prompt: str, messages: List[Dict[str, Any]]) -> List[str]:
        """
        Unified method for generating insights of any type.
        
        Args:
            insight_type: Type of insight ('bivariate', 'correlation', 'vif', 'iv', 'correlation_matrix')
            sys_prompt: System prompt for the LLM
            prompt: User prompt with analysis data
            messages: Chat history for context
            
        Returns:
            List of insight strings
        """
        try:
            # Format messages consistently
            formatted_messages = [
                {"role": "system", "content": [{"type": "text", "text": sys_prompt}]}
            ] + messages + [
                {"role": "user", "content": [{"type": "text", "text": prompt}]}
            ]
            
            # Use structured output for consistency
            response = self.llm.chat.completions.parse(
                model=settings.AZURE_MODEL,
                messages=formatted_messages,
                temperature=0.1,
                stop=None,
                response_format=GenericInsightResponse
            )
            
            content = response.choices[0].message.content
            try:
                parsed = json.loads(content)
                # Try the generic 'insights' key first
                insights = parsed.get("insights", [])
                if isinstance(insights, list) and insights:
                    return [str(x) for x in insights if str(x).strip()]
                
                # Fallback to the specific insight type key for backward compatibility
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

    def get_variable_classification(self, dataset_summary: str) -> str:
        """Get variable classification response from Azure OpenAI with structured output"""
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
            
            response = self.llm.chat.completions.parse(
                model=settings.AZURE_MODEL,
                messages=formatted_messages,
                temperature=0.1,
                stop=None,
                response_format=VariableClassificationResponse
            )
            
            content = response.choices[0].message.content.strip()
            self.logger.debug("Variable classification response generated successfully")
            return content
            
        except Exception as e:
            self.logger.error(f"Failed to get variable classification: {str(e)}")
            raise

    def get_knowledge_graph(self, data_dictionary: str) -> str:
        """Get knowledge graph visualization from Azure OpenAI with structured output"""
        self.logger.debug("Getting knowledge graph response")
        
        sys_prompt = """you are an excellent visualizer for knowledge graph generation . now your task is to create a knowledge graph that takes Data_description as an input and generate knowledge graph from this  

now use the below template in which the graph will be present 
```<!DOCTYPE html>  
<html lang="en">  
<head>  
<meta charset="UTF-8" />  
<meta name="viewport" content="width=device-width, initial-scale=1" />  
<title>Generalized Force-Directed Knowledge Graph</title>  
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>  
<style>  
  body {  
    margin: 0; padding: 20px;  
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;  
    background: linear-gradient(135deg, #f0f4f8 0%, #d9e2ec 100%);  
    height: 100vh;  
    overflow: hidden;  
  }  
  #graph {  
    width: 100%;  
    height: 90vh;  
    border-radius: 10px;  
    background: white;  
    box-shadow: 0 8px 20px rgba(0,0,0,0.1);  
  }  
  .node {  
    cursor: pointer;  
    stroke: #fff;  
    stroke-width: 1.5px;  
    transition: filter 0.3s ease;  
  }  
  .node:hover {  
    filter: brightness(1.3);  
  }  
  .label {  
    font-size: 12px;  
    font-weight: 600;  
    fill: #333;  
    pointer-events: none;  
    text-shadow: 1px 1px 2px rgba(255,255,255,0.8);  
  }  
  .link {  
    stroke: #999;  
    stroke-opacity: 0.6;  
    transition: stroke-opacity 0.3s ease;  
  }  
  .link.highlighted {  
    stroke: #ff7f50;  
    stroke-opacity: 1;  
    stroke-width: 3px;  
  }  
  .tooltip {  
    position: absolute;  
    pointer-events: none;  
    background: rgba(0,0,0,0.8);  
    color: white;  
    padding: 8px 12px;  
    border-radius: 6px;  
    font-size: 13px;  
    line-height: 1.4;  
    max-width: 280px;  
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);  
    opacity: 0;  
    transition: opacity 0.2s ease;  
  }  
</style>  
</head>  
<body>  
//placeholder for placing the graph
<div id="graph"></div>  
<div class="tooltip" id="tooltip"></div>  
  
<script>  
  // Sample data (you can replace with your own)  
  const nodesData = [  
    { id: 'Category A', group: 'category', size: 25, color: '#4E79A7' },  
    { id: 'Category B', group: 'category', size: 25, color: '#F28E2B' },  
    { id: 'Node 1', group: 'A', size: 10, color: '#A0CBE8' },  
    { id: 'Node 2', group: 'A', size: 10, color: '#A0CBE8' },  
    { id: 'Node 3', group: 'B', size: 10, color: '#FFBE7D' },  
    { id: 'Node 4', group: 'B', size: 10, color: '#FFBE7D' },  
  ];  
  const linksData = [  
    { source: 'Node 1', target: 'Category A', strength: 1 },  
    { source: 'Node 2', target: 'Category A', strength: 1 },  
    { source: 'Node 3', target: 'Category B', strength: 1 },  
    { source: 'Node 4', target: 'Category B', strength: 1 },  
    { source: 'Node 1', target: 'Node 2', strength: 0.7 },  
    { source: 'Node 3', target: 'Node 4', strength: 0.7 },  
  ];  
  
  const width = document.getElementById('graph').clientWidth;  
  const height = document.getElementById('graph').clientHeight;  
  
  const svg = d3.select('#graph').append('svg')  
    .attr('width', width)  
    .attr('height', height)  
    .call(d3.zoom().scaleExtent([0.1, 4]).on('zoom', (event) => {  
      g.attr('transform', event.transform);  
    }));  
  
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
  const link = g.append('g')  
    .attr('stroke', '#999')  
    .attr('stroke-opacity', 0.6)  
    .selectAll('line')  
    .data(linksData)  
    .join('line')  
    .attr('class', 'link')  
    .attr('stroke-width', d => 1.5 + d.strength * 2);  
  
  // Draw nodes  
  const node = g.append('g')  
    .selectAll('circle')  
    .data(nodesData)  
    .join('circle')  
    .attr('class', 'node')  
    .attr('r', d => d.size)  
    .attr('fill', d => d.color)  
    .call(drag(simulation));  
  
  // Labels  
  const label = g.append('g')  
    .selectAll('text')  
    .data(nodesData)  
    .join('text')  
    .attr('class', 'label')  
    .attr('text-anchor', 'middle')  
    .attr('dy', d => d.group === 'category' ? 6 : 4)  
    .text(d => d.id);  
  
  // Hover interactions  
  node.on('mouseover', (event, d) => {  
    // Highlight connected nodes and links  
    const connectedNodes = new Set();  
    linksData.forEach(l => {  
      if (l.source.id === d.id || l.source === d.id) connectedNodes.add(l.target.id || l.target);  
      if (l.target.id === d.id || l.target === d.id) connectedNodes.add(l.source.id || l.source);  
    });  
    connectedNodes.add(d.id);  
  
    node.style('opacity', n => connectedNodes.has(n.id) ? 1 : 0.2);  
    label.style('opacity', n => connectedNodes.has(n.id) ? 1 : 0.2);  
    link.style('stroke-opacity', l =>   
      l.source.id === d.id || l.source === d.id || l.target.id === d.id || l.target === d.id ? 1 : 0.1);  
    link.classed('highlighted', l =>  
      l.source.id === d.id || l.source === d.id || l.target.id === d.id || l.target === d.id);  
  
    // Show tooltip  
    tooltip.style('opacity', 1)  
      .html(`<strong>${d.id}</strong><br>Group: ${d.group}`)  
      .style('left', (event.pageX + 15) + 'px')  
      .style('top', (event.pageY - 28) + 'px');  
  })  
  .on('mouseout', () => {  
    node.style('opacity', 1);  
    label.style('opacity', 1);  
    link.style('stroke-opacity', 0.6);  
    link.classed('highlighted', false);  
    tooltip.style('opacity', 0);  
  });  
  
  // Drag functions  
  function drag(simulation) {  
    function dragstarted(event, d) {  
      if (!event.active) simulation.alphaTarget(0.3).restart();  
      d.fx = d.x;  
      d.fy = d.y;  
    }  
    function dragged(event, d) {  
      d.fx = event.x;  
      d.fy = event.y;  
    }  
    function dragended(event, d) {  
      if (!event.active) simulation.alphaTarget(0);  
      // Keep category nodes fixed after drag, others free  
      if (d.group !== 'category') {  
        d.fx = null;  
        d.fy = null;  
      }  
    }  
    return d3.drag()  
      .on('start', dragstarted)  
      .on('drag', dragged)  
      .on('end', dragended);  
  }  
  
  // Simulation tick update  
  function ticked() {  
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
      .attr('y', d => d.y);  
  }  
  
  // Responsive resize  
  window.addEventListener('resize', () => {  
    const w = document.getElementById('graph').clientWidth;  
    const h = document.getElementById('graph').clientHeight;  
    svg.attr('width', w).attr('height', h);  
    simulation.force('center', d3.forceCenter(w / 2, h / 2));  
    simulation.alpha(1).restart();  
  });  
</script>  
</body>  
</html>  
```

below are the instruction for appearance to the graph

<Instructions>
Create an interactive, visually appealing knowledge graph that represents semantic metadata variables and their inferred relationships. The graph should have the following features and appearance:

Nodes:

Category Nodes: Larger, distinctively colored circular nodes representing inferred categories of metadata variables (e.g., Identifiers, Temporal, Locational, Quantitative, Categorical, System).
Variable Nodes: Smaller circular nodes representing individual metadata variables, colored to match their assigned category.
Nodes should have smooth hover effects that brighten the node to indicate interactivity.
Each node should display a label with the variable or category name in a clean, readable font.
Edges (Links):

Category Links: Light, subtle lines connecting variable nodes to their category node.
Relationship Links: Stronger, more prominent lines connecting variable nodes that share a semantic or structural relationship based on similarity analysis.
Relationship links should be visually distinct with thicker stroke and color highlight (e.g., coral or orange) on hover or when connected to the hovered node.
Links should have smooth opacity transitions to highlight connected relationships on node hover and fade unrelated links and nodes.
Layout and Interaction:

Use a force-directed layout that dynamically positions nodes and links for clarity and minimal overlap.
Category nodes should be spaced evenly around the graph, with variable nodes clustering around their categories.
Implement smooth zoom and pan controls so users can explore the graph intuitively.
Nodes should be draggable, allowing users to manually adjust positions. Category nodes remain fixed once dragged.
On hovering over a node, show a tooltip near the cursor with the node's name, category, and a descriptive summary.
Highlight the hovered node and all nodes and links directly connected to it, dimming unrelated parts of the graph.
Controls and Filters:

Provide a dropdown filter to select and highlight a specific category, fading out unrelated nodes and links.
A reset button to restore the default view, zoom, and filters.
Styling:

Use a modern, clean color palette with distinct colors for each category.
The background should be a subtle gradient or light color to emphasize the graph.
Node labels should have subtle text shadows for readability.
Tooltips should have a dark translucent background with white text and slight rounded corners.
Performance and Usability:

The graph should smoothly update when filters or thresholds change, with animated transitions.
Interaction and layout should remain responsive for datasets of moderate size.
Provide clear visual feedback for user interactions such as hovering, dragging, and filtering.

</Instructions>


            """
        
        prompt = f"""Generate a comprehensive knowledge graph in html format which will be replaced placeholder present in system prompt, focused on borrower and loan-related data for business analysis and decision-making. The graph should include multiple categories that capture different dimensions of borrower profiles, loan characteristics, and credit behavior. In addition to the following example 
 
    **strictly look for the relationship amongst the categories if they are related then connect them **

    categories:
    Borrower Credit History
    Borrower Demographics
    Borrower Financial Ratios
    Credit Inquiries & Account Openings
    Credit Utilization & Balances
    Identification & Metadata
    Loan Details
    Loan Listing & Application Info
    Loan Performance Metrics
    Please expand and include new business-driven categories that reflect broader or deeper aspects of borrower and loan data, such as:

    Employment & Income Verification: Employment status, income sources, verification status
    Collateral & Security Details: Collateral types, valuations, liens
    Repayment Behavior & Patterns: Payment timeliness, prepayment, defaults
    Risk Assessment & Scoring Models: Risk scores, model outputs, risk factors
    Customer Interaction & Communication: Contact history, complaint records, support tickets
    Market & Economic Indicators: Interest rates, market trends impacting loan performance
    Regulatory & Compliance Data: KYC/AML checks, legal flags, audit logs
    Loan Servicing & Modification History: Restructuring, refinancing, loan extensions
    Fraud Detection & Alerts: Suspicious activity flags, fraud investigation outcomes



            <DATA DESCRIPTION>
            {data_dictionary}
            </DATA DESCRIPTION>

            <Additional Instructions>
            1. Important!! **Check for any error in the node mapping**
            2. Important!! **Check if all nodes mentioned in the graph are defined or present**
            3. Important!! **Check for any errors in the generated code**
            4. Apply graph layout algorithms like force-directed, hierarchical or circular layouts to optimize spacing and reduce overlapping connections
            5. Enable algorithmic node spreading to prevent tightly packed regions and make individual categories easier to distinguish
            6. Adjust edge thickness or transparency to de-emphasize less important relationships, drawing attention to key business links
            </Additional Instructions>
            """
        self.logger.info(f"Prompt: {prompt}")
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
            
            response = self.llm_KG.chat.completions.parse(
                model=settings.KG_MODEL,
                messages=formatted_messages,
                temperature=0.0,
                max_tokens=32768,
                top_p=1,
                stop=None,
                response_format=KnowledgeGraphResponse
            )


            self.logger.info("res:",response)
            content = response.choices[0].message.content.strip()
            self.logger.debug("Knowledge graph response generated successfully")
            return content
            
        except Exception as e:
            self.logger.error(f"Failed to get knowledge graph response: {str(e)}")
            raise

    def get_dataset_type_classification(self, dataset_summary: str) -> str:
        """Get dataset type classification from Azure OpenAI with structured output"""
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
            
            response = self.llm.chat.completions.parse(
                model=settings.AZURE_MODEL,
                messages=formatted_messages,
                temperature=0.1,
                stop=None,
                response_format=DatasetTypeClassificationLLMResponse
            )
            
            content = response.choices[0].message.content.strip()
            self.logger.debug("Dataset type classification response generated successfully")
            return content
            
        except Exception as e:
            self.logger.error(f"Failed to get dataset type classification: {str(e)}")
            raise

# Global LLM service instance
llm_service = LLMService()
