# ==============================================================================
# FinPilot AI — Production Container Image
# ==============================================================================
FROM python:3.13-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=5000

WORKDIR /app

# Install system dependencies for Tesseract OCR, PyPDF/PDF2Image, and build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    poppler-utils \
    libmagic1 \
    default-libmysqlclient-dev \
    build-essential \
    pkg-config \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir gunicorn>=21.2.0 && \
    pip install --no-cache-dir -r requirements.txt

# Copy project source code
COPY . /app/

# Create non-root user and ensure proper permissions for upload storage
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/uploads && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 5000

# Healthcheck to verify web application responsiveness
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${PORT}/ || exit 1

# Production WSGI server
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT} --workers 3 --threads 2 --timeout 120 run:app"]
