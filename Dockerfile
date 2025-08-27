FROM python:3.13-slim

WORKDIR /app

# Install dependencies
RUN apt-get update && \
  apt-get install -y --no-install-recommends ca-certificates weasyprint && \
  apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy the necessary files
COPY kivra_sync.py /app/
COPY __version__.py /app/
COPY VERSION /app/
COPY kivra/ /app/kivra/
COPY storage/ /app/storage/
COPY utils/ /app/utils/
COPY interaction/ /app/interaction/

# Make scripts executable
RUN chmod +x /app/kivra_sync.py

# Create directories
RUN mkdir -p /app/temp /data

ENV PYTHONUNBUFFERED=1

# Set entrypoint
ENTRYPOINT ["python", "kivra_sync.py"]

# Default command (can be overridden)
CMD ["--help"]
