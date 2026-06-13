"""
LLM-based relevance validation helpers
"""
import json
from typing import Dict, Any
from app.core.logging_config import get_logger

logger = get_logger(__name__)


def build_llm_validation_prompt(query: str, agent_prompt: str) -> str:
    """
    Build prompt for LLM to validate query relevance
    """
    prompt = f"""You are analyzing if a user query is relevant to an AI agent.

AGENT ROLE AND CAPABILITIES:
{agent_prompt}

USER QUERY: "{query}"

Analyze this query and determine if it is relevant to the agent's role and capabilities.

Respond in JSON format:
{{
    "relevant": true/false,
    "relevance_level": "fully_relevant" | "partially_relevant" | "not_relevant",
    "relevant_parts": ["list of relevant parts or empty if none"],
    "irrelevant_parts": ["list of irrelevant parts or empty if all relevant"],
    "filtered_query": "query with only relevant parts, or original if fully relevant",
    "guidance": "helpful message guiding user, or null if fully relevant"
}}

GUIDANCE FORMAT RULES:
- For partially_relevant: "Please note that I cannot assist you with [irrelevant parts] as that is out of my training scope. Would you like me to proceed with [relevant parts]?"
- For not_relevant: "I am a [Agent Name]. I can help you with [list key capabilities from agent prompt]. Could you please rephrase your question related to these capabilities?"
- For fully_relevant: null

IMPORTANT:
- Be strict: Only mark as relevant if query clearly relates to agent's capabilities
- If query is about general topics (weather, news, etc.) → not_relevant
- If query mixes relevant and irrelevant parts → partially_relevant
"""
    return prompt


def parse_llm_response(llm_response: str) -> Dict[str, Any]:
    """
    Parse LLM JSON response with error handling
    """
    try:
        # Try to extract JSON from response
        response_text = llm_response.strip()
        
        # If response is wrapped in markdown code blocks, extract JSON
        if "```" in response_text:
            # Extract JSON from code block
            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            if start >= 0 and end > start:
                response_text = response_text[start:end]
        
        # Parse JSON
        result = json.loads(response_text)
        
        # Validate required fields
        if "relevant" not in result:
            result["relevant"] = result.get("relevance_level") != "not_relevant"
        
        if "relevance_level" not in result:
            result["relevance_level"] = "fully_relevant" if result.get("relevant") else "not_relevant"
        
        return result
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        logger.error(f"Response was: {llm_response[:500]}")
        return handle_timeout()
    except Exception as e:
        logger.error(f"Error parsing LLM response: {e}")
        return handle_timeout()


def handle_timeout() -> Dict[str, Any]:
    """
    Return default response on timeout or error
    """
    return {
        "relevant": True,  # Allow through on error (fail open)
        "relevance_level": "fully_relevant",
        "relevant_parts": [],
        "irrelevant_parts": [],
        "filtered_query": None,
        "guidance": None
    }

