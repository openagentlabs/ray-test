FROM python:3.13-slim

# Set working directory
WORKDIR /app

# System deps for backend build/runtime (native wheels, health checks).
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install the routing-tier gRPC client from the wheel pre-built by CI
# (deploy/scripts/ci/docker-build-matrix.sh) into backend/vendor/. The client
# lives at ../pod_manager/router.svc/client_py, which is outside this build
# context, so it cannot be installed as an editable path here. Its runtime deps
# (grpcio, protobuf) resolve from the index during this install.
COPY vendor/ ./vendor/
RUN pip install --no-cache-dir ./vendor/*.whl

# Copy application code
COPY . .

# Create non-root user
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start the application with production-grade process manager.
#   - WEB_CONCURRENCY default raised from 1 to 4 so dev/local Docker can serve concurrent
#     requests without queueing behind a single worker. Production overrides this via
#     deploy/ecs-app/helm/midas-api-backend-svc/values.yaml (webConcurrency: 8).
#   - --preload imports the application once in the master process before forking workers.
#     This shares LangChain / model registry / agent imports via copy-on-write, saving
#     ~500 MB-1 GB of RAM per worker (P1.6).
CMD ["sh", "-c", "exec gunicorn main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --workers ${WEB_CONCURRENCY:-4} --timeout ${GUNICORN_TIMEOUT:-300} --preload"]
