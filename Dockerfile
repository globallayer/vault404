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
RUN python -c "from vault404.api.server import app; print('Import OK')"

# Run the API server (Railway provides PORT env var)
CMD ["python", "run.py"]
