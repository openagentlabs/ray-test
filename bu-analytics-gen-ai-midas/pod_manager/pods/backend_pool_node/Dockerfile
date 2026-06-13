FROM python:3.12-slim-bookworm

WORKDIR /app
RUN pip install --no-cache-dir "aiohttp>=3.10"
COPY app.py ./

ENV PORT=8080
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8080\")}/healthz', timeout=2)"

CMD ["python", "app.py"]
