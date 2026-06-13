"""
Launcher script for GraphRAG service
This should be run with Python 3.12
"""
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env file before checking environment variables
try:
    from dotenv import load_dotenv
    # Load .env from backend directory
    backend_dir = Path(__file__).parent.parent
    env_file = backend_dir / ".env"
    if env_file.exists():
        load_dotenv(env_file)
        print(f"Loaded .env file from: {env_file}")
    else:
        print(f"WARNING: .env file not found at: {env_file}")
except ImportError:
    print("WARNING: python-dotenv not installed. Environment variables must be set manually.")
except Exception as e:
    print(f"WARNING: Error loading .env file: {e}")

# Verify Python version
if sys.version_info < (3, 12) or sys.version_info >= (3, 13):
    print(f"ERROR: This service requires Python 3.12, found {sys.version}")
    sys.exit(1)

# Verify environment – GraphRAG now uses the AI Gateway virtual key
if not os.getenv("LLM_GATEWAY_VIRTUAL_KEY"):
    print("WARNING: LLM_GATEWAY_VIRTUAL_KEY not set (check .env file)")
else:
    print("✓ LLM_GATEWAY_VIRTUAL_KEY loaded successfully")
if not os.getenv("LLM_GATEWAY_URL"):
    print("WARNING: LLM_GATEWAY_URL not set (check .env file)")

# Start the service
if __name__ == "__main__":
    from graphrag_service.server import app
    import uvicorn
    
    port = int(os.getenv("GRAPHRAG_SERVICE_PORT", "8001"))
    print(f"Starting GraphRAG service on port {port} (Python {sys.version})")
    uvicorn.run(app, host="0.0.0.0", port=port)