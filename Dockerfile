# ============================================================
# Car Rental System - Production Dockerfile
# ============================================================
# Stage 1: Build image with all dependencies
FROM python:3.11-slim as builder

WORKDIR /build

# Install system dependencies for OCR and image processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    libtesseract-dev \
    libleptonica-dev \
    tesseract-ocr \
    libjpeg-dev \
    libpng-dev \
    libjpeg62-turbo \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PYTHONUNBUFFERED=1
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# Stage 2: Production image
FROM python:3.11-slim

LABEL maintainer="Car Rental System"
LABEL description="Car Rental System with Flask, MySQL, and OCR"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FLASK_APP=app.py \
    FLASK_RUN_HOST=0.0.0.0

# Create non-root user for security
RUN groupadd -r appgroup && useradd -r -g appgroup appuser

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libtesseract-dev \
    libleptonica-dev \
    tesseract-ocr \
    default-libmysqlclient-dev \
    libjpeg-dev \
    libpng-dev \
    libfontconfig1 \
    libxrender1 \
    libxext6 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install Python dependencies
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=appuser:appgroup . .

# Create upload directories with proper permissions
RUN mkdir -p /app/MyFlaskApp/base/uploads/verifications \
             /app/MyFlaskApp/base/uploads/vehicles \
    && chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Expose Flask port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/')" || exit 1

# Run Flask
CMD ["python", "app.py"]