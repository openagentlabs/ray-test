#!/usr/bin/env python3
"""
Startup script for MIDAS FastAPI Backend
"""

import uvicorn
import os
import sys
from pathlib import Path

def main():
    """Start the FastAPI server"""

    # Check if we're in a virtual environment, if not, try to use venv
    if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        venv_python = Path("./venv/Scripts/python.exe")
        if venv_python.exists():
            print(f"Switching to virtual environment: {venv_python}")
            os.execv(str(venv_python), [str(venv_python), __file__] + sys.argv[1:])

    # Check if .env file exists
    env_file = Path(".env")
    if not env_file.exists():
        print("Warning: .env file not found. Please create one with your Azure OpenAI credentials.")
        print("Required environment variables:")
        print("- ENDPOINT: Azure OpenAI endpoint")
        print("- API_KEY: Azure OpenAI API key")
        print("- MODEL: Azure OpenAI model name")
    
    # Start server
    print("Starting MIDAS FastAPI Backend...")
    print("API Documentation will be available at: http://localhost:8000/docs")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

if __name__ == "__main__":
    main()
