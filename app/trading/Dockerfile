FROM localhost/open-sol-bot-base:latest

# Install dependencies
COPY ./libs /app/libs
COPY ./app/trading/pyproject.toml /app/
RUN pdm config python.use_venv false && \
    pdm install -G local

ENTRYPOINT [ "pdm", "run", "python", "-m" ]