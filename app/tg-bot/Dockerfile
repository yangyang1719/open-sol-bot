FROM localhost/open-sol-bot-base:latest

# Create necessary directories
RUN mkdir -p /app/tg_bot

# Install dependencies
COPY ./libs /app/libs
COPY ./app/tg-bot/pyproject.toml /app/
RUN pdm config python.use_venv false && \
    pdm install -G local

CMD ["pdm", "run", "python", "-m", "tg_bot.main"]