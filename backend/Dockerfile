FROM python:3.11-slim

WORKDIR /app

# System dependencies for OCR (Tesseract) and Chromium (Playwright)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright (for Crawl4AI JS rendering)
RUN playwright install chromium --with-deps

# Copy application
COPY . .

# Create persistent storage directories
RUN mkdir -p /app/uploads /app/data

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
