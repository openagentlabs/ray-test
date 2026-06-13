# MIDAS FastAPI Backend

A modularized FastAPI backend for the MIDAS (Model Intelligent Data Analysis System) that provides data analysis capabilities through an agentic workflow powered by LangGraph and Azure OpenAI.

## Features

- **Dataset Upload & Management**: Upload CSV datasets with configuration parameters
- **Agentic Analysis**: Multi-agent workflow using LangGraph for intelligent data analysis
- **Persistent Chat State**: SQLite-based MessageState persistence for maintaining conversation context across sessions
- **Vector Store Integration**: FAISS-based vector store with Azure OpenAI embeddings for knowledge base retrieval
- **RESTful API**: Clean, documented API endpoints for easy integration
- **Modular Architecture**: Well-structured, maintainable codebase
- **Comprehensive Logging**: Structured logging with file and console output for debugging and monitoring

## Architecture

```
backend/
├── main.py                 # FastAPI application entry point
├── app/
│   ├── api/
│   │   └── routes.py      # API route definitions
│   ├── core/
│   │   └── config.py      # Configuration settings
│   ├── models/
│   │   ├── schemas.py     # Pydantic models for request/response
│   │   └── database.py    # SQLite database models for persistence
│   ├── services/
│   │   ├── agentic_system.py        # LangGraph agentic workflow
│   │   ├── dataset_service.py       # Dataset management
│   │   ├── llm_service.py           # Azure OpenAI integration
│   │   ├── message_state_service.py # MessageState persistence management
│   │   └── vector_store.py          # FAISS vector store
│   └── utils/
│       └── helpers.py     # Utility functions
├── requirements.txt        # Python dependencies
└── README.md             # This file
```

## Prerequisites

- Python 3.8+
- Azure OpenAI API access
- Knowledge base JSON file

## Installation

1. **Clone the repository and navigate to backend directory:**
   ```bash
   cd backend
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   Create a `.env` file in the backend directory:
   ```env
   ENDPOINT=your_azure_openai_endpoint
   API_KEY=your_azure_openai_api_key
   MODEL=your_azure_openai_model_name
       EMBEDDING_ENDPOINT=your_azure_openai_endpoint
    EMBEDDING_MODEL=text-embedding-ada-002
    ```

5. **Vector Store:**
   The system will automatically create a FAISS vector store from your knowledge base JSON file on first startup. The vector store is created only once and reused for all subsequent requests.

6. **Logging:**
   Logs are automatically written to `logs/midas.log` and displayed in the console. You can configure logging levels and output in your `.env` file.

7. **HTTP rate limiting (optional):** Fixed-window limits apply to all non-exempt routes. Values are read **only** from **`RATE_LIMIT_*` environment variables** (set in **`backend/.env`**; see **`.env.example`**). If `RATE_LIMIT_ENABLED` is omitted or false, limits are off. If `RATE_LIMIT_ENABLED` is true, **every** limit variable in `.env.example` must be set (no in-code defaults). Counters use `REDIS_URL` or `RATE_LIMIT_REDIS_URL` when set; otherwise an in-process store is used. On store errors, requests are allowed (fail open).

   | Variable | Purpose |
   |----------|---------|
   | `RATE_LIMIT_ENABLED` | `true` / `false` - if not set, rate limiting is disabled |
   | `RATE_LIMIT_WINDOW_SECONDS` | Window length (seconds) |
   | `RATE_LIMIT_DEFAULT_MAX` | General API traffic |
   | `RATE_LIMIT_AUTH_MAX` | Login, register, refresh, verify-token |
   | `RATE_LIMIT_LLM_MAX` | Chat, insights, training, documentation LLM, etc. |
   | `RATE_LIMIT_POLL_MAX` | `*/status/*`, keepalive, progress-style polling |
   | `RATE_LIMIT_UPLOAD_MAX` | Upload and heavy dataset prep routes |
   | `RATE_LIMIT_TRUST_PROXY` | `true` / `false` - trust `X-Forwarded-For` for client IP |
   | `RATE_LIMIT_REDIS_URL` | Optional; otherwise uses `REDIS_URL` |

   Quick manual test: set `RATE_LIMIT_ENABLED=true` and all required `RATE_LIMIT_*` keys, set `RATE_LIMIT_LLM_MAX=3` (the script hits `/api/v1/llm-config`, **llm** bucket), restart the server, run `python scripts/test_rate_limit.py`. Use `MIDAS_TEST_TOKEN` if you point `RATE_LIMIT_TEST_PATH` at a protected route.

## Usage

### Starting the Server

```bash
# Development
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn main:app --host 0.0.0.0 --port 8000
```

### API Endpoints

#### 1. Upload Dataset
**POST** `/api/v1/upload`

Upload a CSV dataset with analysis configuration.

**Form Data:**
- `file`: CSV file
- `target_variable`: Column name to analyze
- `target_variable_type`: "Numerical" or "Categorical"
- `data_dictionary`: (Optional) Column descriptions
- `problem_statement`: (Optional) Analysis objective

**Response:**
```json
{
  "success": true,
  "message": "Dataset uploaded successfully",
  "dataset_id": "uuid-string",
  "dataset_info": {
    "filename": "data.csv",
    "target_variable": "target",
    "target_variable_type": "Categorical",
    "stats": {
      "rows": 1000,
      "columns": 10,
      "memory_usage_mb": 0.5,
      "missing_values": {},
      "duplicate_rows": 0,
      "column_types": {...}
    },
    "warnings": []
  }
}
```

#### 2. Analyze Dataset
**POST** `/api/v1/analyze-dataset`

Analyze uploaded dataset and return available columns and their types for dynamic field configuration.

**Form Data:**
- `file`: CSV file

**Response:**
```json
{
  "success": true,
  "message": "Dataset analyzed successfully",
  "dataset_info": {
    "filename": "data.csv",
    "total_rows": 1000,
    "total_columns": 10,
    "columns": [
      {
        "name": "target_variable",
        "type": "Categorical",
        "pandas_type": "object",
        "unique_count": 2,
        "missing_count": 0,
        "sample_values": {"0": 500, "1": 500}
      },
      {
        "name": "feature_1",
        "type": "Numerical",
        "pandas_type": "float64",
        "unique_count": 1000,
        "missing_count": 5,
        "numerical_stats": {
          "min": 0.0,
          "max": 100.0,
          "mean": 50.0,
          "missing_count": 5
        }
      }
    ],
    "suggested_target_variable": "target_variable"
  }
}
```

#### 3. Chat with Agent
**POST** `/api/v1/chat`

Send queries to the agentic system for data analysis.

**Request Body:**
```json
{
  "query": "Show me the distribution of my target variable",
  "dataset_id": "uuid-string"
}
```

**Response:**
```json
{
  "response": "Analysis results...",
  "code": "# Python code snippet",
  "suggestions": [
    "🔍 Explore feature correlations",
    "📊 Create target distribution plot",
    "🧹 Check for data quality issues"
  ],
  "role": "data_transformation"
}
```

#### 4. Get Dataset Statistics
**GET** `/api/v1/datasets/{dataset_id}/stats`

Retrieve comprehensive statistics for a dataset.

#### 5. Delete Dataset
**DELETE** `/api/v1/datasets/{dataset_id}`

Remove a dataset and its associated files.

#### 6. Reinitialize Vector Store
**POST** `/api/v1/vector-store/reinitialize`

Recreate the FAISS vector store from the knowledge base (useful if knowledge base is updated).

#### 7. Health Check
**GET** `/health`

Check system health including vector store status.

### API Documentation

Once the server is running, visit:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## Key Components

### Agentic System
The system uses LangGraph to orchestrate multiple specialized agents:

1. **Router Agent**: Determines which agent should handle the query
2. **Planner Agent**: Creates comprehensive analysis plans
3. **Data Transformation Agent**: Handles data preprocessing and analysis
4. **Modelling Agent**: (Future implementation) For ML model training

### Vector Store
- Uses FAISS for efficient similarity search
- Azure OpenAI `text-embedding-ada-002` for embeddings
- Indexes knowledge base content for contextual retrieval
- Replaces direct knowledge base injection with semantic search

### Dataset Management
- Secure file upload and storage
- Dataset validation and statistics generation
- In-memory metadata storage (use database in production)
- Automatic cleanup of invalid uploads

### MessageState Persistence
- SQLite-based persistent storage for conversation context
- Maintains chat history across API calls
- Automatic state management per dataset
- Support for state reset and cleanup operations

## Configuration

Key configuration options in `app/core/config.py`:

- `AZURE_ENDPOINT`: Azure OpenAI endpoint
- `AZURE_API_KEY`: Azure OpenAI API key
- `AZURE_MODEL`: Model name for completions
- `AZURE_EMBEDDING_MODEL`: Model name for embeddings
- `UPLOAD_DIR`: Directory for uploaded files
- `VECTOR_STORE_PATH`: Directory for FAISS index
- `DATABASE_PATH`: Path to SQLite database for MessageState persistence
- `DATABASE_CLEANUP_DAYS`: Number of days to keep old MessageStates (default: 30)
- `MAX_FILE_SIZE`: Maximum upload file size in bytes (default: 10 GiB / 10737418240). Tighten for production, e.g. `2147483648` (2 GB).
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `LOG_FILE`: Path to log file
- `ENABLE_CONSOLE_LOGGING`: Whether to enable console logging

## Development

### Project Structure
- **API Layer**: FastAPI routes and request/response handling
- **Service Layer**: Business logic and external integrations
- **Model Layer**: Data validation and serialization
- **Core Layer**: Configuration and shared utilities

### Adding New Features
1. Create new service in `app/services/`
2. Add Pydantic models in `app/models/schemas.py`
3. Create API routes in `app/api/routes.py`
4. Update configuration if needed

### API Endpoints

#### Chat Endpoints
- `POST /api/v1/chat` - Chat with agentic system (with persistent state)
- `GET /api/v1/chat/{dataset_id}/history` - Get chat history for a dataset
- `DELETE /api/v1/chat/{dataset_id}/reset` - Reset chat state for a dataset
- `GET /api/v1/chat/states` - List all chat states (admin)

#### Dataset Endpoints
- `POST /api/v1/upload` - Upload dataset
- `POST /api/v1/analyze-dataset` - Analyze dataset structure
- `GET /api/v1/datasets` - List all datasets
- `GET /api/v1/datasets/{dataset_id}/stats` - Get dataset statistics
- `GET /api/v1/datasets/{dataset_id}/raw-data` - Get raw dataset data
- `PUT /api/v1/datasets/{dataset_id}/config` - Update dataset configuration
- `DELETE /api/v1/datasets/{dataset_id}` - Delete dataset and associated chat state

### Testing
```bash
# Run tests (when implemented)
pytest

# Run with coverage
pytest --cov=app
```

## Production Deployment

### Environment Variables
```env
ENDPOINT=your_azure_openai_endpoint
API_KEY=your_azure_openai_api_key
MODEL=your_azure_openai_model_name
ENVIRONMENT=production
```

### Database Integration
Replace in-memory storage with a proper database:
- PostgreSQL for metadata storage
- Redis for caching
- MinIO/S3 for file storage

### Security
- Implement authentication/authorization
- Add rate limiting
- Configure CORS properly
- Use HTTPS in production

### Monitoring
- Structured logging is already implemented with file and console output
- Health checks are available at `/health` endpoint
- Add metrics collection
- Set up error tracking

## Troubleshooting

### Common Issues

1. **Vector Store Initialization Failed**
   - Ensure knowledge base JSON file exists at `../knowledge_base.json`
   - Check Azure OpenAI credentials (both main and embedding endpoints)
   - Verify embedding model availability
   - Use the reinitialize endpoint if needed: `POST /api/v1/vector-store/reinitialize`

2. **File Upload Errors**
   - Check file size limits
   - Ensure CSV format is valid
   - Verify upload directory permissions

3. **Agentic System Errors**
   - Check Azure OpenAI API limits
   - Verify model availability
   - Review LangGraph configuration

### Logs
Check application logs for detailed error information:
```bash
# View logs in real-time
tail -f logs/midas.log

# View recent logs
tail -n 100 logs/midas.log

# Search for errors
grep "ERROR" logs/midas.log
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- Create an issue in the repository
- Check the API documentation at `/docs`
- Review the troubleshooting section above
