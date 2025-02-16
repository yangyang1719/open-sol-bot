FROM python:3.10-slim

WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/libs \
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

# Create necessary directories
RUN mkdir -p /app/libs /app/tg_bot /app/logs

# Install dependencies
COPY ./app/tg-bot/pyproject.toml /app/
COPY ./libs /app/libs
RUN pdm config python.use_venv false && \
    pdm install -G local

CMD ["pdm", "run", "python", "-m", "tg_bot.main"]