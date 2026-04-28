FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy everything (engine at root, api/ folder, schema/)
COPY . .

# Install the concordance engine from repo root
RUN pip install --no-cache-dir -e ".[mcp]"

# Install API dependencies
RUN pip install --no-cache-dir -r api/requirements.txt

# Ledger persists in a mounted volume
RUN mkdir -p /data
ENV LEDGER_PATH=/data/ledger.jsonl
ENV CONCORDANCE_SCHEMA_PATH=/app/schema/packet.schema.json

EXPOSE 8000
CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
