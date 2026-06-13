# !/bin/bash

# Navigate to correct directory
cd /site/wwwroot

# Install dependencies
python3 -m pip install -r requirements.txt 

# Run the application
uvicorn main:app --host 0.0.0.0 --port 8000