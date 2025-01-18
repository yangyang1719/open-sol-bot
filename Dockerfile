FROM python:3.10-slim

WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
  PYTHONPATH=/app/src \
  PDM_USE_VENV=false \
  PDM_INSTALL_PATH=/app

# Install system dependencies
RUN apt-get update && apt-get install -y \
  build-essential \
  curl \
  git \
  libssl-dev \
  pkg-config \
  && rm -rf /var/lib/apt/lists/*

# Install PDM
RUN curl -sSL https://pdm.fming.dev/install-pdm.py | python3 - && \
  ln -s /root/.local/bin/pdm /usr/bin/pdm

# Copy project files first to optimize caching
COPY Makefile pyproject.toml pdm.lock ./

# Install dependencies
RUN pdm config python.use_venv false && \
  pdm install --no-self --no-lock

# Copy source code
COPY src/ ./src/

# No CMD here - let docker-compose specify the command for each service
