FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Install the package
RUN pip install --no-cache-dir -e .

# Railway provides PORT env var
ENV PORT=8000
EXPOSE $PORT

# Run the API server - use shell form to expand $PORT
CMD uvicorn clawdex.api.server:app --host 0.0.0.0 --port $PORT
