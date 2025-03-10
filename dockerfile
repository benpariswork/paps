FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpcap-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Create necessary directories
RUN mkdir -p data/packets logs

# Expose ports for different protocols
EXPOSE 8080 2121 5353 2323

# Set the entrypoint
ENTRYPOINT ["python", "src/main.py"]

# Default command (can be overridden)
CMD ["--config", "config/config.yaml"]
