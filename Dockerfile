FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY src/ ./src/
COPY tests/ ./tests/

# Create data directory
RUN mkdir -p /app/data

# Run tests
RUN pytest -q

# Default command
CMD ["python", "-m", "tuner.cli", "start"]
