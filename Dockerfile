FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Install the package
RUN pip install --no-cache-dir -e .

# Expose port
EXPOSE 8000

# Run the API server
CMD ["uvicorn", "clawdex.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
