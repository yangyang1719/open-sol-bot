FROM localhost/open-sol-bot-base:latest

# Create necessary directories
RUN mkdir -p /app/trading

# Install dependencies
COPY ./libs /app/libs
COPY ./app/trading/pyproject.toml /app/
RUN pdm config python.use_venv false && \
    pdm install -G local

CMD ["pdm", "run", "python", "-m", "trading.main"]