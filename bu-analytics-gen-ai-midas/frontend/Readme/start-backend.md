# Starting the Credit Risk Backend Agent

## Prerequisites

### 1. Node.js and npm
- Node.js 18+ required
- npm or yarn package manager

### 2. Redis Server
Download and install Redis:
- **Windows**: Download from https://github.com/microsoftarchive/redis/releases
- **macOS**: `brew install redis`
- **Linux**: `sudo apt-get install redis-server`

Start Redis server:
```bash
# Windows/macOS/Linux
redis-server
```

### 3. PostgreSQL (Optional)
For production usage, install PostgreSQL:
- Download from https://www.postgresql.org/download/

## Quick Start

### 1. Install Dependencies
```bash
cd backend
npm install
```

### 2. Environment Setup
```bash
# Copy environment template
cp env.example .env

# Edit .env file with your configuration
# At minimum, set:
NODE_ENV=development
PORT=3001
REDIS_URL=redis://localhost:6379
```

### 3. Start the Backend
```bash
# Development mode with hot reload
npm run dev

# Or build and run
npm run build
npm start
```

### 4. Start the ML Engine (Optional)
```bash
cd ../ml-engine

# Install Python dependencies
pip install -r requirements.txt

# Start the ML engine
python main.py
```

## Verification

### Backend Health Check
```bash
curl http://localhost:3001/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "Credit Risk Backend Agent",
  "version": "1.0.0",
  "timestamp": "2024-01-20T12:00:00.000Z"
}
```

### ML Engine Health Check
```bash
curl http://localhost:8000/health
```

## API Endpoints

### Model Builder APIs
- `GET /api/model-builder/data-sources` - Get available data sources
- `POST /api/model-builder/data-collection` - Start data collection
- `GET /api/model-builder/data-quality-report/:datasetId` - Get data quality report
- `POST /api/model-builder/preprocessing/start` - Start preprocessing
- `POST /api/model-builder/features/generate` - Start feature engineering
- `GET /api/model-builder/jobs/:jobId` - Get job status
- `POST /api/model-builder/jobs/:jobId/cancel` - Cancel job

### WebSocket Events
- Connect to `ws://localhost:3001` for real-time updates
- Events: `data_collection_started`, `data_collection_progress`, `data_collection_completed`

## Development Features

### 1. Real-time Updates
- WebSocket integration for live job progress
- Automatic frontend updates during data processing

### 2. Credit Risk Specific
- Banking data simulation
- Credit bureau data integration
- Economic indicators (FRED API)
- Compliance validation (GDPR, Basel III, IFRS 9)

### 3. Mock Data Generation
- 10,000+ synthetic credit records
- Realistic distributions and correlations
- Credit risk features (debt-to-income, credit utilization, etc.)

## Integration with Frontend

The backend automatically integrates with your React frontend:

1. **Data Sources**: Step 2 loads real data sources from `/api/model-builder/data-sources`
2. **Real-time Processing**: WebSocket updates show live progress
3. **Quality Assessment**: AI-powered data quality reports
4. **Feature Engineering**: Credit risk specific feature generation
5. **Compliance**: Regulatory compliance validation

## Troubleshooting

### Redis Connection Issues
```bash
# Check if Redis is running
redis-cli ping
# Should return: PONG
```

### Port Conflicts
If port 3001 is busy, update the PORT in `.env`:
```bash
PORT=3002
```

### CORS Issues
Update `CORS_ORIGIN` in `.env` to match your frontend URL:
```bash
CORS_ORIGIN=http://localhost:5173
```

## Production Deployment

For production deployment:

1. Set `NODE_ENV=production`
2. Configure PostgreSQL database
3. Set up Redis cluster
4. Configure SSL certificates
5. Set up load balancer
6. Enable monitoring and logging

The backend agent is now ready to power your credit risk model development workflow! 