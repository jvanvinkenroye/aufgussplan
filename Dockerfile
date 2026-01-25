# syntax=docker/dockerfile:1
FROM python:3.12-slim

LABEL maintainer="aufgussplan"
LABEL description="Scraper für aufgussplan.de - Speichert Sauna-Aufgusspläne in SQLite"

# Installiere cron und sqlite3 CLI
RUN apt-get update && apt-get install -y --no-install-recommends \
    cron \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Arbeitsverzeichnis
WORKDIR /app

# Kopiere Projekt-Dateien
COPY pyproject.toml .
COPY src/ src/

# Installiere uv und Dependencies
RUN pip install --no-cache-dir uv && \
    uv pip install --system --no-cache .

# Datenbank-Verzeichnis
RUN mkdir -p /data

# Kopiere Entrypoint und Cron-Konfiguration
COPY docker/entrypoint.sh /entrypoint.sh
COPY docker/crontab /etc/cron.d/aufgussplan

# Berechtigungen setzen
RUN chmod +x /entrypoint.sh && \
    chmod 0644 /etc/cron.d/aufgussplan && \
    crontab /etc/cron.d/aufgussplan

# Umgebungsvariablen
ENV AUFGUSSPLAN_DB=/data/aufgussplan.db
ENV TZ=Europe/Berlin

# Volume für Datenbank
VOLUME /data

# Healthcheck
HEALTHCHECK --interval=1h --timeout=10s --start-period=5s --retries=3 \
    CMD aufgussplan --db-file /data/aufgussplan.db --db-stats > /dev/null 2>&1 || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["cron", "-f"]
