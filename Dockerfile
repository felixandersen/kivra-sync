FROM python:3.13-slim

WORKDIR /app

# Install dependencies
RUN apt-get update && \
  apt-get install -y weasyprint && \
  pip install --no-cache-dir requests qrcode pillow weasyprint

# Copy the necessary files
COPY kivra_sync.py /app/
COPY kivra/ /app/kivra/
COPY storage/ /app/storage/
COPY utils/ /app/utils/
COPY interaction/ /app/interaction/

# Make scripts executable
RUN chmod +x /app/kivra_sync.py

# Create directories
RUN mkdir -p /app/temp /data

# Set entrypoint
ENTRYPOINT ["python", "kivra_sync.py"]

# Default command (can be overridden)
CMD ["--help"]
