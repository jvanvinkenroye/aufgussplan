.PHONY: build up down logs shell scrape stats query help

# Standard-Ziel
help:
	@echo "Aufgussplan Docker Commands:"
	@echo ""
	@echo "  make build    - Docker-Image bauen"
	@echo "  make up       - Container starten"
	@echo "  make down     - Container stoppen"
	@echo "  make logs     - Logs anzeigen"
	@echo "  make shell    - Shell im Container öffnen"
	@echo "  make scrape   - Manuell scrapen"
	@echo "  make stats    - Statistiken anzeigen"
	@echo "  make query    - Aufgüsse für heute anzeigen"
	@echo "  make db       - SQLite CLI öffnen"
	@echo ""

# Docker-Image bauen
build:
	docker compose build

# Container starten
up:
	docker compose up -d

# Container stoppen
down:
	docker compose down

# Logs anzeigen
logs:
	docker compose logs -f

# Shell im Container
shell:
	docker compose exec aufgussplan /bin/bash

# Manuell scrapen
scrape:
	docker compose exec aufgussplan aufgussplan --db-file /data/aufgussplan.db --db --all

# Statistiken anzeigen
stats:
	docker compose exec aufgussplan aufgussplan --db-file /data/aufgussplan.db --db-stats

# Aufgüsse für heute
query:
	docker compose exec aufgussplan aufgussplan --db-file /data/aufgussplan.db --db-query heute

# SQLite CLI
db:
	docker compose exec aufgussplan sqlite3 /data/aufgussplan.db

# Datenbank exportieren
export:
	docker compose exec aufgussplan cat /data/aufgussplan.db > aufgussplan.db
	@echo "Datenbank exportiert: aufgussplan.db"
