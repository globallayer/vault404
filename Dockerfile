FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Install the package
RUN pip install --no-cache-dir -e .

# Test that imports work
RUN python -c "from clawdex.api.server import app; print('Import OK')"

# Railway provides PORT env var
ENV PORT=8000

# Run the API server
CMD ["sh", "-c", "uvicorn clawdex.api.server:app --host 0.0.0.0 --port $PORT"]
