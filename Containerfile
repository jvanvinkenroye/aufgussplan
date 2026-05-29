# Podman container for aufgussplan scraper
FROM docker.io/library/python:3.12-slim

LABEL maintainer="aufgussplan"
LABEL description="Scraper für aufgussplan.de"

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml .
COPY src/ src/

# Install dependencies
RUN uv pip install --system --no-cache .

# Create non-root user
RUN useradd -m -u 1000 scraper
USER scraper

# Data directory (will be mounted)
VOLUME /data

ENV AUFGUSSPLAN_DB=/data/aufgussplan.db
ENV TZ=Europe/Berlin

ENTRYPOINT ["aufgussplan"]
CMD ["--help"]
