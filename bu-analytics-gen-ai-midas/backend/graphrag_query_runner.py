"""
GraphRAG Query Runner - Must be run with Python 3.12
This script is called by graphrag_service.py as a subprocess
Uses the graphrag executable from the venv Scripts directory
"""
import argparse
import json
import sys
import os
import subprocess
from pathlib import Path

def run_query(root_dir: str, query: str, method: str = "local", max_tokens: int = 5000):
    """Run GraphRAG query using the graphrag CLI executable"""
    try:
        # Verify AI Gateway credentials – settings.yaml reads these at query time
        gateway_key = os.getenv("LLM_GATEWAY_VIRTUAL_KEY")
        gateway_url = os.getenv("LLM_GATEWAY_URL")
        if not gateway_key or not gateway_url:
            error_output = {
                "success": False,
                "context": "",
                "error": "LLM_GATEWAY_URL / LLM_GATEWAY_VIRTUAL_KEY environment variables not set",
            }
            print(json.dumps(error_output))
            return 1
        
        root = Path(root_dir)
        
        # Check if output directory exists
        output_dir = root / "output"
        if not output_dir.exists():
            error_output = {
                "success": False,
                "context": "",
                "error": f"GraphRAG output directory not found at {output_dir}"
            }
            print(json.dumps(error_output))
            return 1
        
        # Get the directory where this Python executable is located
        python_dir = Path(sys.executable).parent
        
        # Construct path to graphrag executable in the same Scripts directory
        graphrag_exe = python_dir / "graphrag.exe"
        
        # If .exe doesn't exist, try without extension (Unix-like systems)
        if not graphrag_exe.exists():
            graphrag_exe = python_dir / "graphrag"
        
        # If still not found, try using python -m graphrag.cli
        if not graphrag_exe.exists():
            # Use python -m to run graphrag as a module
            cmd = [
                str(sys.executable),
                "-m", "graphrag.cli",
                "query",
                "--root", str(root),
                "--method", method,
                "--query", query
            ]
        else:
            # Use the graphrag executable directly
            cmd = [
                str(graphrag_exe),
                "query",
                "--root", str(root),
                "--method", method,
                "--query", query
            ]
        
        # Run the GraphRAG command
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1200,
            cwd=str(root),
            env=os.environ.copy()
        )
        
        # Check return code
        if result.returncode != 0:
            error_msg = result.stderr.strip() if result.stderr else result.stdout.strip()
            if not error_msg:
                error_msg = f"GraphRAG command exited with code {result.returncode}"
            
            error_output = {
                "success": False,
                "context": "",
                "error": f"GraphRAG CLI error: {error_msg}"
            }
            print(json.dumps(error_output))
            return 1
        
        # Success - extract the response
        response_text = result.stdout.strip()
        
        if not response_text:
            error_output = {
                "success": False,
                "context": "",
                "error": "GraphRAG returned empty response"
            }
            print(json.dumps(error_output))
            return 1
        
        # Clean up the response - remove log lines and progress indicators
        lines = response_text.split('\n')
        cleaned_lines = []
        
        skip_indicators = [
            'info:', 'debug:', 'warning:', 'error:',
            'creating', 'reading', 'loading', 'processing',
            '⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏',
            '100%', '|', '━', '█'
        ]
        
        for line in lines:
            line_lower = line.lower().strip()
            
            # Skip empty lines
            if not line_lower:
                continue
            
            # Skip log lines
            is_log_line = any(indicator in line_lower for indicator in skip_indicators)
            
            if not is_log_line:
                cleaned_lines.append(line)
        
        # Join cleaned lines
        if cleaned_lines:
            response_text = '\n'.join(cleaned_lines).strip()
        
        # If cleaning removed everything, use original
        if not response_text or len(response_text) < 10:
            response_text = result.stdout.strip()
        
        # Extract content after common markers
        markers = ['SUCCESS:', 'Response:', 'Answer:', 'Result:']
        for marker in markers:
            if marker in response_text:
                parts = response_text.split(marker, 1)
                if len(parts) > 1 and parts[1].strip():
                    response_text = parts[1].strip()
                    break
        
        output = {
            "success": True,
            "context": response_text,
            "method": method
        }
        
        print(json.dumps(output))
        return 0
        
    except subprocess.TimeoutExpired:
        error_output = {
            "success": False,
            "context": "",
            "error": "GraphRAG query timeout after 120 seconds"
        }
        print(json.dumps(error_output))
        return 1
        
    except Exception as e:
        error_output = {
            "success": False,
            "context": "",
            "error": f"Unexpected error: {str(e)}"
        }
        print(json.dumps(error_output))
        return 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run GraphRAG query via CLI")
    parser.add_argument("--root", required=True, help="Root directory of GraphRAG project")
    parser.add_argument("--query", required=True, help="Query string")
    parser.add_argument("--method", default="local", choices=["local", "global"], help="Search method")
    parser.add_argument("--max-tokens", type=int, default=5000, help="Max tokens for response")
    
    args = parser.parse_args()
    
    sys.exit(run_query(args.root, args.query, args.method, args.max_tokens))