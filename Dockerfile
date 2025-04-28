FROM python:slim

# Install supercronic for scheduling
ENV SUPERCRONIC_URL=https://github.com/aptible/supercronic/releases/download/v0.1.12/supercronic-linux-amd64 \
    SUPERCRONIC_SHA1SUM=048b95b48b708983effb2e5c935a1ef8483d9e3e \
    SUPERCRONIC=/usr/local/bin/supercronic

RUN apt-get update && apt-get install -y curl \
    && curl -fsSLO "$SUPERCRONIC_URL" \
    && echo "${SUPERCRONIC_SHA1SUM}  supercronic-linux-amd64" | sha1sum -c - \
    && chmod +x supercronic-linux-amd64 \
    && mv supercronic-linux-amd64 "$SUPERCRONIC" \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
ENV POETRY_HOME=/opt/poetry
ENV POETRY_VERSION=1.5.1
ENV POETRY_NO_INTERACTION=1
ENV POETRY_VIRTUALENVS_IN_PROJECT=0
ENV POETRY_VIRTUALENVS_CREATE=0
ENV PATH=${PATH}:${POETRY_HOME}/bin

RUN curl -sSL https://install.python-poetry.org | python3 -

# Set up the application
WORKDIR /app

# Copy pyproject.toml and poetry.lock (if exists)
COPY pyproject.toml poetry.lock* ./

# Install dependencies
RUN poetry install --only main --no-root

# Copy application code
COPY . .

# Create crontab file to run every 8 hours
RUN echo "0 */8 * * * python -m storygrabber.main" > /app/crontab

# Run as non-root user
RUN useradd -m appuser
RUN chown -R appuser:appuser /app
USER appuser

# Run supercronic with our crontab
CMD ["supercronic", "/app/crontab"]
